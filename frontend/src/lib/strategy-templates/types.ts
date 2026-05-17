/**
 * TypeScript types mirroring the backend Pydantic schemas at
 * ``backend/app/templates/schemas.py``. Kept hand-written rather than
 * codegen'd so the wire contract is reviewable in PR and the
 * narrowing for the 3 picker card states (active equity / cataloged
 * equity / options-pending) is explicit.
 */

export type Segment =
  | "EQUITY"
  | "FUTURES"
  | "OPTIONS"
  | "COMMODITY"
  | "CURRENCY";

export type InstrumentType =
  | "CASH"
  | "FUTURES"
  | "CALL"
  | "PUT"
  | "MULTI_LEG";

export type Complexity =
  | "beginner"
  | "intermediate"
  | "advanced"
  | "expert";

export type RiskLevel = "low" | "medium" | "high";

/** The three card states the picker renders. Resolved from
 *  ``is_active`` + ``requires_options_builder``. */
export type TemplateCardState =
  | "active-equity"
  | "inactive-equity-coming-soon"
  | "options-builder-required";

export interface TemplateSummary {
  id: string;
  slug: string;
  name: string;
  segment: Segment;
  instrument_type: InstrumentType;
  category: string;
  complexity: Complexity;
  description_en: string;
  risk_level: RiskLevel;
  recommended_capital_inr: number;
  timeframe: string;
  indicators_used: string[];
  tags: string[];
  is_active: boolean;
  requires_options_builder: boolean;
  legs_count: number | null;
  display_order: number;
}

export interface TemplateDetail extends TemplateSummary {
  description_hi: string;
  config_json: Record<string, unknown>;
  index_filter: string[];
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  total: number;
  active_count: number;
  inactive_count: number;
  items: TemplateSummary[];
}

export interface CategoryCount {
  category: string;
  total: number;
  active: number;
}

export interface CategoryCounts {
  items: CategoryCount[];
}

export interface CloneResponse {
  strategy_id: string;
  strategy_name: string;
  template_slug: string;
  message: string;
}

/** Resolves a template's UX card state from its flags. */
export function resolveCardState(t: TemplateSummary): TemplateCardState {
  if (t.requires_options_builder) return "options-builder-required";
  if (t.is_active) return "active-equity";
  return "inactive-equity-coming-soon";
}
