/**
 * @vitest-environment happy-dom
 */
import { createRef } from "react"
import { describe, it, expect, vi, beforeEach, afterAll } from "vitest"
import { render, screen, waitFor } from "@/test/test-utils"
import userEvent from "@testing-library/user-event"
import IgvBrowser from "./IgvBrowser"
import type { IgvBrowserHandle } from "./IgvBrowser"
import { __setIgvForTesting } from "./igv-test-utils"

const mockCreateBrowser = vi.fn()
const mockRemoveBrowser = vi.fn()
const mockSearch = vi.fn()
const mockOn = vi.fn()

const mockBrowser = {
  search: mockSearch,
  on: mockOn,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockCreateBrowser.mockResolvedValue(mockBrowser)
  __setIgvForTesting({
    createBrowser: mockCreateBrowser,
    removeBrowser: mockRemoveBrowser,
  })
})

afterAll(() => {
  __setIgvForTesting(null)
})

describe("IgvBrowser", () => {
  it("renders loading state initially", () => {
    render(<IgvBrowser />)
    expect(screen.getByRole("status")).toBeInTheDocument()
    expect(screen.getByText(/loading genome browser/i)).toBeInTheDocument()
  })

  it("creates IGV browser with GRCh37/hg19 genome on mount", async () => {
    render(<IgvBrowser />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    const [, options] = mockCreateBrowser.mock.calls[0]
    expect(options.genome).toBe("hg19")
    expect(options.locus).toBe("all")
    expect(options.showNavigation).toBe(true)
    expect(options.showRuler).toBe(true)
  })

  it("passes custom locus to IGV options", async () => {
    render(<IgvBrowser locus="chr17:41196312-41277500" />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    const [, options] = mockCreateBrowser.mock.calls[0]
    expect(options.locus).toBe("chr17:41196312-41277500")
  })

  it("passes additional tracks to IGV options", async () => {
    const tracks = [{ name: "Test Track", type: "variant", format: "vcf", url: "/api/test.vcf" }]
    render(<IgvBrowser tracks={tracks} />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    const [, options] = mockCreateBrowser.mock.calls[0]
    expect(options.tracks).toHaveLength(1)
    expect(options.tracks[0].name).toBe("Test Track")
  })

  it("removes loading state after browser creation", async () => {
    render(<IgvBrowser />)
    await waitFor(() => {
      expect(screen.queryByRole("status")).not.toBeInTheDocument()
    })
  })

  it("shows error state when browser creation fails", async () => {
    mockCreateBrowser.mockReset()
    mockCreateBrowser.mockRejectedValue(new Error("Network error"))
    render(<IgvBrowser />)
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument()
    })
    expect(screen.getByText("Failed to load genome browser")).toBeInTheDocument()
    expect(screen.getByText("Network error")).toBeInTheDocument()
    expect(screen.getByText("Retry")).toBeInTheDocument()
  })

  it("retries browser creation on retry button click", async () => {
    mockCreateBrowser.mockReset()
    mockCreateBrowser.mockRejectedValue(new Error("Network error"))
    const user = userEvent.setup()
    render(<IgvBrowser />)
    await waitFor(() => {
      expect(screen.getByText("Retry")).toBeInTheDocument()
    })
    mockCreateBrowser.mockReset()
    mockCreateBrowser.mockResolvedValue(mockBrowser)
    await user.click(screen.getByText("Retry"))
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })
  })

  it("removes browser on unmount", async () => {
    const { unmount } = render(<IgvBrowser />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    unmount()
    expect(mockRemoveBrowser).toHaveBeenCalledWith(mockBrowser)
  })

  it("registers trackclick handler for variant clicks", async () => {
    const onVariantClick = vi.fn()
    render(<IgvBrowser onVariantClick={onVariantClick} />)
    await waitFor(() => {
      expect(mockOn).toHaveBeenCalledWith("trackclick", expect.any(Function))
    })
  })

  it("invokes onVariantClick with parsed variant data", async () => {
    const onVariantClick = vi.fn()
    render(<IgvBrowser onVariantClick={onVariantClick} />)
    await waitFor(() => {
      expect(mockOn).toHaveBeenCalledWith("trackclick", expect.any(Function))
    })
    const trackClickHandler = mockOn.mock.calls.find(
      ([event]: [string]) => event === "trackclick",
    )?.[1]
    const result = trackClickHandler(
      { config: { type: "variant" } },
      [
        { name: "Chr", value: "chr17" },
        { name: "Pos", value: "41196312" },
        { name: "ID", value: "rs123" },
        { name: "Ref", value: "A" },
        { name: "Alt", value: "G" },
      ],
    )
    expect(onVariantClick).toHaveBeenCalledWith({
      chr: "chr17", pos: 41196312, id: "rs123", ref: "A", alt: "G",
    })
    expect(result).toBe(false)
  })

  it("skips onVariantClick when essential fields are missing", async () => {
    const onVariantClick = vi.fn()
    render(<IgvBrowser onVariantClick={onVariantClick} />)
    await waitFor(() => {
      expect(mockOn).toHaveBeenCalledWith("trackclick", expect.any(Function))
    })
    const trackClickHandler = mockOn.mock.calls.find(
      ([event]: [string]) => event === "trackclick",
    )?.[1]
    const result = trackClickHandler(
      { config: { type: "variant" } },
      [{ name: "ID", value: "rs123" }],
    )
    expect(onVariantClick).not.toHaveBeenCalled()
    expect(result).toBeUndefined()
  })

  it("exposes search method via ref", async () => {
    const ref = createRef<IgvBrowserHandle>()
    render(<IgvBrowser ref={ref} />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    ref.current?.search("BRCA1")
    expect(mockSearch).toHaveBeenCalledWith("BRCA1")
  })

  it("exposes getBrowser method via ref", async () => {
    const ref = createRef<IgvBrowserHandle>()
    render(<IgvBrowser ref={ref} />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    expect(ref.current?.getBrowser()).toBe(mockBrowser)
  })

  it("renders the IGV container div with data-testid", () => {
    render(<IgvBrowser />)
    expect(screen.getByTestId("igv-container")).toBeInTheDocument()
  })

  it("applies custom className to container", () => {
    const { container } = render(<IgvBrowser className="custom-class" />)
    expect(container.firstChild).toHaveClass("custom-class")
  })

  it("applies custom minHeight to the IGV container", async () => {
    render(<IgvBrowser minHeight={800} />)
    await waitFor(() => {
      expect(mockCreateBrowser).toHaveBeenCalledTimes(1)
    })
    const igvContainer = screen.getByTestId("igv-container")
    expect(igvContainer.style.minHeight).toBe("800px")
  })
})
