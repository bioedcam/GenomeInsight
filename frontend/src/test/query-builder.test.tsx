import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "./test-utils"
import userEvent from "@testing-library/user-event"
import QueryBuilderView from "@/pages/QueryBuilderView"
import SavedQueriesPanel from "@/components/query-builder/SavedQueriesPanel"
import QueryResultsTable from "@/components/query-builder/QueryResultsTable"
import type { QueryResultPage, RuleGroupModel } from "@/types/query-builder"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render as rtlRender } from "@testing-library/react"
import type { ReactNode } from "react"

const mockFetch = vi.fn()

function renderWithRoute(ui: ReactNode, route = "/query-builder") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  return rtlRender(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

// Mock field metadata response
const MOCK_FIELDS = {
  fields: [
    { name: "rsid", type: "text", label: "Rsid" },
    { name: "chrom", type: "text", label: "Chrom" },
    { name: "pos", type: "integer", label: "Pos" },
    { name: "clinvar_significance", type: "text", label: "Clinvar Significance" },
    { name: "gnomad_af_global", type: "number", label: "Gnomad Af Global" },
    { name: "rare_flag", type: "boolean", label: "Rare Flag" },
  ],
  operators: ["=", "!=", "<", ">", "<=", ">=", "beginsWith", "between", "contains", "endsWith", "in", "notIn", "notNull", "null"],
}

// Mock query result
const MOCK_RESULT: QueryResultPage = {
  items: [
    {
      rsid: "rs429358",
      chrom: "19",
      pos: 44908684,
      genotype: "TC",
      ref: "T",
      alt: "C",
      zygosity: "het",
      gene_symbol: "APOE",
      transcript_id: null,
      consequence: "missense_variant",
      hgvs_coding: null,
      hgvs_protein: null,
      clinvar_significance: "risk_factor",
      clinvar_review_stars: 3,
      clinvar_accession: "VCV000017864",
      clinvar_conditions: "Alzheimer disease",
      gnomad_af_global: 0.15,
      gnomad_af_afr: null,
      gnomad_af_amr: null,
      gnomad_af_eas: null,
      gnomad_af_eur: null,
      gnomad_af_fin: null,
      gnomad_af_sas: null,
      rare_flag: false,
      ultra_rare_flag: false,
      cadd_phred: 25.3,
      sift_score: null,
      sift_pred: null,
      polyphen2_hsvar_score: null,
      polyphen2_hsvar_pred: null,
      revel: 0.45,
      annotation_coverage: 63,
      evidence_conflict: false,
      ensemble_pathogenic: false,
      disease_name: "Alzheimer disease",
      inheritance_pattern: null,
    },
  ],
  total_matching: 1,
  next_cursor_chrom: null,
  next_cursor_pos: null,
  has_more: false,
  limit: 50,
}

beforeEach(() => {
  mockFetch.mockReset()
  vi.stubGlobal("fetch", mockFetch)
})

describe("QueryBuilderView", () => {
  it("shows empty state when no sample selected", () => {
    renderWithRoute(<QueryBuilderView />)
    expect(screen.getByText(/select a sample/i)).toBeInTheDocument()
  })

  it("loads and renders query builder when sample selected", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/query/fields")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_FIELDS),
          text: () => Promise.resolve(""),
        })
      }
      if (url.includes("/api/saved-queries")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ queries: [] }),
          text: () => Promise.resolve(""),
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    })

    renderWithRoute(<QueryBuilderView />, "/query-builder?sample_id=1")

    await waitFor(() => {
      expect(screen.getByTestId("query-builder-panel")).toBeInTheDocument()
    })
    expect(screen.getByTestId("run-query-btn")).toBeInTheDocument()
    expect(screen.getByTestId("clear-query-btn")).toBeInTheDocument()
  })

  it("disables Run button when no rules", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/query/fields")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_FIELDS),
          text: () => Promise.resolve(""),
        })
      }
      if (url.includes("/api/saved-queries")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ queries: [] }),
          text: () => Promise.resolve(""),
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    })

    renderWithRoute(<QueryBuilderView />, "/query-builder?sample_id=1")

    await waitFor(() => {
      expect(screen.getByTestId("run-query-btn")).toBeInTheDocument()
    })
    expect(screen.getByTestId("run-query-btn")).toBeDisabled()
  })
})

describe("QueryResultsTable", () => {
  it("renders results with variant data", () => {
    render(
      <QueryResultsTable
        pages={[MOCK_RESULT]}
        totalMatching={1}
        hasMore={false}
        isFetchingMore={false}
        onLoadMore={vi.fn()}
      />,
    )
    expect(screen.getByTestId("query-results-table")).toBeInTheDocument()
    expect(screen.getByTestId("query-result-row")).toBeInTheDocument()
    expect(screen.getByText("rs429358")).toBeInTheDocument()
    expect(screen.getByText("APOE")).toBeInTheDocument()
  })

  it("shows empty message when no results", () => {
    const emptyResult: QueryResultPage = {
      items: [],
      total_matching: 0,
      next_cursor_chrom: null,
      next_cursor_pos: null,
      has_more: false,
      limit: 50,
    }
    render(
      <QueryResultsTable
        pages={[emptyResult]}
        totalMatching={0}
        hasMore={false}
        isFetchingMore={false}
        onLoadMore={vi.fn()}
      />,
    )
    expect(screen.getByText(/no variants match/i)).toBeInTheDocument()
  })

  it("shows load more button when has_more", () => {
    const pageWithMore: QueryResultPage = {
      ...MOCK_RESULT,
      has_more: true,
      next_cursor_chrom: "19",
      next_cursor_pos: 44908684,
    }
    render(
      <QueryResultsTable
        pages={[pageWithMore]}
        totalMatching={100}
        hasMore={true}
        isFetchingMore={false}
        onLoadMore={vi.fn()}
      />,
    )
    expect(screen.getByTestId("load-more-btn")).toBeInTheDocument()
  })

  it("does not show load more when no more pages", () => {
    render(
      <QueryResultsTable
        pages={[MOCK_RESULT]}
        totalMatching={1}
        hasMore={false}
        isFetchingMore={false}
        onLoadMore={vi.fn()}
      />,
    )
    expect(screen.queryByTestId("load-more-btn")).not.toBeInTheDocument()
  })
})

describe("SavedQueriesPanel", () => {
  const emptyFilter: RuleGroupModel = { combinator: "and", rules: [] }
  const filterWithRules: RuleGroupModel = {
    combinator: "and",
    rules: [{ field: "chrom", operator: "=", value: "1" }],
  }

  it("shows empty state initially", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ queries: [] }),
      text: () => Promise.resolve(""),
    })

    render(<SavedQueriesPanel currentFilter={emptyFilter} onLoad={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/no saved queries/i)).toBeInTheDocument()
    })
  })

  it("disables save button when no rules", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ queries: [] }),
      text: () => Promise.resolve(""),
    })

    render(<SavedQueriesPanel currentFilter={emptyFilter} onLoad={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByTestId("save-query-btn")).toBeDisabled()
    })
  })

  it("enables save button when filter has rules", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ queries: [] }),
      text: () => Promise.resolve(""),
    })

    render(<SavedQueriesPanel currentFilter={filterWithRules} onLoad={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByTestId("save-query-btn")).not.toBeDisabled()
    })
  })

  it("renders saved queries list", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          queries: [
            {
              name: "My Query",
              filter: { combinator: "and", rules: [{ field: "chrom", operator: "=", value: "1" }] },
              created_at: "2026-03-01T00:00:00Z",
              updated_at: "2026-03-01T00:00:00Z",
            },
          ],
        }),
      text: () => Promise.resolve(""),
    })

    render(<SavedQueriesPanel currentFilter={emptyFilter} onLoad={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText("My Query")).toBeInTheDocument()
    })
    expect(screen.getByText(/1 rule/)).toBeInTheDocument()
  })

  it("calls onLoad when clicking a saved query", async () => {
    const savedQuery = {
      name: "Clickable",
      filter: { combinator: "and", rules: [{ field: "chrom", operator: "=", value: "X" }] },
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    }
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ queries: [savedQuery] }),
      text: () => Promise.resolve(""),
    })

    const onLoad = vi.fn()
    render(<SavedQueriesPanel currentFilter={emptyFilter} onLoad={onLoad} />)

    await waitFor(() => {
      expect(screen.getByTestId("load-query-btn")).toBeInTheDocument()
    })

    const user = userEvent.setup()
    await user.click(screen.getByTestId("load-query-btn"))
    expect(onLoad).toHaveBeenCalledWith(savedQuery)
  })
})
