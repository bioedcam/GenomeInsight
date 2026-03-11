/** Shared formatting utilities (P1-16). */

/** Format a raw file_format string (e.g. "23andme_v5") for display. */
export function formatFileFormat(fileFormat: string | null | undefined): string {
  if (!fileFormat) return "Unknown format"
  return fileFormat.replace("23andme_", "23andMe ").toUpperCase()
}

/** Parse a numeric query param safely, returning null for invalid values. */
export function parseSampleId(raw: string | null): number | null {
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

/** Format a number with locale-appropriate separators (e.g. 623841 → "623,841"). */
export function formatNumber(n: number): string {
  return n.toLocaleString()
}
