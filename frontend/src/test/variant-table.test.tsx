import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor } from "./test-utils"
import userEvent from "@testing-library/user-event"
import VariantTable from "@/components/variant-table/VariantTable"
import type { VariantPage, VariantCount, ChromosomeSummary, ColumnPreset } from "@/types/variants"

// Mock fetch globally
const mockFetch = vi.fn()

const defaultPresets: ColumnPreset[] = [
  {
    name: "Clinical",
    columns: ["genotype", "gene_symbol", "consequence", "clinvar_significance", "clinvar_review_stars"],
    predefined: true,
  },
  {
    name: "Research",
    columns: [
      "genotype", "gene_symbol", "consequence", "clinvar_significance", "clinvar_review_stars",
      "cadd_phred", "sift_score", "sift_pred", "polyphen2_hsvar_score", "polyphen2_hsvar_pred",
      "revel", "ensemble_pathogenic",
    ],
    predefined: true,
  },
  {
    name: "Frequency",
    columns: ["genotype", "gene_symbol", "gnomad_af_global", "rare_flag"],
    predefined: true,
  },
  {
    name: "Scores",
    columns: [
      "gene_symbol", "consequence", "cadd_phred", "sift_score", "sift_pred",
      "polyphen2_hsvar_score", "polyphen2_hsvar_pred", "revel",
    ],
    predefined: true,
  },
]

function makeVariantPage(
  count: number,
  hasMore = false,
  startPos = 1000,
): VariantPage {
  return {
    items: Array.from({ length: count }, (_, i) => ({
      rsid: `rs${100 + i}`,
      chrom: "1",
      pos: startPos + i * 100,
      genotype: "AG",
      ref: "A",
      alt: "G",
      zygosity: "het",
      gene_symbol: i % 2 === 0 ? "BRCA1" : "TP53",
      consequence: "missense_variant",
      clinvar_significance: i === 0 ? "Pathogenic" : null,
      clinvar_review_stars: i === 0 ? 2 : null,
      gnomad_af_global: 0.001,
      rare_flag: true,
      cadd_phred: 25.5,
      sift_score: 0.01,
      sift_pred: "D",
      polyphen2_hsvar_score: 0.99,
      polyphen2_hsvar_pred: "D",
      revel: 0.85,
      annotation_coverage: 0b111111,
      evidence_conflict: i === 0,
      ensemble_pathogenic: i === 0,
    })),
    next_cursor_chrom: hasMore ? "1" : null,
    next_cursor_pos: hasMore ? startPos + count * 100 : null,
    has_more: hasMore,
    limit: 100,
  }
}

function makeCountResponse(total: number): VariantCount {
  return { total, filtered: false }
}

const defaultChromCounts: ChromosomeSummary[] = [
  { chrom: "1", count: 50000 },
  { chrom: "2", count: 45000 },
  { chrom: "3", count: 35000 },
  { chrom: "X", count: 10000 },
]

function setupFetchMock(
  page: VariantPage,
  count: VariantCount,
  chromCounts: ChromosomeSummary[] = defaultChromCounts,
  presets: ColumnPreset[] = defaultPresets,
) {
  mockFetch.mockImplementation(async (url: string) => {
    if (url.includes("/api/column-presets")) {
      return { ok: true, json: async () => ({ presets }) }
    }
    if (url.includes("/api/variants/chromosomes")) {
      return { ok: true, json: async () => chromCounts }
    }
    if (url.includes("/api/variants/count")) {
      return { ok: true, json: async () => count }
    }
    if (url.includes("/api/variants")) {
      return { ok: true, json: async () => page }
    }
    return { ok: false, status: 404 }
  })
}

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch)
  mockFetch.mockReset()
  // Reset URL params
  window.history.replaceState({}, "", window.location.pathname)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("VariantTable", () => {
  it("shows upload prompt when no sample selected", () => {
    render(<VariantTable sampleId={null} />)
    expect(screen.getByText("Upload a file to get started")).toBeInTheDocument()
  })

  it("renders variant rows from API", async () => {
    const page = makeVariantPage(3)
    setupFetchMock(page, makeCountResponse(3))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })
    expect(screen.getByText("rs101")).toBeInTheDocument()
    expect(screen.getByText("rs102")).toBeInTheDocument()
  })

  it("shows async total count", async () => {
    const page = makeVariantPage(5)
    setupFetchMock(page, makeCountResponse(12345))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("12,345 variants")).toBeInTheDocument()
    })
  })

  it("fires count query with annotation_coverage:notnull filter by default (P1-15d)", async () => {
    const page = makeVariantPage(3)
    setupFetchMock(page, makeCountResponse(3))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("3 variants")).toBeInTheDocument()
    })

    // Verify the count endpoint was called with annotation_coverage:notnull
    const countCalls = mockFetch.mock.calls
      .map((c) => c[0] as string)
      .filter((url) => url.includes("/api/variants/count"))
    expect(countCalls.length).toBeGreaterThan(0)
    expect(countCalls[0]).toContain("annotation_coverage%3Anotnull")
  })

  it("fires count query without annotation_coverage filter when showing unannotated (P1-15d)", async () => {
    const page = makeVariantPage(3)
    setupFetchMock(page, makeCountResponse(3))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })

    // Toggle unannotated on
    const toggle = screen.getByRole("button", { name: /show unannotated/i })
    await user.click(toggle)

    // After toggling, a new count call should fire without annotation_coverage filter
    await waitFor(() => {
      const countCalls = mockFetch.mock.calls
        .map((c) => c[0] as string)
        .filter((url) => url.includes("/api/variants/count"))
      const callsWithoutFilter = countCalls.filter(
        (url) => !url.includes("annotation_coverage"),
      )
      expect(callsWithoutFilter.length).toBeGreaterThan(0)
    })
  })

  it("displays conflict flag for conflicting variants", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("\u26A0")).toBeInTheDocument()
    })
  })

  it("shows error state on fetch failure", async () => {
    mockFetch.mockImplementation(async () => ({
      ok: false,
      status: 500,
      text: async () => "Internal Server Error",
    }))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("Error loading variants")).toBeInTheDocument()
    })
  })

  it("filters variants by search query (client-side)", async () => {
    const page = makeVariantPage(4)
    setupFetchMock(page, makeCountResponse(4))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText("Search rsid or gene...")
    await user.type(searchInput, "BRCA1")

    // BRCA1 genes are on even indices (rs100, rs102)
    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
      expect(screen.getByText("rs102")).toBeInTheDocument()
    })
    expect(screen.queryByText("rs101")).not.toBeInTheDocument()
    expect(screen.queryByText("rs103")).not.toBeInTheDocument()
  })

  it("has unannotated toggle button", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /show unannotated/i })).toBeInTheDocument()
    })
  })

  it("toggles unannotated visibility on button click", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    const toggle = await waitFor(() =>
      screen.getByRole("button", { name: /show unannotated/i }),
    )

    await user.click(toggle)
    expect(toggle).toHaveAttribute("aria-pressed", "true")

    await user.click(toggle)
    expect(toggle).toHaveAttribute("aria-pressed", "false")
  })

  it("renders table headers", async () => {
    const page = makeVariantPage(1)
    setupFetchMock(page, makeCountResponse(1))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rsID")).toBeInTheDocument()
    })
    // "Chr" appears in both the chromosome nav label and the table header
    expect(screen.getAllByText("Chr").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Position")).toBeInTheDocument()
    expect(screen.getByText("Genotype")).toBeInTheDocument()
    expect(screen.getByText("Gene")).toBeInTheDocument()
    expect(screen.getByText("Consequence")).toBeInTheDocument()
    expect(screen.getByText("ClinVar")).toBeInTheDocument()
  })

  it("shows empty state with clear suggestions when no results match", async () => {
    const page: VariantPage = {
      items: [
        {
          rsid: "rs999",
          chrom: "1",
          pos: 1000,
          genotype: "AG",
          ref: null,
          alt: null,
          zygosity: null,
          gene_symbol: null,
          consequence: null,
          clinvar_significance: null,
          clinvar_review_stars: null,
          gnomad_af_global: null,
          rare_flag: null,
          cadd_phred: null,
          sift_score: null,
          sift_pred: null,
          polyphen2_hsvar_score: null,
          polyphen2_hsvar_pred: null,
          revel: null,
          annotation_coverage: null,
          evidence_conflict: null,
          ensemble_pathogenic: null,
        },
      ],
      next_cursor_chrom: null,
      next_cursor_pos: null,
      has_more: false,
      limit: 100,
    }
    setupFetchMock(page, makeCountResponse(1))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("No variants match your filters")).toBeInTheDocument()
    })
    expect(screen.getByText("Show unannotated")).toBeInTheDocument()
  })

  it("shows ClinVar review stars correctly", async () => {
    const page = makeVariantPage(1)
    setupFetchMock(page, makeCountResponse(1))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      // 2 stars = ★★☆☆
      expect(screen.getByText("\u2605\u2605\u2606\u2606")).toBeInTheDocument()
    })
  })

  it("displays gnomAD AF in scientific notation for very small values", async () => {
    const page = makeVariantPage(1)
    // Override the gnomad_af_global to be very small
    page.items[0].gnomad_af_global = 0.00001
    setupFetchMock(page, makeCountResponse(1))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("1.00e-5")).toBeInTheDocument()
    })
  })
})

describe("VariantToolbar", () => {
  it("has search input with correct aria-label", async () => {
    const page = makeVariantPage(1)
    setupFetchMock(page, makeCountResponse(1))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "Search variants by rsid or gene" }),
      ).toBeInTheDocument()
    })
  })
})

describe("ChromosomeNav (P1-15b)", () => {
  it("renders chromosome navigation bar", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByRole("toolbar", { name: "Chromosome navigation" })).toBeInTheDocument()
    })
  })

  it("shows chromosome buttons with variant counts in title", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      const chr1Button = screen.getByRole("button", { name: /^jump to chromosome 1,/i })
      expect(chr1Button).toBeInTheDocument()
      expect(chr1Button).toHaveAttribute("title", "Chromosome 1: 50,000 variants")
    })
  })

  it("disables chromosomes with no data", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      // Chromosome 4 is not in our mock data, should be disabled
      const chr4Button = screen.getByRole("button", { name: /^jump to chromosome 4$/i })
      expect(chr4Button).toBeDisabled()
    })
  })

  it("highlights the active chromosome", async () => {
    const page = makeVariantPage(2) // all items on chrom "1"
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      const chr1Button = screen.getByRole("button", { name: /^jump to chromosome 1,/i })
      expect(chr1Button).toHaveAttribute("aria-current", "location")
    })
  })

  it("triggers chromosome jump on click", async () => {
    const page = makeVariantPage(3)
    setupFetchMock(page, makeCountResponse(3))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })

    // Click chromosome X to jump
    const chrXButton = screen.getByRole("button", { name: /^jump to chromosome x,/i })
    await user.click(chrXButton)

    // After clicking, the fetch should have been called with cursor params for chr X
    await waitFor(() => {
      const calls = mockFetch.mock.calls.map((c) => c[0] as string)
      const variantCalls = calls.filter(
        (url) => url.includes("/api/variants?") && !url.includes("count") && !url.includes("chromosomes"),
      )
      // Should have a call with cursor_chrom=X&cursor_pos=0
      const jumpCall = variantCalls.find(
        (url) => url.includes("cursor_chrom=X") && url.includes("cursor_pos=0"),
      )
      expect(jumpCall).toBeDefined()
    })
  })

  it("does not render chromosome nav when no sample selected", () => {
    render(<VariantTable sampleId={null} />)
    expect(screen.queryByRole("toolbar", { name: "Chromosome navigation" })).not.toBeInTheDocument()
  })
})

describe("ColumnPresets (P1-15c)", () => {
  it("renders preset selector in toolbar", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Column presets" })).toBeInTheDocument()
    })
    // Default label
    expect(screen.getByText("All Columns")).toBeInTheDocument()
  })

  it("opens dropdown with predefined presets", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Column presets" })).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: "Column presets" }))

    await waitFor(() => {
      expect(screen.getByRole("menu")).toBeInTheDocument()
    })
    expect(screen.getByRole("menuitem", { name: /Clinical/ })).toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: /Research/ })).toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: /Frequency/ })).toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: /Scores/ })).toBeInTheDocument()
  })

  it("switching preset hides non-preset columns", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })

    // CADD header should be visible initially (All Columns)
    expect(screen.getByText("CADD")).toBeInTheDocument()

    // Click preset button and select Clinical
    await user.click(screen.getByRole("button", { name: "Column presets" }))
    await waitFor(() => {
      expect(screen.getByRole("menu")).toBeInTheDocument()
    })
    await user.click(screen.getByRole("menuitem", { name: /Clinical/ }))

    // CADD should be hidden (not in Clinical preset)
    await waitFor(() => {
      expect(screen.queryByText("CADD")).not.toBeInTheDocument()
    })
    // Gene should still be visible (in Clinical preset)
    expect(screen.getByText("Gene")).toBeInTheDocument()
    // rsID always visible
    expect(screen.getByText("rsID")).toBeInTheDocument()
  })

  it("All Columns shows all columns after switching away and back", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })

    // Switch to Clinical (hides CADD)
    await user.click(screen.getByRole("button", { name: "Column presets" }))
    await waitFor(() => expect(screen.getByRole("menu")).toBeInTheDocument())
    await user.click(screen.getByRole("menuitem", { name: /Clinical/ }))

    await waitFor(() => {
      expect(screen.queryByText("CADD")).not.toBeInTheDocument()
    })

    // Switch back to All Columns
    await user.click(screen.getByRole("button", { name: "Column presets" }))
    await waitFor(() => expect(screen.getByRole("menu")).toBeInTheDocument())
    await user.click(screen.getByRole("menuitem", { name: /All Columns/ }))

    await waitFor(() => {
      expect(screen.getByText("CADD")).toBeInTheDocument()
    })
  })

  it("updates URL param when preset is selected", async () => {
    const page = makeVariantPage(2)
    setupFetchMock(page, makeCountResponse(2))

    const user = userEvent.setup()
    render(<VariantTable sampleId={1} />)

    await waitFor(() => {
      expect(screen.getByText("rs100")).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: "Column presets" }))
    await waitFor(() => expect(screen.getByRole("menu")).toBeInTheDocument())
    await user.click(screen.getByRole("menuitem", { name: /Frequency/ }))

    await waitFor(() => {
      const params = new URLSearchParams(window.location.search)
      expect(params.get("profile")).toBe("frequency")
    })
  })
})
