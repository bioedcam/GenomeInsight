/** vcfanno overlay API types (P4-12). */

/** A saved overlay configuration. */
export interface OverlayConfig {
  id: number
  name: string
  description: string
  file_type: "bed" | "vcf"
  column_names: string[]
  region_count: number
  created_at: string | null
}

/** List of all saved overlays. */
export interface OverlayListResponse {
  items: OverlayConfig[]
  total: number
}

/** Preview result from parsing an overlay file. */
export interface OverlayParsePreviewResponse {
  file_type: "bed" | "vcf"
  column_names: string[]
  record_count: number
  warnings: string[]
}

/** Response after uploading and saving an overlay. */
export interface OverlayUploadResponse {
  overlay: OverlayConfig
  warnings: string[]
}

/** Response from applying an overlay to a sample. */
export interface OverlayApplyResponse {
  overlay_id: number
  overlay_name: string
  variants_matched: number
  records_checked: number
}

/** Overlay results for a sample. */
export interface OverlayResultsResponse {
  overlay_id: number
  overlay_name: string
  results: Record<string, unknown>[]
  total: number
}
