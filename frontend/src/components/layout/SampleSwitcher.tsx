/** Sample switcher dropdown in the top nav bar (P1-16).
 *
 * Reads `?sample_id=` from the URL search params, shows a dropdown
 * of all loaded samples, and navigates on selection.
 */

import { useState, useRef, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { ChevronDown, FlaskConical, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatFileFormat, parseSampleId } from "@/lib/format"
import { useSamples } from "@/api/samples"

export default function SampleSwitcher() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeSampleId = parseSampleId(searchParams.get("sample_id"))

  const { data: samples, isLoading } = useSamples()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close dropdown on click outside
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open])

  if (isLoading) {
    return (
      <span className="text-sm text-muted-foreground hidden sm:block">
        Loading...
      </span>
    )
  }

  if (!samples || samples.length === 0) {
    return (
      <span className="text-sm text-muted-foreground hidden sm:block">
        No sample loaded
      </span>
    )
  }

  const activeSample = samples.find((s) => s.id === activeSampleId)
  const label = activeSample?.name ?? "Select sample"

  const selectSample = (sampleId: number) => {
    const params = new URLSearchParams(searchParams)
    params.set("sample_id", String(sampleId))
    setSearchParams(params)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative hidden sm:block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-2 text-sm border border-input rounded-md px-3 py-1.5",
          "hover:bg-accent hover:text-accent-foreground transition-colors",
          "max-w-[220px]",
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Switch sample"
      >
        <FlaskConical className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="truncate">{label}</span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div
          className="absolute top-full right-0 mt-1 w-64 bg-popover border border-border rounded-md shadow-md z-50 py-1 max-h-60 overflow-y-auto"
          role="listbox"
          aria-label="Samples"
        >
          {samples.map((sample) => (
            <button
              key={sample.id}
              type="button"
              role="option"
              aria-selected={sample.id === activeSampleId}
              onClick={() => selectSample(sample.id)}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 text-sm text-left",
                "hover:bg-accent hover:text-accent-foreground transition-colors",
                sample.id === activeSampleId && "bg-accent/50",
              )}
            >
              <Check
                className={cn(
                  "h-3.5 w-3.5 shrink-0",
                  sample.id === activeSampleId
                    ? "text-primary"
                    : "text-transparent",
                )}
              />
              <div className="flex-1 min-w-0">
                <div className="truncate font-medium">{sample.name}</div>
                <div className="text-xs text-muted-foreground">
                  {formatFileFormat(sample.file_format)}
                  {sample.created_at && (
                    <>
                      {" · "}
                      {new Date(sample.created_at).toLocaleDateString()}
                    </>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
