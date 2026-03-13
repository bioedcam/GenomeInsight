/** Genomic locus pattern: chr1:12345-67890 or chr1:12345 or 1:12345-67890 */
const COORD_PATTERN = /^(chr)?\d{1,2}:\d[\d,]*([-–]\d[\d,]*)?$/i

/** rsid pattern: rs followed by digits */
const RSID_PATTERN = /^rs\d+$/i

/** Checks whether the query looks like it should navigate IGV */
export function isGenomicQuery(query: string): boolean {
  const q = query.trim()
  if (!q) return false
  if (RSID_PATTERN.test(q)) return true
  if (COORD_PATTERN.test(q)) return true
  // Gene symbols: 1-10 uppercase letters/digits (e.g., BRCA1, TP53, MTHFR, APOE)
  // Case-sensitive to avoid matching page names like "Settings" or "Dashboard"
  if (/^[A-Z][A-Z0-9]{0,9}$/.test(q) && !/^\d+$/.test(q)) return true
  return false
}
