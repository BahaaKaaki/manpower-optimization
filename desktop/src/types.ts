// Tier 5 — user-defined family specs

export type ActivityProfession = { activity: string; profession: string };

export type OutsourceabilityKind =
  | "Fully Outsourceable"
  | "Partially Outsourceable"
  | "Not Outsourceable";

export type PartialKind = "percent" | "fixed" | "driver";

export type PartialConfig = {
  kind: PartialKind;
  percent?: number | null;
  fixed_count?: number | null;
  driver_activity?: string | null;
  driver_profession?: string | null;
  max_ratio?: string | null;
};

export type CustomFamilyCosts = {
  saudi_inhouse: number;
  non_saudi_inhouse: number;
  outsourced: number;
};

export type CustomFamilySpec = {
  family_name: string;
  outsourceability: OutsourceabilityKind;
  source_pairs: ActivityProfession[];
  partial_config?: PartialConfig | null;
  costs?: CustomFamilyCosts | null;
};

export type UnmappedPair = { activity: string; profession: string; count: number };

export type OptimizationMode = "current" | "target";

export type Settings = {
  enforce_saudization: boolean;
  saudization_rate: number;
  can_reduce_current_saudi: boolean;
  risk_factor: number;
  negotiated_rates: boolean;
  negotiated_insurance_cost: number;
  negotiated_service_margin: number;
  protect_tenured_inhouse: boolean;
  tenure_threshold_years: number;
  engineer_saudization_rate: number;
  sales_saudization_rate: number;
  management_saudization_rate: number;
  saudi_cost_premium: number;
  outsource_cost_discount: number | null;
  max_ratio_overrides: Record<string, string>;
  optimization_mode: OptimizationMode;
  target_headcounts: Record<string, number>;
  custom_families: CustomFamilySpec[];
};

export type FamilySummary = {
  family_name: string;
  current_headcount: number;
  outsourceability: string;
};

export type UploadResponse = {
  filename: string;
  job_family_count: number;
  inhouse_count: number;
  subcontractor_count: number;
  service_fee_column?: string | null;
  tenure_source_column?: string | null;
  model_input_count?: number;
  model_input?: Record<string, unknown>[];
  unmapped_pairs?: UnmappedPair[];
  workbook_pairs?: ActivityProfession[];
  families?: FamilySummary[];
};

export type OptimizationSummary = {
  current_payroll_cost?: number;
  optimized_payroll?: number;
  optimized_savings?: number;
  optimization_mode?: OptimizationMode;
  target_headcount_total?: number;
  final_scenario_label?: string;
  total_cost: number;
  total_saudi_final: number;
  total_non_saudi_final: number;
  total_outsourced_final: number;
  total_employees_final: number;
  saudization_achieved: number;
  optimization_status: string;
  total_cost_saudi: number;
  total_cost_non_saudi: number;
  total_cost_outsourced: number;
};

export type OptimizationMetadata = {
  current_payroll_cost?: number;
  optimized_payroll?: number;
  optimized_savings?: number;
  optimization_status?: string;
  final_scenario_label?: string;
  tenure_constraint_active?: boolean;
  risk_formula?: string;
};

export type OptimizationResponse = {
  metadata: OptimizationMetadata;
  summary: OptimizationSummary;
  results: Record<string, number | string>[];
  model_processing: Record<string, number | string | null>[];
  audit?: Record<string, number | string | boolean | null>[];
};

export type TargetSplitResponse = {
  metadata: Record<string, number | string | boolean>;
  rows: Record<string, unknown>[];
  model_processing: Record<string, number | string | null>[];
};

export type AppStage = "home" | "upload" | "mappings" | "ready" | "results";
export type DetailTab = "insights" | "families" | "target" | "audit";

export type AssumptionsCatalog = {
  outsourceability_rules: {
    description: string;
    categories: Record<string, string>;
    rules_by_family: Record<string, string>;
  };
  special_profession_rules: Array<{
    families: string[];
    rule: string;
    description: string;
    applies_to_categories: string[];
    implemented_in: string;
  }>;
  maximum_ratio_rules: {
    description: string;
    rules_by_family: Record<string, string>;
  };
  default_optimization_settings: Array<{
    key: string;
    default: number | boolean;
    unit: string;
    description: string;
  }>;
  cost_assumptions: Array<{
    name: string;
    value: string;
    description: string;
    implemented_in: string;
  }>;
  input_format: {
    required_sheets: string[];
    required_inhouse_columns: string[];
    required_subcontractor_columns: string[];
    nationality_detection: string;
    tenure_detection: string;
  };
  risk_formula: {
    formula: string;
    description: string;
    edge_case_risk_zero: string;
  };
};

export type BusyAction = "upload" | "target" | "optimize" | "mappings" | null;

export type ChartItem = {
  label: string;
  value: number;
  color: string;
  displayValue: string;
};
