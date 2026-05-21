import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "./test-utils"
import SampleMetadataEditor from "@/components/settings/SampleMetadataEditor"

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

const SAMPLE_LIST = [
  {
    id: 1,
    name: "genome_a.txt",
    db_path: "samples/sample_1.db",
    file_format: "23andme_v5",
    file_hash: "abc",
    notes: null,
    date_collected: null,
    source: null,
    extra: null,
    created_at: "2025-06-01T00:00:00",
    updated_at: null,
  },
]

const SAMPLE_DETAIL = {
  ...SAMPLE_LIST[0],
  notes: "Test note",
  source: "23andMe",
  date_collected: "2025-01-15",
  extra: { ethnicity: "European" },
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    clone() {
      return this
    },
  } as unknown as Response
}

/** Returns a fetch implementation that routes /api/samples + /api/individuals
 * to the canned responses defined per-test, while keeping default no-op
 * responses for the individuals routes the assign-to-individual dropdown
 * (Step 51) added to SampleMetadataEditor. */
function makeRouter(handlers: {
  samples?: (init?: RequestInit) => Response | Promise<Response>
  sampleDetail?: (id: number, init?: RequestInit) => Response | Promise<Response>
}) {
  return (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString()
    const method = (init?.method ?? "GET").toUpperCase()
    if (url === "/api/samples" && method === "GET" && handlers.samples) {
      return Promise.resolve(handlers.samples(init))
    }
    const detailMatch = /^\/api\/samples\/(\d+)$/.exec(url)
    if (detailMatch && handlers.sampleDetail) {
      return Promise.resolve(
        handlers.sampleDetail(Number(detailMatch[1]), init),
      )
    }
    if (url === "/api/individuals" && method === "GET") {
      return Promise.resolve(jsonResponse([]))
    }
    if (/^\/api\/individuals\/\d+$/.test(url) && method === "GET") {
      return Promise.resolve(jsonResponse({ detail: "not found" }, 404))
    }
    return Promise.resolve(jsonResponse({ detail: "unhandled" }, 500))
  }
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe("SampleMetadataEditor", () => {
  it("shows empty state when no samples", async () => {
    mockFetch.mockImplementation(
      makeRouter({ samples: () => jsonResponse([]) }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("no-samples")).toBeInTheDocument()
    })
  })

  it("renders sample list with names", async () => {
    mockFetch.mockImplementation(
      makeRouter({ samples: () => jsonResponse(SAMPLE_LIST) }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByText("genome_a.txt")).toBeInTheDocument()
    })
  })

  it("expands edit form on edit button click", async () => {
    mockFetch.mockImplementation(
      makeRouter({
        samples: () => jsonResponse(SAMPLE_LIST),
        sampleDetail: () => jsonResponse(SAMPLE_DETAIL),
      }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-edit-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-edit-1"))

    await waitFor(() => {
      expect(screen.getByTestId("sample-edit-form")).toBeInTheDocument()
    })
  })

  it("shows delete confirmation dialog on delete click", async () => {
    mockFetch.mockImplementation(
      makeRouter({ samples: () => jsonResponse(SAMPLE_LIST) }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-delete-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-delete-1"))

    await waitFor(() => {
      expect(screen.getByTestId("delete-confirm-dialog")).toBeInTheDocument()
      expect(screen.getByTestId("delete-confirm-btn")).toBeInTheDocument()
    })
  })

  it("cancels delete when cancel button is clicked", async () => {
    mockFetch.mockImplementation(
      makeRouter({ samples: () => jsonResponse(SAMPLE_LIST) }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-delete-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-delete-1"))

    await waitFor(() => {
      expect(screen.getByTestId("delete-cancel-btn")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("delete-cancel-btn"))

    await waitFor(() => {
      expect(screen.queryByTestId("delete-confirm-dialog")).not.toBeInTheDocument()
    })
  })

  it("displays metadata fields in edit form", async () => {
    mockFetch.mockImplementation(
      makeRouter({
        samples: () => jsonResponse(SAMPLE_LIST),
        sampleDetail: () => jsonResponse(SAMPLE_DETAIL),
      }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-edit-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-edit-1"))

    await waitFor(() => {
      expect(screen.getByTestId("sample-name-input")).toHaveValue("genome_a.txt")
      expect(screen.getByTestId("sample-source-input")).toHaveValue("23andMe")
      expect(screen.getByTestId("sample-notes-input")).toHaveValue("Test note")
      expect(screen.getByTestId("sample-date-input")).toHaveValue("2025-01-15")
    })
  })

  it("save button is disabled when no changes", async () => {
    mockFetch.mockImplementation(
      makeRouter({
        samples: () => jsonResponse(SAMPLE_LIST),
        sampleDetail: () => jsonResponse(SAMPLE_DETAIL),
      }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-edit-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-edit-1"))

    await waitFor(() => {
      expect(screen.getByTestId("sample-save-btn")).toBeDisabled()
    })
  })

  it("calls update mutation with changed fields on save", async () => {
    mockFetch.mockImplementation(
      makeRouter({
        samples: () => jsonResponse(SAMPLE_LIST),
        sampleDetail: (_id, init) => {
          if ((init?.method ?? "GET").toUpperCase() === "PATCH") {
            return jsonResponse({ ...SAMPLE_DETAIL, notes: "Updated note" })
          }
          return jsonResponse(SAMPLE_DETAIL)
        },
      }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-edit-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-edit-1"))

    await waitFor(() => {
      expect(screen.getByTestId("sample-notes-input")).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId("sample-notes-input"), {
      target: { value: "Updated note" },
    })

    fireEvent.click(screen.getByTestId("sample-save-btn"))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/samples/1",
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("Updated note"),
        })
      )
    })
  })

  it("save button is enabled after making changes", async () => {
    mockFetch.mockImplementation(
      makeRouter({
        samples: () => jsonResponse(SAMPLE_LIST),
        sampleDetail: () => jsonResponse(SAMPLE_DETAIL),
      }),
    )

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("sample-edit-1")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("sample-edit-1"))

    await waitFor(() => {
      expect(screen.getByTestId("sample-notes-input")).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId("sample-notes-input"), {
      target: { value: "Updated note" },
    })

    expect(screen.getByTestId("sample-save-btn")).not.toBeDisabled()
  })
})
