/** Export dropdown button (P4-05).
 *
 * Shows a dropdown menu of export formats. Triggers download on selection.
 */

import { useEffect, useRef, useState } from "react"
import { Download, Loader2 } from "lucide-react"

interface ExportButtonProps {
  formats: readonly string[]
  onExport: (format: string) => void
  disabled?: boolean
  isPending?: boolean
}

const FORMAT_LABELS: Record<string, string> = {
  vcf: "VCF",
  tsv: "TSV",
  json: "JSON",
  csv: "CSV",
}

export default function ExportButton({
  formats,
  onExport,
  disabled,
  isPending,
}: ExportButtonProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on outside click or Escape key
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", handleClick)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("mousedown", handleClick)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled || isPending}
        className="inline-flex items-center gap-2 rounded-md border border-input px-3 py-1.5 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="export-btn"
        aria-haspopup="true"
        aria-expanded={open}
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Download className="h-4 w-4" />
        )}
        Export
      </button>

      {open && (
        <div
          className="absolute right-0 mt-1 w-32 rounded-md border border-border bg-popover shadow-md z-20"
          role="menu"
          data-testid="export-menu"
        >
          {formats.map((fmt) => (
            <button
              key={fmt}
              type="button"
              role="menuitem"
              className="block w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors first:rounded-t-md last:rounded-b-md"
              onClick={() => {
                setOpen(false)
                onExport(fmt)
              }}
              data-testid={`export-${fmt}`}
            >
              {FORMAT_LABELS[fmt] || fmt.toUpperCase()}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
