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

beforeEach(() => {
  mockFetch.mockReset()
})

describe("SampleMetadataEditor", () => {
  it("shows empty state when no samples", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByTestId("no-samples")).toBeInTheDocument()
    })
  })

  it("renders sample list with names", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_LIST),
    })

    render(<SampleMetadataEditor />)
    await waitFor(() => {
      expect(screen.getByText("genome_a.txt")).toBeInTheDocument()
    })
  })

  it("expands edit form on edit button click", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_LIST),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_DETAIL),
      })

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
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_LIST),
    })

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
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_LIST),
    })

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
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_LIST),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_DETAIL),
      })

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
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_LIST),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_DETAIL),
      })

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
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_LIST),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_DETAIL),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ ...SAMPLE_DETAIL, notes: "Updated note" }),
      })
      // React Query invalidation re-fetches
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_LIST),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ ...SAMPLE_DETAIL, notes: "Updated note" }),
      })

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
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_LIST),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(SAMPLE_DETAIL),
      })

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
