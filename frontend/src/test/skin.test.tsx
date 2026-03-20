/** Tests for the Gene Skin UI (P3-56, T3-67). */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "./test-utils"
import userEvent from "@testing-library/user-event"
import PathwayCard from "@/components/skin/PathwayCard"
import type { PathwaySummary } from "@/types/skin"

// ── Fixtures ──────────────────────────────────────────────────────────

const PIGMENTATION_PATHWAY: PathwaySummary = {
  pathway_id: "pigmentation_uv",
  pathway_name: "Pigmentation & UV Response",
  level: "Elevated",
  evidence_level: 3,
  called_snps: 4,
  total_snps: 4,
  missing_snps: [],
  pmids: ["18488027", "17952075"],
}

const BARRIER_PATHWAY: PathwaySummary = {
  pathway_id: "skin_barrier_inflammation",
  pathway_name: "Skin Barrier & Inflammation",
  level: "Moderate",
  evidence_level: 2,
  called_snps: 2,
  total_snps: 3,
  missing_snps: ["rs61816761"],
  pmids: ["16804399"],
}

const OXIDATIVE_PATHWAY: PathwaySummary = {
  pathway_id: "oxidative_stress_aging",
  pathway_name: "Oxidative Stress & Aging",
  level: "Standard",
  evidence_level: 1,
  called_snps: 3,
  total_snps: 3,
  missing_snps: [],
  pmids: [],
}

const MICRONUTRIENTS_PATHWAY: PathwaySummary = {
  pathway_id: "skin_micronutrients",
  pathway_name: "Skin Micronutrients",
  level: "Moderate",
  evidence_level: 2,
  called_snps: 1,
  total_snps: 2,
  missing_snps: ["rs7975232"],
  pmids: ["20541252"],
}

// ── PathwayCard tests ─────────────────────────────────────────────────

describe("PathwayCard", () => {
  const onClick = vi.fn()

  beforeEach(() => {
    onClick.mockClear()
  })

  it("renders pathway name", () => {
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Pigmentation & UV Response")).toBeInTheDocument()
  })

  it("shows Elevated badge for Elevated level", () => {
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Elevated")).toBeInTheDocument()
  })

  it("shows Moderate badge for Moderate level", () => {
    render(<PathwayCard pathway={BARRIER_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Moderate")).toBeInTheDocument()
  })

  it("shows Standard badge for Standard level", () => {
    render(<PathwayCard pathway={OXIDATIVE_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Standard")).toBeInTheDocument()
  })

  it("renders evidence stars", () => {
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    expect(screen.getByLabelText("3 of 4 stars evidence")).toBeInTheDocument()
  })

  it("renders SNP coverage count", () => {
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("4/4 SNPs called")).toBeInTheDocument()
  })

  it("calls onClick when clicked", async () => {
    const user = userEvent.setup()
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    await user.click(
      screen.getByRole("button", {
        name: "Pigmentation & UV Response — Elevated",
      }),
    )
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("calls onClick on Enter key", async () => {
    const user = userEvent.setup()
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    const card = screen.getByRole("button", {
      name: "Pigmentation & UV Response — Elevated",
    })
    card.focus()
    await user.keyboard("{Enter}")
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("has accessible role and label", () => {
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByRole("button", {
        name: "Pigmentation & UV Response — Elevated",
      }),
    ).toBeInTheDocument()
  })

  it("renders pathway description for pigmentation_uv", () => {
    render(<PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/MC1R-driven pigmentation.*UV sensitivity/),
    ).toBeInTheDocument()
  })

  it("renders pathway description for skin_barrier_inflammation", () => {
    render(<PathwayCard pathway={BARRIER_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/Skin barrier integrity.*filaggrin/),
    ).toBeInTheDocument()
  })

  it("renders pathway description for oxidative_stress_aging", () => {
    render(<PathwayCard pathway={OXIDATIVE_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/Antioxidant capacity.*collagen/),
    ).toBeInTheDocument()
  })

  it("renders pathway description for skin_micronutrients", () => {
    render(<PathwayCard pathway={MICRONUTRIENTS_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/Vitamin D receptor.*micronutrient/),
    ).toBeInTheDocument()
  })

  it("shows selected state when selected prop is true", () => {
    render(
      <PathwayCard pathway={PIGMENTATION_PATHWAY} onClick={onClick} selected />,
    )
    const card = screen.getByRole("button", {
      name: "Pigmentation & UV Response — Elevated",
    })
    expect(card).toHaveAttribute("data-selected", "true")
  })

  it("renders all four pathway cards with correct data", () => {
    const pathways = [PIGMENTATION_PATHWAY, BARRIER_PATHWAY, OXIDATIVE_PATHWAY, MICRONUTRIENTS_PATHWAY]
    for (const pathway of pathways) {
      const { unmount } = render(
        <PathwayCard pathway={pathway} onClick={onClick} />,
      )
      expect(screen.getByText(pathway.pathway_name)).toBeInTheDocument()
      unmount()
    }
  })
})
