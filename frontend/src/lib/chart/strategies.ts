/**
 * Chart-module strategies fetch — minimal shell over ``GET /api/strategies``
 * for the StrategySelector dropdown.
 *
 * The dashboard's ``/strategies`` page consumes the full strategy
 * shape via :func:`useApi`; the chart only needs ``{ id, name,
 * is_active }`` so we ship a narrower wrapper here. Same mock-toggle
 * + same backend endpoint, just a smaller projection.
 */

import { api } from "@/lib/api";

import { getMockStrategies, isMockEnabled } from "./mock_data";
import type { ChartStrategyListResponse } from "./types";

export interface FetchStrategiesOptions {
  /** Test-injection override of the env-based mock toggle. */
  forceMock?: boolean;
}

export async function fetchUserStrategies(
  opts: FetchStrategiesOptions = {},
): Promise<ChartStrategyListResponse> {
  if (opts.forceMock ?? isMockEnabled()) {
    return Promise.resolve(getMockStrategies());
  }
  return api.get<ChartStrategyListResponse>("/strategies");
}
