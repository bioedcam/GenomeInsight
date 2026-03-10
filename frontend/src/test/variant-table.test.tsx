import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor } from "./test-utils"
import userEvent from "@testing-library/user-event"
import VariantTable from "@/components/variant-table/VariantTable"
import type { VariantPage, VariantCount } from "@/types/variants"

// Mock fetch globally
const mockFetch = vi.fn()

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

function setupFetchMock(page: VariantPage, count: VariantCount) {
  mockFetch.mockImplementation(async (url: string) => {
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
    expect(screen.getByText("Chr")).toBeInTheDocument()
    expect(screen.getByText("Position")).toBeInTheDocument()
    expect(screen.getByText("Genotype")).toBeInTheDocument()
    expect(screen.getByText("Gene")).toBeInTheDocument()
    expect(screen.getByText("Consequence")).toBeInTheDocument()
    expect(screen.getByText("ClinVar")).toBeInTheDocument()
  })

  it("shows empty state with clear suggestions when no results match", async () => {
    // Return variants that are all unannotated (annotation_coverage=null)
    // With showUnannotated=false (default), they'll be filtered out client-side
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
