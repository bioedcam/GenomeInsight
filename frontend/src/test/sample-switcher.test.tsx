import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "./test-utils"
import SampleSwitcher from "@/components/layout/SampleSwitcher"

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
})

describe("SampleSwitcher", () => {
  it("shows 'No sample loaded' when no samples exist", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<SampleSwitcher />)
    await waitFor(() => {
      expect(screen.getByText("No sample loaded")).toBeInTheDocument()
    })
  })

  it("shows loading state initially", () => {
    mockFetch.mockReturnValueOnce(new Promise(() => {})) // Never resolves
    render(<SampleSwitcher />)
    expect(screen.getByText("Loading...")).toBeInTheDocument()
  })

  it("renders sample selector button when samples exist", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: 1,
            name: "test_genome.txt",
            db_path: "samples/sample_1.db",
            file_format: "23andme_v5",
            file_hash: "abc",
            created_at: "2025-01-01T00:00:00",
            updated_at: null,
          },
          {
            id: 2,
            name: "second_sample.txt",
            db_path: "samples/sample_2.db",
            file_format: "23andme_v4",
            file_hash: "def",
            created_at: "2025-01-02T00:00:00",
            updated_at: null,
          },
        ]),
    })

    render(<SampleSwitcher />)
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /switch sample/i }),
      ).toBeInTheDocument()
    })
  })

  it("opens dropdown and shows sample list on click", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: 1,
            name: "genome_a.txt",
            db_path: "samples/sample_1.db",
            file_format: "23andme_v5",
            file_hash: "abc",
            created_at: "2025-06-01T00:00:00",
            updated_at: null,
          },
          {
            id: 2,
            name: "genome_b.txt",
            db_path: "samples/sample_2.db",
            file_format: "23andme_v3",
            file_hash: "def",
            created_at: "2025-06-02T00:00:00",
            updated_at: null,
          },
        ]),
    })

    render(<SampleSwitcher />)
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /switch sample/i }),
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: /switch sample/i }))

    await waitFor(() => {
      expect(screen.getByText("genome_a.txt")).toBeInTheDocument()
      expect(screen.getByText("genome_b.txt")).toBeInTheDocument()
    })
  })
})
