/** Rare variant finder filter controls (P3-30).
 *
 * Gene panel textarea, AF threshold slider, consequence multi-select,
 * ClinVar significance multi-select, novel toggle, zygosity select.
 */

import { useState } from "react"
import { Search, Upload, RotateCcw } from "lucide-react"
import type { RareVariantFilterRequest } from "@/types/rare-variants"

/** Default AF threshold (1%) matching backend DEFAULT_AF_THRESHOLD. */
const DEFAULT_AF_THRESHOLD = 0.01

const CONSEQUENCE_OPTIONS = [
  "frameshift_variant",
  "stop_gained",
  "splice_donor_variant",
  "splice_acceptor_variant",
  "missense_variant",
  "start_lost",
  "stop_lost",
  "inframe_insertion",
  "inframe_deletion",
] as const

const CLINVAR_OPTIONS = [
  "Pathogenic",
  "Likely pathogenic",
  "Uncertain significance",
  "Likely benign",
  "Benign",
] as const

interface FilterPanelProps {
  onSearch: (filters: RareVariantFilterRequest) => void
  isSearching: boolean
}

export default function FilterPanel({ onSearch, isSearching }: FilterPanelProps) {
  const [geneText, setGeneText] = useState("")
  const [afThreshold, setAfThreshold] = useState(DEFAULT_AF_THRESHOLD)
  const [selectedConsequences, setSelectedConsequences] = useState<string[]>([])
  const [selectedClinvar, setSelectedClinvar] = useState<string[]>([])
  const [includeNovel, setIncludeNovel] = useState(true)
  const [zygosity, setZygosity] = useState<string | null>(null)

  function handleGeneFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const text = reader.result as string
      // Parse gene symbols: one per line or comma-separated
      const genes = text
        .split(/[\n,]+/)
        .map((g) => g.trim().toUpperCase())
        .filter(Boolean)
      setGeneText(genes.join("\n"))
    }
    reader.readAsText(file)
    // Reset input so re-uploading same file works
    e.target.value = ""
  }

  function handleReset() {
    setGeneText("")
    setAfThreshold(DEFAULT_AF_THRESHOLD)
    setSelectedConsequences([])
    setSelectedClinvar([])
    setIncludeNovel(true)
    setZygosity(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const geneSymbols = geneText
      .split(/[\n,]+/)
      .map((g) => g.trim().toUpperCase())
      .filter(Boolean)

    onSearch({
      gene_symbols: geneSymbols.length > 0 ? geneSymbols : null,
      af_threshold: afThreshold,
      consequences: selectedConsequences.length > 0 ? selectedConsequences : null,
      clinvar_significance: selectedClinvar.length > 0 ? selectedClinvar : null,
      include_novel: includeNovel,
      zygosity,
    })
  }

  function toggleConsequence(value: string) {
    setSelectedConsequences((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
    )
  }

  function toggleClinvar(value: string) {
    setSelectedClinvar((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border bg-card p-5 space-y-5"
      data-testid="rare-variant-filter-panel"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Search Filters</h2>
        <button
          type="button"
          onClick={handleReset}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Reset filters"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </button>
      </div>

      {/* Gene panel */}
      <div>
        <label htmlFor="gene-panel" className="block text-sm font-medium mb-1.5">
          Gene Panel
          <span className="text-muted-foreground font-normal ml-1">(optional)</span>
        </label>
        <div className="flex gap-2">
          <textarea
            id="gene-panel"
            value={geneText}
            onChange={(e) => setGeneText(e.target.value)}
            placeholder="Enter gene symbols (one per line or comma-separated)&#10;e.g. BRCA1, BRCA2, TP53"
            rows={3}
            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
            data-testid="gene-panel-input"
          />
          <div className="flex flex-col gap-1">
            <label
              className="inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-xs cursor-pointer hover:bg-muted transition-colors"
              title="Upload gene list file (.txt, .csv)"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload
              <input
                type="file"
                accept=".txt,.csv,.tsv"
                onChange={handleGeneFileUpload}
                className="sr-only"
                data-testid="gene-panel-upload"
              />
            </label>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Leave empty to search all genes
        </p>
      </div>

      {/* AF threshold */}
      <div>
        <label htmlFor="af-threshold" className="block text-sm font-medium mb-1.5">
          Max Allele Frequency
        </label>
        <div className="flex items-center gap-3">
          <input
            id="af-threshold"
            type="range"
            min={0}
            max={0.05}
            step={0.001}
            value={afThreshold}
            onChange={(e) => setAfThreshold(Number(e.target.value))}
            className="flex-1"
            data-testid="af-threshold-slider"
          />
          <span className="text-sm font-mono w-16 text-right" data-testid="af-threshold-value">
            {(afThreshold * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Consequence filter */}
      <div>
        <span className="block text-sm font-medium mb-1.5">Consequence Types</span>
        <div className="flex flex-wrap gap-1.5" data-testid="consequence-filter">
          {CONSEQUENCE_OPTIONS.map((csq) => (
            <button
              key={csq}
              type="button"
              onClick={() => toggleConsequence(csq)}
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                selectedConsequences.includes(csq)
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
              aria-pressed={selectedConsequences.includes(csq)}
            >
              {csq.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      {/* ClinVar significance filter */}
      <div>
        <span className="block text-sm font-medium mb-1.5">ClinVar Significance</span>
        <div className="flex flex-wrap gap-1.5" data-testid="clinvar-filter">
          {CLINVAR_OPTIONS.map((sig) => (
            <button
              key={sig}
              type="button"
              onClick={() => toggleClinvar(sig)}
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                selectedClinvar.includes(sig)
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
              aria-pressed={selectedClinvar.includes(sig)}
            >
              {sig}
            </button>
          ))}
        </div>
      </div>

      {/* Bottom row: novel toggle + zygosity + search button */}
      <div className="flex flex-wrap items-end gap-4 pt-2">
        {/* Include novel */}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeNovel}
            onChange={(e) => setIncludeNovel(e.target.checked)}
            className="rounded border-input"
            data-testid="include-novel-checkbox"
          />
          Include novel variants
        </label>

        {/* Zygosity */}
        <div className="flex items-center gap-2">
          <label htmlFor="zygosity-select" className="text-sm">
            Zygosity
          </label>
          <select
            id="zygosity-select"
            value={zygosity ?? ""}
            onChange={(e) => setZygosity(e.target.value || null)}
            className="rounded-md border bg-background px-2 py-1 text-sm"
            data-testid="zygosity-select"
          >
            <option value="">Any</option>
            <option value="het">Heterozygous</option>
            <option value="hom_alt">Homozygous</option>
          </select>
        </div>

        {/* Search button */}
        <button
          type="submit"
          disabled={isSearching}
          className="ml-auto inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          data-testid="search-button"
        >
          <Search className="h-4 w-4" />
          {isSearching ? "Searching..." : "Search"}
        </button>
      </div>
    </form>
  )
}
