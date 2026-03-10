/** Shared filter suggestion definitions for the variant table (P1-15e). */

export const FILTER_SUGGESTIONS = [
  { label: "Pathogenic only", filter: "clinvar_significance:Pathogenic" },
  { label: "Rare variants", filter: "rare_flag:1" },
] as const

/** Human-readable label for a filter string. */
export function filterLabel(filter: string): string {
  return FILTER_SUGGESTIONS.find((s) => s.filter === filter)?.label ?? filter
}
