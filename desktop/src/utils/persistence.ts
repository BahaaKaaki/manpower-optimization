// Persistent key-value store for user preferences (e.g. custom job-family mappings).
// Backed by tauri-plugin-store (a JSON file in the OS app-data directory) when running
// in the Tauri desktop app, and by localStorage when running in a plain browser
// (the Azure web deploy or `npm run dev` without Tauri).

import type { Store } from "@tauri-apps/plugin-store";

const STORE_FILE = "manpower-prefs.json";

let storePromise: Promise<Store | null> | null = null;

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function getStore(): Promise<Store | null> {
  if (!isTauri()) return null;
  if (!storePromise) {
    storePromise = import("@tauri-apps/plugin-store").then(({ load }) =>
      load(STORE_FILE).catch((err) => {
        // Failure to open the file (e.g. permissions) shouldn't break the app —
        // fall through to the localStorage path below.
        console.error("tauri-plugin-store load failed, falling back to localStorage:", err);
        return null;
      }),
    );
  }
  return storePromise;
}

export async function persistGet<T>(key: string, fallback: T): Promise<T> {
  const store = await getStore();
  if (store) {
    const value = await store.get<T>(key);
    return (value ?? fallback) as T;
  }
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function persistSet<T>(key: string, value: T): Promise<void> {
  const store = await getStore();
  if (store) {
    await store.set(key, value);
    await store.save();
    return;
  }
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export async function persistDelete(key: string): Promise<void> {
  const store = await getStore();
  if (store) {
    await store.delete(key);
    await store.save();
    return;
  }
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}
