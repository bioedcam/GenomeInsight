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

/** Per-chromosome variant count for the chromosome nav bar (P1-15b). */
export interface ChromosomeSummary {
  chrom: string
  count: number
}

/** Canonical chromosome list in display order. */
export const CHROMOSOMES = [
  "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
  "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
  "21", "22", "X", "Y", "MT",
] as const

export type Chromosome = (typeof CHROMOSOMES)[number]

/** Per-chromosome QC breakdown (P1-21). */
export interface ChromosomeQCStats {
  chrom: string
  total: number
  het_count: number
  hom_count: number
  nocall_count: number
}

/** Aggregate QC statistics for a sample (P1-21). */
export interface QCStats {
  total_variants: number
  called_variants: number
  nocall_variants: number
  het_count: number
  hom_count: number
  call_rate: number
  heterozygosity_rate: number
  per_chromosome: ChromosomeQCStats[]
}

/** Single genomic bin in the density histogram (P2-23). */
export interface DensityBin {
  chrom: string
  bin_start: number
  bin_end: number
  high: number
  moderate: number
  low: number
  modifier: number
  total: number
}

/** Variant density response (P2-23). */
export interface DensityResponse {
  bins: DensityBin[]
  bin_size: number
}

/** Column preset profile (P1-15c). */
export interface ColumnPreset {
  name: string
  columns: string[]
  predefined: boolean
}
