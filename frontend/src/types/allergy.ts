/** Gene Allergy API types (P3-61). */

/** Categorical level for an allergy pathway. */
export type PathwayLevel = "Elevated" | "Moderate" | "Standard"

/** HLA proxy metadata for a SNP. */
export interface HLAProxyInfo {
  hla_allele: string
  proxy_rsid: string
  r_squared: number
  ancestry_pop: string
  clinical_context: string | null
  pmid: string | null
}

/** Per-SNP result within an allergy pathway. */
export interface SNPDetail {
  rsid: string
  gene: string
  variant_name: string
  genotype: string | null
  category: PathwayLevel
  effect_summary: string
  evidence_level: number
  recommendation: string | null
  pmids: string[]
  /** HLA proxy metadata from panel definition. */
  hla_proxy: HLAProxyInfo | null
  /** HLA proxy lookup result from reference DB. */
  hla_proxy_lookup: Record<string, unknown> | null
  /** Coverage caveat text. */
  coverage_note: string | null
}

/** Summary of a single allergy pathway. */
export interface PathwaySummary {
  pathway_id: string
  pathway_name: string
  level: PathwayLevel
  evidence_level: number
  called_snps: number
  total_snps: number
  missing_snps: string[]
  pmids: string[]
  hla_proxy_lookup: Record<string, unknown> | null
}

/** Celiac DQ2/DQ8 combined assessment result. */
export interface CeliacCombinedItem {
  state: "neither" | "dq2_only" | "dq8_only" | "both"
  label: string
  dq2_genotype: string | null
  dq8_genotype: string | null
  description: string | null
  evidence_level: number
  pmids: string[]
}

/** Histamine metabolism combined assessment result. */
export interface HistamineCombinedItem {
  aoc1_genotype: string | null
  hnmt_genotype: string | null
  aoc1_category: string
  hnmt_category: string
  combined_text: string
  de_emphasize: boolean
  evidence_level: number
  pmids: string[]
}

/** Cross-module reference finding. */
export interface CrossModuleItem {
  rsid: string
  gene: string
  source_module: string
  target_module: string
  finding_text: string
  evidence_level: number
  pmids: string[]
}

/** All pathway results for a sample. */
export interface PathwaysResponse {
  items: PathwaySummary[]
  total: number
  celiac_combined: CeliacCombinedItem | null
  histamine_combined: HistamineCombinedItem | null
  cross_module: CrossModuleItem[]
}

/** Full pathway detail with per-SNP breakdown. */
export interface PathwayDetailResponse {
  pathway_id: string
  pathway_name: string
  level: PathwayLevel
  evidence_level: number
  called_snps: number
  total_snps: number
  missing_snps: string[]
  pmids: string[]
  snp_details: SNPDetail[]
  hla_proxy_lookup: Record<string, unknown> | null
}
