/** Carrier status module API types (P3-38). */

/** A single heterozygous P/LP variant in the carrier panel. */
export interface CarrierVariant {
  rsid: string
  gene_symbol: string
  genotype: string | null
  zygosity: string
  clinvar_significance: string
  clinvar_accession: string | null
  clinvar_review_stars: number
  clinvar_conditions: string | null
  conditions: string[]
  inheritance: string
  evidence_level: number
  cross_links: string[]
  pmids: string[]
  notes: string
}

/** All carrier findings for a sample. */
export interface CarrierVariantsListResponse {
  items: CarrierVariant[]
  total: number
  genes_with_findings: string[]
}

/** Carrier status disclaimer with per-gene notes. */
export interface CarrierDisclaimerResponse {
  title: string
  text: string
  gene_notes: Record<string, string>
}

/** Result of running carrier status analysis. */
export interface CarrierRunResponse {
  findings_count: number
  panel_genes_checked: number
  variants_in_panel_genes: number
  homozygous_plp_skipped: number
}
