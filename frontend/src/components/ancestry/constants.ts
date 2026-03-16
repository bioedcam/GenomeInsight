/** Ancestry module shared constants (P3-27). */

/** Population code → display label mapping. */
export const POPULATION_LABELS: Record<string, string> = {
  AFR: "African",
  AMR: "Admixed American",
  EAS: "East Asian",
  EUR: "European",
  SAS: "South Asian",
  OCE: "Oceanian",
}

/** Population code → color mapping for charts. */
export const POPULATION_COLORS: Record<string, string> = {
  AFR: "#F59E0B",  // amber-500
  AMR: "#EF4444",  // red-500
  EAS: "#10B981",  // emerald-500
  EUR: "#3B82F6",  // blue-500
  SAS: "#8B5CF6",  // violet-500
  OCE: "#EC4899",  // pink-500
}
