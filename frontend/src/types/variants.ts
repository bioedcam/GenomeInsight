/** Variant types matching backend Pydantic models (P1-14). */

export interface VariantRow {
  rsid: string
  chrom: string
  pos: number
  genotype: string
  ref: string | null
  alt: string | null
  zygosity: string | null
  gene_symbol: string | null
  consequence: string | null
  clinvar_significance: string | null
  clinvar_review_stars: number | null
  gnomad_af_global: number | null
  rare_flag: boolean | null
  cadd_phred: number | null
  sift_score: number | null
  sift_pred: string | null
  polyphen2_hsvar_score: number | null
  polyphen2_hsvar_pred: string | null
  revel: number | null
  annotation_coverage: number | null
  evidence_conflict: boolean | null
  ensemble_pathogenic: boolean | null
}

export interface VariantPage {
  items: VariantRow[]
  next_cursor_chrom: string | null
  next_cursor_pos: number | null
  has_more: boolean
  limit: number
}

export interface VariantCount {
  total: number
  filtered: boolean
}

/** Cursor used for keyset pagination. */
export interface VariantCursor {
  chrom: string
  pos: number
}
