/**
 * Genome Browser page (P2-16).
 *
 * Full-page IGV.js browser with GRCh37 reference.
 * Supports navigation via URL search params (?locus=BRCA1).
 */
import { useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { IgvBrowser } from "@/components/igv-browser"
import type { IgvBrowserHandle, IgvVariantClickEvent } from "@/components/igv-browser"

export default function GenomeBrowser() {
  const [searchParams] = useSearchParams()
  const locusParam = searchParams.get("locus") ?? "all"
  const browserRef = useRef<IgvBrowserHandle>(null)

  const handleVariantClick = (variant: IgvVariantClickEvent) => {
    // Future: open variant detail side panel (P2-18)
    console.log("Variant clicked:", variant)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-40px)]">
      <div className="px-4 py-3 border-b border-border">
        <h1 className="text-xl font-semibold">Genome Browser</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Interactive genome visualization — GRCh37/hg19
        </p>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <IgvBrowser
          ref={browserRef}
          locus={locusParam}
          onVariantClick={handleVariantClick}
          className="rounded-md border border-border overflow-hidden"
          minHeight={600}
        />
      </div>
    </div>
  )
}
