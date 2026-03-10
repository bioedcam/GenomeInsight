import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "./test-utils"
import FileUpload from "@/components/upload/FileUpload"

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
})

describe("FileUpload", () => {
  it("renders the drop zone in idle state", () => {
    render(<FileUpload />)
    expect(
      screen.getByText(/drop your 23andMe file here/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/upload 23andMe file/i)).toBeInTheDocument()
  })

  it("shows dragging state on dragover", () => {
    render(<FileUpload />)
    const dropZone = screen.getByRole("button")
    fireEvent.dragOver(dropZone)
    // The border color changes — component should still be visible
    expect(
      screen.getByText(/drop your 23andMe file here/i),
    ).toBeInTheDocument()
  })

  it("uploads file on drop and shows success", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          sample_id: 1,
          job_id: "abc-123",
          variant_count: 600000,
          nocall_count: 500,
          file_format: "23andme_v5",
        }),
    })

    render(<FileUpload />)
    const dropZone = screen.getByRole("button")
    const file = new File(["test content"], "genome.txt", {
      type: "text/plain",
    })
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    })

    // Should show parsing state
    await waitFor(() => {
      expect(screen.getByText(/parsing variants/i)).toBeInTheDocument()
    })

    // Should show success
    await waitFor(() => {
      expect(screen.getByText(/600,000 variants parsed/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/view variants/i)).toBeInTheDocument()
    expect(screen.getByText(/upload another/i)).toBeInTheDocument()
  })

  it("shows error state on upload failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      text: () => Promise.resolve('{"detail":"Not a valid 23andMe file"}'),
    })

    render(<FileUpload />)
    const dropZone = screen.getByRole("button")
    const file = new File(["bad"], "bad.txt", { type: "text/plain" })
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    })

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/try again/i)).toBeInTheDocument()
  })

  it("resets to idle after clicking try again", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Server error"),
    })

    render(<FileUpload />)
    const dropZone = screen.getByRole("button")
    const file = new File(["bad"], "bad.txt", { type: "text/plain" })
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    })

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText(/try again/i))
    expect(
      screen.getByText(/drop your 23andMe file here/i),
    ).toBeInTheDocument()
  })

  it("uploads file via file input click", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          sample_id: 2,
          job_id: "def-456",
          variant_count: 100000,
          nocall_count: 0,
          file_format: "23andme_v4",
        }),
    })

    render(<FileUpload />)
    const fileInput = screen.getByLabelText(/upload 23andMe file/i)
    const file = new File(["content"], "my_data.txt", { type: "text/plain" })
    fireEvent.change(fileInput, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByText(/100,000 variants parsed/i)).toBeInTheDocument()
    })
  })
})
