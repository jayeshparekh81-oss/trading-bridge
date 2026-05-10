/**
 * Wire shapes for ``POST /api/strategies/pine-import``.
 *
 * The backend's :func:`convert_pine_to_strategy` returns one of two
 * dict shapes (success vs failure / partial). We mirror that as a
 * discriminated union so the result panel can switch on
 * ``response.success`` / ``response.partial`` cleanly.
 */
export type LicenseStatus =
  | "permissive"
  | "compliance_required"
  | "needs_review"
  | "blocked";


export interface PineImportSuccess {
  success: true;
  strategy: Record<string, unknown>;
  explanation: string;
  license_status: LicenseStatus;
  notes: string[];
}


export interface PineImportFailure {
  success: false;
  partial: boolean;
  converted: Record<string, unknown> | null;
  unsupported: string[];
  message: string;
  license_status: LicenseStatus;
}


export type PineImportResponse = PineImportSuccess | PineImportFailure;
