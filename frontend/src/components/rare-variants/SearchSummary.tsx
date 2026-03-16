/** Search result summary stats bar (P3-30).
 *
 * Shows total found, variants scanned, novel count, pathogenic count,
 * genes with findings, and export buttons.
 */

import { Download } from "lucide-react"
import { formatNumber } from "@/lib/format"

interface SearchSummaryProps {
  total: number
  totalScanned: number
  novelCount: number
  pathogenicCount: number
  genesWithFindings: string[]
  sampleId: number
}

export default function SearchSummary({
  total,
  totalScanned,
  novelCount,
  pathogenicCount,
  genesWithFindings,
  sampleId,
}: SearchSummaryProps) {
  return (
    <div
      className="rounded-lg border bg-card p-4"
      data-testid="search-summary"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Stats */}
        <div className="flex flex-wrap gap-6">
          <div>
            <p className="text-2xl font-bold" data-testid="total-found">{formatNumber(total)}</p>
            <p className="text-xs text-muted-foreground">Variants found</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{formatNumber(totalScanned)}</p>
            <p className="text-xs text-muted-foreground">Total scanned</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">{formatNumber(pathogenicCount)}</p>
            <p className="text-xs text-muted-foreground">Pathogenic</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatNumber(novelCount)}</p>
            <p className="text-xs text-muted-foreground">Novel</p>
          </div>
          {genesWithFindings.length > 0 && (
            <div>
              <p className="text-2xl font-bold">{genesWithFindings.length}</p>
              <p className="text-xs text-muted-foreground">Genes affected</p>
            </div>
          )}
        </div>

        {/* Export buttons */}
        <div className="flex gap-2" data-testid="export-buttons">
          <a
            href={`/api/analysis/rare-variants/export/tsv?sample_id=${sampleId}`}
            download
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
            data-testid="export-tsv"
          >
            <Download className="h-3.5 w-3.5" />
            TSV
          </a>
          <a
            href={`/api/analysis/rare-variants/export/vcf?sample_id=${sampleId}`}
            download
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
            data-testid="export-vcf"
          >
            <Download className="h-3.5 w-3.5" />
            VCF
          </a>
        </div>
      </div>

      {/* Genes list */}
      {genesWithFindings.length > 0 && (
        <div className="mt-3 pt-3 border-t">
          <p className="text-xs text-muted-foreground mb-1.5">Genes with findings</p>
          <div className="flex flex-wrap gap-1">
            {genesWithFindings.map((gene) => (
              <span
                key={gene}
                className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-mono"
              >
                {gene}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
