/** Types for the query builder UI (P4-02). */

/** A single rule from react-querybuilder. */
export interface RuleModel {
  field: string
  operator: string
  value?: unknown
  disabled?: boolean
}

/** Recursive rule group from react-querybuilder (RuleGroupType). */
export interface RuleGroupModel {
  combinator: string
  rules: Array<RuleGroupModel | RuleModel>
  not?: boolean
}

/** POST /api/query request body. */
export interface QueryRequest {
  sample_id: number
  filter: RuleGroupModel
  cursor_chrom?: string | null
  cursor_pos?: number | null
  limit?: number
}

/** Single variant row in query results. */
export interface QueryVariantRow {
  rsid: string
  chrom: string
  pos: number
  genotype: string | null
  ref: string | null
  alt: string | null
  zygosity: string | null
  gene_symbol: string | null
  transcript_id: string | null
  consequence: string | null
  hgvs_coding: string | null
  hgvs_protein: string | null
  clinvar_significance: string | null
  clinvar_review_stars: number | null
  clinvar_accession: string | null
  clinvar_conditions: string | null
  gnomad_af_global: number | null
  gnomad_af_afr: number | null
  gnomad_af_amr: number | null
  gnomad_af_eas: number | null
  gnomad_af_eur: number | null
  gnomad_af_fin: number | null
  gnomad_af_sas: number | null
  rare_flag: boolean | null
  ultra_rare_flag: boolean | null
  cadd_phred: number | null
  sift_score: number | null
  sift_pred: string | null
  polyphen2_hsvar_score: number | null
  polyphen2_hsvar_pred: string | null
  revel: number | null
  annotation_coverage: number | null
  evidence_conflict: boolean | null
  ensemble_pathogenic: boolean | null
  disease_name: string | null
  inheritance_pattern: string | null
}

/** Paginated query result. */
export interface QueryResultPage {
  items: QueryVariantRow[]
  total_matching: number | null
  next_cursor_chrom: string | null
  next_cursor_pos: number | null
  has_more: boolean
  limit: number
}

/** Metadata about an allowed query field. */
export interface QueryFieldInfo {
  name: string
  type: string
  label: string
}

/** Response for GET /api/query/fields. */
export interface QueryMetaResponse {
  fields: QueryFieldInfo[]
  operators: string[]
}

/** A saved query entry. */
export interface SavedQuery {
  name: string
  filter: RuleGroupModel
  created_at: string
  updated_at: string
}

/** Response for GET /api/saved-queries. */
export interface SavedQueryListResponse {
  queries: SavedQuery[]
}
