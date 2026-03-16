/** Ancestry module API types (P3-27). */

/** Distance to a reference population centroid. */
export interface PopulationDistance {
  population: string
  distance: number
}

/** Ancestry inference finding response. */
export interface AncestryFindingResponse {
  top_population: string
  pc_scores: number[]
  population_distances: Record<string, number>
  admixture_fractions: Record<string, number>
  population_ranking: PopulationDistance[]
  snps_used: number
  snps_total: number
  coverage_fraction: number
  projection_time_ms: number
  is_sufficient: boolean
  evidence_level: number
  finding_text: string
}

/** PCA coordinates for scatter plot visualization (P3-25). */
export interface PCACoordinatesResponse {
  user: number[]
  reference_samples: Record<string, number[][]>
  centroids: Record<string, number[]>
  population_labels: Record<string, string>
  n_components: number
  pc_labels: string[]
  top_population: string
}
