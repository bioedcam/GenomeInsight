/** TypeScript types for the unified findings API (P3-43). */

export interface Finding {
  id: number
  module: string
  category: string | null
  evidence_level: number | null
  gene_symbol: string | null
  rsid: string | null
  finding_text: string
  phenotype: string | null
  conditions: string | null
  zygosity: string | null
  clinvar_significance: string | null
  diplotype: string | null
  metabolizer_status: string | null
  drug: string | null
  haplogroup: string | null
  prs_score: number | null
  prs_percentile: number | null
  pathway: string | null
  pathway_level: string | null
  svg_path: string | null
  pmid_citations: string[]
  detail: Record<string, unknown> | null
  created_at: string | null
}

export interface FindingSummaryItem {
  module: string
  count: number
  max_evidence_level: number | null
  top_finding_text: string | null
}

export interface FindingsSummaryResponse {
  total_findings: number
  modules: FindingSummaryItem[]
  high_confidence_findings: Finding[]
}
