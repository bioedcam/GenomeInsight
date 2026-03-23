/** Custom gene panel API types (P4-11). */

/** A saved custom gene panel. */
export interface CustomPanel {
  id: number
  name: string
  description: string
  gene_symbols: string[]
  bed_regions: BedRegion[] | null
  source_type: "gene_list" | "bed"
  gene_count: number
  created_at: string | null
}

/** A BED region from a panel. */
export interface BedRegion {
  chrom: string
  start: number
  end: number
  name: string | null
}

/** List of all saved custom panels. */
export interface CustomPanelListResponse {
  items: CustomPanel[]
  total: number
}

/** Preview result from parsing a file. */
export interface ParsePreviewResponse {
  gene_symbols: string[]
  gene_count: number
  region_count: number
  source_type: string
  warnings: string[]
}

/** Response after uploading and saving a panel. */
export interface PanelUploadResponse {
  panel: CustomPanel
  warnings: string[]
}

/** Search request body for panel-based rare variant search. */
export interface PanelSearchRequest {
  af_threshold?: number
  consequences?: string[] | null
  clinvar_significance?: string[] | null
  include_novel?: boolean
  zygosity?: string | null
}

/** Response from panel-based rare variant search. */
export interface PanelSearchResponse {
  panel_name: string
  variants_found: number
  findings_stored: number
  total_variants_scanned: number
  novel_count: number
  pathogenic_count: number
  genes_with_findings: string[]
}
