#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(not(debug_assertions))]
use std::net::TcpListener;
use std::sync::Mutex;

use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct SidecarState {
    child: Mutex<Option<CommandChild>>,
}

struct ApiBaseUrl(String);

fn terminate_sidecar(child: CommandChild) {
    let pid = child.pid();

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;

        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }

    #[cfg(unix)]
    {
        terminate_unix_descendants(pid);
    }

    let _ = child.kill();
}

#[cfg(unix)]
fn terminate_unix_descendants(pid: u32) {
    let Ok(output) = std::process::Command::new("pgrep")
        .args(["-P", &pid.to_string()])
        .output()
    else {
        return;
    };

    let child_pids = String::from_utf8_lossy(&output.stdout)
        .lines()
        .filter_map(|line| line.trim().parse::<u32>().ok())
        .collect::<Vec<_>>();

    for child_pid in &child_pids {
        terminate_unix_descendants(*child_pid);
    }

    for child_pid in child_pids {
        let _ = std::process::Command::new("kill")
            .args(["-TERM", &child_pid.to_string()])
            .status();
    }
}

fn stop_sidecar_on_exit<R: tauri::Runtime>(
    app_handle: &tauri::AppHandle<R>,
    event: tauri::RunEvent,
) {
    if let tauri::RunEvent::Exit = event {
        if let Some(state) = app_handle.try_state::<SidecarState>() {
            let mut guard = state
                .child
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if let Some(child) = guard.take() {
                terminate_sidecar(child);
            }
        }
    }
}

#[cfg(not(debug_assertions))]
fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("could not bind to find free port")
        .local_addr()
        .expect("could not get local address")
        .port()
}

#[tauri::command]
fn get_manpower_api_base(api_base_url: tauri::State<'_, ApiBaseUrl>) -> String {
    api_base_url.0.clone()
}

#[cfg(not(debug_assertions))]
fn api_port() -> u16 {
    free_port()
}

#[cfg(debug_assertions)]
fn api_port() -> u16 {
    8765
}

fn main() {
    let context = tauri::generate_context!();
    let api_port = api_port();
    let api_port_string = api_port.to_string();
    let api_base_url = format!("http://127.0.0.1:{api_port}");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .manage(ApiBaseUrl(api_base_url))
        .invoke_handler(tauri::generate_handler![get_manpower_api_base])
        .setup(move |app| {
            app.manage(SidecarState {
                child: Mutex::new(None),
            });

            match app.shell().sidecar("manpower-api") {
                Ok(command) => {
                    {
                        let sidecar = app.state::<SidecarState>();
                        let mut slot = sidecar
                            .child
                            .lock()
                            .expect("sidecar state mutex poisoned");
                        if let Some(old) = slot.take() {
                            terminate_sidecar(old);
                        }
                    }

                    let (rx, child) = command
                        .env("MANPOWER_API_HOST", "127.0.0.1")
                        .env("MANPOWER_API_PORT", &api_port_string)
                        .spawn()?;

                    let sidecar = app.state::<SidecarState>();
                    *sidecar
                        .child
                        .lock()
                        .expect("sidecar state mutex poisoned") = Some(child);

                    tauri::async_runtime::spawn(async move {
                        let mut rx = rx;
                        while rx.recv().await.is_some() {}
                    });
                }
                Err(error) => {
                    return Err(error.into());
                }
            }
            Ok(())
        })
        .build(context)
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            stop_sidecar_on_exit(app_handle, event);
        });
}
