/**
 * REST client for the Strategy Template System.
 *
 * Hits the same backend that the rest of the app uses via the shared
 * ``api`` helper at :mod:`@/lib/api` — so the JWT, refresh, and 401
 * handling are inherited automatically.
 */

import { api, type ApiError } from "@/lib/api";
import type {
  CategoryCounts,
  CloneResponse,
  TemplateDetail,
  TemplateListResponse,
} from "./types";

export interface ListTemplatesQuery {
  category?: string;
  complexity?: string;
  segment?: string;
  search?: string;
  is_active?: boolean;
}

function buildQueryString(params: ListTemplatesQuery): string {
  const entries: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    entries.push(
      `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`,
    );
  }
  return entries.length === 0 ? "" : `?${entries.join("&")}`;
}

/** GET /api/templates — filtered list. */
export async function fetchTemplates(
  query: ListTemplatesQuery = {},
): Promise<TemplateListResponse> {
  const qs = buildQueryString(query);
  return api.get<TemplateListResponse>(`/templates${qs}`);
}

/** GET /api/templates/categories — counts per category. */
export async function fetchCategoryCounts(): Promise<CategoryCounts> {
  return api.get<CategoryCounts>("/templates/categories");
}

/** GET /api/templates/{slug} — full detail incl. config_json. */
export async function fetchTemplateDetail(
  slug: string,
): Promise<TemplateDetail> {
  return api.get<TemplateDetail>(`/templates/${encodeURIComponent(slug)}`);
}

/** POST /api/templates/{slug}/clone — materialise a Strategy. */
export async function cloneTemplate(
  slug: string,
  opts: { name?: string } = {},
): Promise<CloneResponse> {
  return api.post<CloneResponse>(
    `/templates/${encodeURIComponent(slug)}/clone`,
    opts.name ? { name: opts.name } : {},
  );
}

export type { ApiError };
