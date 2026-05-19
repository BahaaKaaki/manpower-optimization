from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from manpower_app.assumptions import build_assumptions_catalog
from manpower_app.bu_config_io import (
    BUConfigurationPayload,
    build_workbook as build_bu_config_workbook,
    parse_workbook as parse_bu_config_workbook,
)
from manpower_app.family_specs import (
    ActivityProfession,
    CustomFamilyCosts,
    CustomFamilySpec,
    PartialConfig,
)
from manpower_app.service import (
    OptimizationSettings,
    ProcessedWorkbook,
    calculate_target_split_from_data,
    dataframe_records,
    prepare_model_data,
    process_workbook,
    run_optimization,
)


# --- pydantic mirrors of the dataclasses in manpower_app.family_specs (used for API
# input validation) ----------------------------------------------------------------

class ActivityProfessionRequest(BaseModel):
    activity: str
    profession: str

    def to_dataclass(self) -> ActivityProfession:
        return ActivityProfession(activity=self.activity, profession=self.profession)


class PartialConfigRequest(BaseModel):
    kind: Literal["percent", "fixed", "driver"]
    percent: float | None = Field(default=None, ge=0, le=1)
    fixed_count: int | None = Field(default=None, ge=0)
    driver_activity: str | None = None
    driver_profession: str | None = None
    max_ratio: str | None = None

    def to_dataclass(self) -> PartialConfig:
        return PartialConfig(
            kind=self.kind,
            percent=self.percent,
            fixed_count=self.fixed_count,
            driver_activity=self.driver_activity,
            driver_profession=self.driver_profession,
            max_ratio=self.max_ratio,
        )


class CustomFamilyCostsRequest(BaseModel):
    saudi_inhouse: float = Field(ge=0)
    non_saudi_inhouse: float = Field(ge=0)
    outsourced: float = Field(ge=0)

    def to_dataclass(self) -> CustomFamilyCosts:
        return CustomFamilyCosts(
            saudi_inhouse=self.saudi_inhouse,
            non_saudi_inhouse=self.non_saudi_inhouse,
            outsourced=self.outsourced,
        )


class CustomFamilySpecRequest(BaseModel):
    family_name: str
    outsourceability: Literal[
        "Fully Outsourceable", "Partially Outsourceable", "Not Outsourceable"
    ]
    source_pairs: list[ActivityProfessionRequest] = Field(default_factory=list)
    partial_config: PartialConfigRequest | None = None
    costs: CustomFamilyCostsRequest | None = None

    def to_dataclass(self) -> CustomFamilySpec:
        return CustomFamilySpec(
            family_name=self.family_name,
            outsourceability=self.outsourceability,
            source_pairs=[pair.to_dataclass() for pair in self.source_pairs],
            partial_config=self.partial_config.to_dataclass() if self.partial_config else None,
            costs=self.costs.to_dataclass() if self.costs else None,
        )


def _custom_families_from_json(payload: str | None) -> list[CustomFamilySpec]:
    """Decode a JSON-string list of CustomFamilySpec from a multipart form field."""
    if not payload:
        return []
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"custom_families JSON malformed: {exc}") from exc
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="custom_families must be a JSON array.")
    specs: list[CustomFamilySpec] = []
    for entry in raw:
        try:
            specs.append(CustomFamilySpecRequest.model_validate(entry).to_dataclass())
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"custom_families entry invalid: {exc}",
            ) from exc
    return specs


class OptimizationSettingsRequest(BaseModel):
    enforce_saudization: bool = True
    saudization_rate: float = Field(default=0.30, ge=0, le=1)
    can_reduce_current_saudi: bool = False
    # Dynamic Saudi protection (0.0–1.0). When provided, it overrides the legacy
    # `can_reduce_current_saudi` boolean and protects that fraction per family.
    protect_current_saudi_percent: float | None = Field(default=None, ge=0, le=1)
    risk_factor: float = Field(default=0.25, ge=0, le=1)
    negotiated_rates: bool = False
    negotiated_insurance_cost: float = 0.0
    negotiated_service_margin: float = 0.0
    protect_tenured_inhouse: bool = False
    tenure_threshold_years: float = Field(default=5.0, ge=0, le=60)
    engineer_saudization_rate: float = Field(default=0.25, ge=0, le=1)
    sales_saudization_rate: float = Field(default=0.60, ge=0, le=1)
    management_saudization_rate: float = Field(default=0.35, ge=0, le=1)
    saudi_cost_premium: float = Field(default=1.10, ge=1.0, le=3.0)
    outsource_cost_discount: float | None = Field(default=None, ge=0, le=1)
    max_ratio_overrides: dict[str, str] = Field(default_factory=dict)
    # Batch-2 BU configuration overrides. Empty defaults preserve historical behavior.
    outsourceability_overrides: dict[str, str] = Field(default_factory=dict)
    driver_overrides: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    optimization_mode: Literal["current", "target"] = "current"
    target_headcounts: dict[str, int] = Field(default_factory=dict)
    custom_families: list[CustomFamilySpecRequest] = Field(default_factory=list)

    def to_settings(self) -> OptimizationSettings:
        payload = self.model_dump(exclude={"custom_families"})
        return OptimizationSettings(
            **payload,
            custom_families=[spec.to_dataclass() for spec in self.custom_families],
        )


class ReprocessRequest(BaseModel):
    custom_families: list[CustomFamilySpecRequest] = Field(default_factory=list)
    # Batch-2: route an unmapped (activity, profession) pair to an existing canonical
    # family by name. Keyed by "activity|profession" to match the frontend persistence.
    payroll_pair_overrides: dict[str, str] = Field(default_factory=dict)


class AppStore:
    processed: ProcessedWorkbook | None = None
    workbook_bytes: bytes | None = None
    workbook_filename: str | None = None
    model_data = None
    model_metadata: dict[str, Any] | None = None
    target_split = None
    optimization_payload: dict[str, Any] | None = None


store = AppStore()
app = FastAPI(title="Manpower Optimization API")
# Browser dev (any Vite port): regex so changing `npm run dev -- --port` does not require edits here.
# Tauri webviews use fixed origins below.
_LOCAL_HTTP_ORIGIN_RE = r"http://(127\.0\.0\.1|localhost)(:\d+)?"


def _cors_allow_origins() -> list[str]:
    origins = [
        "tauri://127.0.0.1",
        "tauri://localhost",
    ]
    extra = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
    if extra:
        origins.extend(part.strip() for part in extra.split(",") if part.strip())
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_origin_regex=_LOCAL_HTTP_ORIGIN_RE,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_processed() -> ProcessedWorkbook:
    if store.processed is None:
        raise HTTPException(status_code=400, detail="Upload a workbook before running the model.")
    return store.processed


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/assumptions")
def assumptions() -> dict[str, Any]:
    """Return the catalog of every hardcoded business rule and default in the tool.

    The desktop UI calls this on load and renders the response in an "Assumptions & Rules"
    panel so reviewers can audit what the optimizer is doing without reading code.
    """
    return build_assumptions_catalog()


@app.get("/assumptions/defaults")
def assumption_defaults() -> dict[str, Any]:
    """Per-BU Configuration seeds. The desktop Configuration panel calls this once on
    load to render the *default* outsourceability, ratio, and driver values; the user's
    saved overrides per BU are then layered on top of these defaults in the UI."""
    from manpower_app.rules import MAXIMUM_RATIO_RULES, OUTSOURCEABILITY_RULES

    driver_defaults: dict[str, list[dict[str, str]]] = {
        "Quarries Foreman": [
            {"activity": "Quarries", "profession": "Labor"},
            {"activity": "Quarries", "profession": "Skilled Labor"},
            {"activity": "Quarries", "profession": "Technician"},
        ],
        "Production Foreman": [
            {"activity": "Factory", "profession": "Labor"},
            {"activity": "Factory", "profession": "Skilled Labor"},
            {"activity": "Factory", "profession": "Technician"},
        ],
        "Installation Foreman": [
            {"activity": "Installation", "profession": "Skilled Labor"},
            {"activity": "Installation", "profession": "Labor"},
        ],
        "Showroom Supervisor": [
            {"activity": "Showroom", "profession": "Labor"},
            {"activity": "Showroom", "profession": "Skilled Labor"},
            {"activity": "Showroom", "profession": "Store Keeper"},
            {"activity": "Showroom", "profession": "Foreman"},
            {"activity": "Showroom", "profession": "Operator"},
        ],
        "Safety Officer": [
            {"activity": "Factory", "profession": ""},
            {"activity": "Idle Saudi Labor", "profession": ""},
            {"activity": "Installation", "profession": ""},
            {"activity": "Quarries", "profession": ""},
        ],
        "Quarries Supervisor": [{"activity": "Quarries", "profession": "Foreman"}],
        "Installation Supervisor": [{"activity": "Installation", "profession": "Foreman"}],
        "Factory Supervisor": [{"activity": "Factory", "profession": "Foreman"}],
    }
    return {
        "outsourceability": dict(sorted(OUTSOURCEABILITY_RULES.items())),
        "max_ratios": dict(sorted(MAXIMUM_RATIO_RULES.items())),
        "drivers": driver_defaults,
    }


class BUConfigurationExportRequest(BaseModel):
    bu_code: str
    bu_name: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


@app.get("/bu/configuration/template")
def bu_configuration_template(bu_code: str = "", bu_name: str = "") -> Response:
    """Download a blank-template workbook. Use the empty-config path so all override
    columns are blank — the user can fill them in Excel and re-upload. If no `bu_code`
    is provided the file is a generic shared template (still valid)."""
    payload = BUConfigurationPayload()
    xlsx = build_bu_config_workbook(bu_code or "(template)", bu_name or None, payload)
    filename = f"{(bu_code or 'manpower-bu')}_configuration_template.xlsx"
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/bu/configuration/export")
def bu_configuration_export(payload: BUConfigurationExportRequest) -> Response:
    """Download the user's currently-saved BU configuration as XLSX."""
    config = BUConfigurationPayload.from_dict(payload.configuration)
    xlsx = build_bu_config_workbook(payload.bu_code, payload.bu_name, config)
    filename = f"{payload.bu_code or 'manpower-bu'}_configuration.xlsx"
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/bu/configuration/import")
async def bu_configuration_import(file: UploadFile) -> dict[str, Any]:
    """Parse an uploaded Configuration XLSX, validate, return the parsed payload.
    The frontend persists it locally — the server is stateless here so the user can
    sanity-check the result before saving."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    contents = await file.read()
    config, errors = parse_bu_config_workbook(contents)
    return {"configuration": config.to_dict(), "errors": errors}


def _build_upload_response(processed: ProcessedWorkbook, filename: str | None) -> dict[str, Any]:
    families = []
    if not processed.optimization_df.empty:
        for _, row in processed.optimization_df.iterrows():
            families.append({
                "family_name": str(row["Job Family"]),
                "current_headcount": int(row.get("Current Headcount", 0) or 0),
                "outsourceability": str(row.get("Outsourceability Type", "")),
            })
    return {
        "filename": filename,
        "job_family_count": int(len(processed.optimization_df)),
        "inhouse_count": int(len(processed.inhouse_cleaned)),
        "subcontractor_count": int(len(processed.subcontractor_cleaned)),
        "service_fee_column": processed.service_fee_column,
        "tenure_source_column": processed.tenure_source_column,
        "model_input_count": int(len(processed.optimization_df)),
        "unmapped_pairs": processed.unmapped_pairs,
        "workbook_pairs": processed.workbook_pairs,
        "families": families,
    }


@app.post("/workbooks/upload")
async def upload_workbook(
    file: UploadFile,
    custom_families: str | None = Form(default=None),
) -> dict[str, Any]:
    """Upload a workbook and process it.

    ``custom_families`` is an optional JSON-encoded array of
    ``CustomFamilySpec`` objects (matches the desktop client's persisted prefs).
    Unmapped (activity, profession) pairs are returned in ``unmapped_pairs`` rather
    than failing the upload, so the UI can collect resolutions interactively.
    """
    custom_specs = _custom_families_from_json(custom_families)
    try:
        contents = await file.read()
        store.workbook_bytes = contents
        store.workbook_filename = file.filename
        store.processed = process_workbook(io.BytesIO(contents), custom_families=custom_specs)
        store.model_data = None
        store.model_metadata = None
        store.target_split = None
        store.optimization_payload = None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _build_upload_response(require_processed(), file.filename)


@app.post("/workbooks/reprocess")
def reprocess_workbook(payload: ReprocessRequest) -> dict[str, Any]:
    """Re-run :func:`process_workbook` on the cached workbook with a refreshed set
    of user-supplied family resolutions. Used by the UI after the user fills in
    answers on the Mappings step.
    """
    if store.workbook_bytes is None:
        raise HTTPException(status_code=400, detail="Upload a workbook before resolving mappings.")
    custom_specs = [spec.to_dataclass() for spec in payload.custom_families]
    try:
        store.processed = process_workbook(
            io.BytesIO(store.workbook_bytes),
            custom_families=custom_specs,
            payroll_pair_overrides=payload.payroll_pair_overrides or None,
        )
        store.model_data = None
        store.model_metadata = None
        store.target_split = None
        store.optimization_payload = None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_upload_response(require_processed(), store.workbook_filename)


@app.get("/model/input")
def model_input() -> dict[str, Any]:
    processed = require_processed()
    return {"rows": dataframe_records(processed.optimization_df)}


@app.post("/optimization/target-split")
def target_split(settings: OptimizationSettingsRequest) -> dict[str, Any]:
    processed = require_processed()
    data, metadata = prepare_model_data(processed, settings.to_settings())
    store.model_data = data
    store.model_metadata = metadata
    store.target_split = calculate_target_split_from_data(data)
    return {
        "metadata": metadata,
        "rows": dataframe_records(store.target_split),
        "model_processing": dataframe_records(data),
    }


def optimization_summary(results: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        # Present in current mode only:
        "current_payroll_cost": metadata.get("current_payroll_cost"),
        "optimized_savings": metadata.get("optimized_savings"),
        # Present always:
        "optimized_payroll": metadata.get("optimized_payroll"),
        "final_scenario_label": metadata.get("final_scenario_label"),
        "optimization_mode": metadata.get("optimization_mode", "current"),
        "target_headcount_total": metadata.get("target_headcount_total"),
        "total_cost": results["total_cost"],
        "total_saudi_final": results["total_saudi_final"],
        "total_non_saudi_final": results["total_non_saudi_final"],
        "total_outsourced_final": results["total_outsourced_final"],
        "total_employees_final": results["total_employees_final"],
        "saudization_achieved": results["saudization_achieved"],
        "optimization_status": results["optimization_status"],
        "total_cost_saudi": results["total_cost_saudi"],
        "total_cost_non_saudi": results["total_cost_non_saudi"],
        "total_cost_outsourced": results["total_cost_outsourced"],
    }


@app.post("/optimization/run")
def run(settings: OptimizationSettingsRequest) -> dict[str, Any]:
    processed = require_processed()
    store.optimization_payload = run_optimization(processed, settings.to_settings())
    store.model_data = store.optimization_payload["data"]
    store.model_metadata = store.optimization_payload["metadata"]
    results = store.optimization_payload["results"]
    return {
        "metadata": store.model_metadata,
        "summary": optimization_summary(results, store.model_metadata),
        "results": dataframe_records(results["results_df"]),
        "model_processing": dataframe_records(store.model_data),
        "audit": dataframe_records(store.optimization_payload["audit"]),
    }


@app.get("/optimization/results", response_model=None)
def optimization_results() -> Any:
    if store.optimization_payload is None:
        return Response(status_code=204)
    results = store.optimization_payload["results"]
    return {
        "metadata": store.optimization_payload["metadata"],
        "summary": optimization_summary(results, store.optimization_payload["metadata"]),
        "results": dataframe_records(results["results_df"]),
        "model_processing": dataframe_records(store.optimization_payload["data"]),
        "audit": dataframe_records(store.optimization_payload["audit"]),
    }


@app.get("/exports/results.xlsx")
def export_results() -> Response:
    if store.optimization_payload is None:
        raise HTTPException(status_code=404, detail="Run optimization before downloading results.")
    return Response(
        content=store.optimization_payload["export_bytes"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Manpower_Optimization_Results.xlsx"'},
    )


def _mount_frontend_static(app_instance: FastAPI) -> None:
    """Serve the Vite production build from STATIC_ROOT (same-origin API + SPA for Docker / Azure)."""
    raw = os.environ.get("STATIC_ROOT", "").strip()
    if not raw:
        return
    root = Path(raw)
    if not root.is_dir():
        return
    app_instance.mount("/", StaticFiles(directory=str(root), html=True), name="spa")


_mount_frontend_static(app)
