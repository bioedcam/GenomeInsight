/** Tests for NuclearDelete component (P4-21). */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "./test-utils"
import NuclearDelete from "@/components/settings/NuclearDelete"

// Mock fetch globally
const mockFetch = vi.fn()
beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch)
  mockFetch.mockReset()
})

describe("NuclearDelete", () => {
  it("renders the trigger button initially", () => {
    render(<NuclearDelete />)
    expect(screen.getByTestId("nuclear-delete-trigger")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Delete All Data/ })).toBeInTheDocument()
  })

  it("does not show confirmation dialog initially", () => {
    render(<NuclearDelete />)
    expect(screen.queryByTestId("nuclear-confirm-input")).not.toBeInTheDocument()
  })

  it("shows confirmation dialog when trigger is clicked", () => {
    render(<NuclearDelete />)
    fireEvent.click(screen.getByTestId("nuclear-delete-trigger"))
    expect(screen.getByTestId("nuclear-confirm-input")).toBeInTheDocument()
    expect(screen.getByTestId("nuclear-delete-confirm")).toBeInTheDocument()
    expect(screen.getByTestId("nuclear-delete-cancel")).toBeInTheDocument()
  })

  it("keeps delete button disabled until confirmation phrase is typed", () => {
    render(<NuclearDelete />)
    fireEvent.click(screen.getByTestId("nuclear-delete-trigger"))

    const confirmBtn = screen.getByTestId("nuclear-delete-confirm")
    expect(confirmBtn).toBeDisabled()

    // Partial text — still disabled
    const input = screen.getByTestId("nuclear-confirm-input")
    fireEvent.change(input, { target: { value: "DELETE" } })
    expect(confirmBtn).toBeDisabled()

    // Full phrase — enabled
    fireEvent.change(input, { target: { value: "DELETE ALL DATA" } })
    expect(confirmBtn).not.toBeDisabled()
  })

  it("hides confirmation dialog on cancel", () => {
    render(<NuclearDelete />)
    fireEvent.click(screen.getByTestId("nuclear-delete-trigger"))
    expect(screen.getByTestId("nuclear-confirm-input")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("nuclear-delete-cancel"))
    expect(screen.queryByTestId("nuclear-confirm-input")).not.toBeInTheDocument()
    expect(screen.getByTestId("nuclear-delete-trigger")).toBeInTheDocument()
  })

  it("calls DELETE /api/data/nuclear on confirm", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ deleted: true, message: "All data has been deleted." }),
    })

    // Mock window.location
    const locationSpy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      href: "/settings/general",
    })
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, href: "/settings/general" },
    })

    render(<NuclearDelete />)
    fireEvent.click(screen.getByTestId("nuclear-delete-trigger"))

    const input = screen.getByTestId("nuclear-confirm-input")
    fireEvent.change(input, { target: { value: "DELETE ALL DATA" } })
    fireEvent.click(screen.getByTestId("nuclear-delete-confirm"))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/data/nuclear", { method: "DELETE" })
    })

    locationSpy.mockRestore()
  })

  it("shows error message on failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => "Internal Server Error",
    })

    render(<NuclearDelete />)
    fireEvent.click(screen.getByTestId("nuclear-delete-trigger"))

    const input = screen.getByTestId("nuclear-confirm-input")
    fireEvent.change(input, { target: { value: "DELETE ALL DATA" } })
    fireEvent.click(screen.getByTestId("nuclear-delete-confirm"))

    await waitFor(() => {
      expect(screen.getByTestId("nuclear-delete-error")).toBeInTheDocument()
    })
  })

  it("has proper accessibility attributes", () => {
    render(<NuclearDelete />)
    fireEvent.click(screen.getByTestId("nuclear-delete-trigger"))

    const dialog = screen.getByRole("alertdialog")
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute("aria-labelledby", "nuclear-delete-title")
    expect(dialog).toHaveAttribute("aria-describedby", "nuclear-delete-desc")
  })
})
