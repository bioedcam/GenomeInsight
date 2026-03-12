/**
 * IGV.js React wrapper component (P2-16).
 *
 * Embeds an IGV.js genome browser configured for GRCh37 (hg19).
 * Uses useEffect + ref pattern to create/destroy the browser instance.
 */
import { useEffect, useRef, useReducer, forwardRef, useImperativeHandle } from "react"
import igv from "igv"
import type { Browser, BrowserOptions, TrackLoad, TrackType } from "igv"

// ── Public API ──────────────────────────────────────────────────────

export interface IgvBrowserHandle {
  /** Navigate to a locus (gene symbol, rsid, or coordinates like "chr17:41,196,312-41,277,500") */
  search: (query: string) => void
  /** Get the underlying IGV browser instance (for advanced usage) */
  getBrowser: () => Browser | null
}

export interface IgvBrowserProps {
  /** Initial locus to display (e.g., "all", "chr1", "BRCA1", "chr17:41196312-41277500") */
  locus?: string
  /** Additional tracks to load beyond defaults */
  tracks?: TrackLoad<TrackType>[]
  /** Callback when a variant is clicked in the browser */
  onVariantClick?: (variant: IgvVariantClickEvent) => void
  /** CSS class for the container div */
  className?: string
  /** Minimum height for the IGV container */
  minHeight?: number
}

export interface IgvVariantClickEvent {
  chr: string
  pos: number
  id: string
  ref: string
  alt: string
}

// ── Default GRCh37 configuration ────────────────────────────────────

const DEFAULT_GRCH37_OPTIONS: BrowserOptions = {
  genome: "hg19",
  locus: "all",
  showNavigation: true,
  showRuler: true,
  showCenterGuide: false,
  showCursorTrackingGuide: false,
  tracks: [],
}

// ── State reducer ───────────────────────────────────────────────────

type BrowserState =
  | { status: "loading" }
  | { status: "ready" }
  | { status: "error"; message: string }

type BrowserAction =
  | { type: "loading" }
  | { type: "ready" }
  | { type: "error"; message: string }

function browserReducer(_state: BrowserState, action: BrowserAction): BrowserState {
  switch (action.type) {
    case "loading":
      return { status: "loading" }
    case "ready":
      return { status: "ready" }
    case "error":
      return { status: "error", message: action.message }
  }
}

// ── Component ───────────────────────────────────────────────────────

const IgvBrowser = forwardRef<IgvBrowserHandle, IgvBrowserProps>(
  function IgvBrowser(
    { locus = "all", tracks = [], onVariantClick, className, minHeight = 500 },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null)
    const browserRef = useRef<Browser | null>(null)
    const [state, dispatch] = useReducer(browserReducer, { status: "loading" })
    // Track retry requests — incrementing forces the effect to re-run
    const retryCountRef = useRef(0)
    const [retryCount, setRetryCount] = useReducer((c: number) => c + 1, 0)

    // Expose imperative handle for parent components
    useImperativeHandle(ref, () => ({
      search: (query: string) => {
        browserRef.current?.search(query)
      },
      getBrowser: () => browserRef.current,
    }))

    // Stable onVariantClick ref to avoid recreating browser on callback change
    const onVariantClickRef = useRef(onVariantClick)
    useEffect(() => {
      onVariantClickRef.current = onVariantClick
    }, [onVariantClick])

    // Initialize browser on mount (and on retry), destroy on unmount
    useEffect(() => {
      if (!containerRef.current) return

      let cancelled = false

      // Clean up any existing browser in this container
      if (browserRef.current) {
        igv.removeBrowser(browserRef.current)
        browserRef.current = null
      }

      dispatch({ type: "loading" })

      const options: BrowserOptions = {
        ...DEFAULT_GRCH37_OPTIONS,
        locus,
        tracks: [...tracks],
      }

      igv
        .createBrowser(containerRef.current, options)
        .then((browser) => {
          if (cancelled) {
            igv.removeBrowser(browser)
            return
          }

          browserRef.current = browser

          // Register variant click handler if provided
          browser.on("trackclick", (track, popoverData) => {
            if (!onVariantClickRef.current) return undefined

            // Extract variant info from IGV click data
            if (track?.config?.type === "variant" && popoverData) {
              const fields = Array.isArray(popoverData) ? popoverData : []
              const getName = (name: string) =>
                fields.find(
                  (f: { name: string; value: string }) =>
                    f.name?.toLowerCase() === name.toLowerCase(),
                )?.value

              const chr = getName("Chr") ?? getName("Chromosome") ?? ""
              const pos = parseInt(getName("Pos") ?? getName("Position") ?? "0", 10)
              const id = getName("ID") ?? getName("Names") ?? ""
              const refAllele = getName("Ref") ?? ""
              const alt = getName("Alt") ?? ""

              onVariantClickRef.current({
                chr,
                pos,
                id,
                ref: refAllele,
                alt,
              })

              // Return false to suppress default IGV popover when we handle it
              return false
            }

            // Let IGV handle non-variant track clicks with default popover
            return undefined
          })

          dispatch({ type: "ready" })
        })
        .catch((err: unknown) => {
          if (cancelled) return
          const message =
            err instanceof Error ? err.message : "Failed to initialize IGV browser"
          dispatch({ type: "error", message })
        })

      return () => {
        cancelled = true
        if (browserRef.current) {
          igv.removeBrowser(browserRef.current)
          browserRef.current = null
        }
      }
      // retryCount forces re-initialization on retry click
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [locus, retryCount])

    // Keep retryCountRef in sync for the retry handler
    retryCountRef.current = retryCount

    return (
      <div className={className}>
        {state.status === "loading" && (
          <div
            className="flex items-center justify-center py-12 text-muted-foreground"
            role="status"
            aria-label="Loading genome browser"
          >
            <svg
              className="animate-spin h-5 w-5 mr-2"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Loading genome browser…
          </div>
        )}
        {state.status === "error" && (
          <div
            className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-destructive text-sm"
            role="alert"
          >
            <p className="font-medium">Failed to load genome browser</p>
            <p className="mt-1">{state.message}</p>
            <button
              type="button"
              onClick={setRetryCount}
              className="mt-2 text-xs underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        )}
        <div
          ref={containerRef}
          data-testid="igv-container"
          style={{ minHeight: state.status === "loading" ? 0 : minHeight }}
        />
      </div>
    )
  },
)

export default IgvBrowser
