/** Tests for the Gene Health UI (P3-66). */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "./test-utils"
import userEvent from "@testing-library/user-event"
import PathwayCard from "@/components/gene-health/PathwayCard"
import type { PathwaySummary } from "@/types/gene-health"

// ── Fixtures ──────────────────────────────────────────────────────────

const NEUROLOGICAL_PATHWAY: PathwaySummary = {
  pathway_id: "neurological",
  pathway_name: "Neurological Conditions",
  level: "Elevated",
  evidence_level: 3,
  called_snps: 10,
  total_snps: 12,
  missing_snps: ["rs123", "rs456"],
  pmids: ["29059683", "24842889"],
}

const METABOLIC_PATHWAY: PathwaySummary = {
  pathway_id: "metabolic",
  pathway_name: "Metabolic Conditions",
  level: "Moderate",
  evidence_level: 3,
  called_snps: 9,
  total_snps: 10,
  missing_snps: ["rs789"],
  pmids: ["22885922"],
}

const AUTOIMMUNE_PATHWAY: PathwaySummary = {
  pathway_id: "autoimmune",
  pathway_name: "Autoimmune Conditions",
  level: "Standard",
  evidence_level: 3,
  called_snps: 12,
  total_snps: 12,
  missing_snps: [],
  pmids: ["20190752"],
}

const SENSORY_PATHWAY: PathwaySummary = {
  pathway_id: "sensory",
  pathway_name: "Sensory Conditions",
  level: "Standard",
  evidence_level: 2,
  called_snps: 7,
  total_snps: 9,
  missing_snps: ["rs101", "rs102"],
  pmids: [],
}

// ── PathwayCard tests ─────────────────────────────────────────────────

describe("PathwayCard", () => {
  const onClick = vi.fn()

  beforeEach(() => {
    onClick.mockClear()
  })

  it("renders pathway name", () => {
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Neurological Conditions")).toBeInTheDocument()
  })

  it("shows Elevated badge for Elevated level", () => {
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Elevated")).toBeInTheDocument()
  })

  it("shows Moderate badge for Moderate level", () => {
    render(<PathwayCard pathway={METABOLIC_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Moderate")).toBeInTheDocument()
  })

  it("shows Standard badge for Standard level", () => {
    render(<PathwayCard pathway={AUTOIMMUNE_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("Standard")).toBeInTheDocument()
  })

  it("renders evidence stars", () => {
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    expect(screen.getByLabelText("3 of 4 stars evidence")).toBeInTheDocument()
  })

  it("renders SNP coverage count", () => {
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    expect(screen.getByText("10/12 SNPs called")).toBeInTheDocument()
  })

  it("calls onClick when clicked", async () => {
    const user = userEvent.setup()
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    await user.click(
      screen.getByRole("button", {
        name: "Neurological Conditions — Elevated",
      }),
    )
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("calls onClick on Enter key", async () => {
    const user = userEvent.setup()
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    const card = screen.getByRole("button", {
      name: "Neurological Conditions — Elevated",
    })
    card.focus()
    await user.keyboard("{Enter}")
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("has accessible role and label", () => {
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByRole("button", {
        name: "Neurological Conditions — Elevated",
      }),
    ).toBeInTheDocument()
  })

  it("renders pathway description for neurological", () => {
    render(<PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/neurological conditions.*Alzheimer.*Parkinson/i),
    ).toBeInTheDocument()
  })

  it("renders pathway description for metabolic", () => {
    render(<PathwayCard pathway={METABOLIC_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/metabolic conditions.*type 2 diabetes.*obesity/i),
    ).toBeInTheDocument()
  })

  it("renders pathway description for autoimmune", () => {
    render(<PathwayCard pathway={AUTOIMMUNE_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/autoimmune conditions.*rheumatoid arthritis/i),
    ).toBeInTheDocument()
  })

  it("renders pathway description for sensory", () => {
    render(<PathwayCard pathway={SENSORY_PATHWAY} onClick={onClick} />)
    expect(
      screen.getByText(/sensory conditions.*hearing loss/i),
    ).toBeInTheDocument()
  })

  it("shows selected state when selected prop is true", () => {
    render(
      <PathwayCard pathway={NEUROLOGICAL_PATHWAY} onClick={onClick} selected />,
    )
    const card = screen.getByRole("button", {
      name: "Neurological Conditions — Elevated",
    })
    expect(card).toHaveAttribute("data-selected", "true")
  })

  it("renders all four pathway cards with correct data", () => {
    const pathways = [NEUROLOGICAL_PATHWAY, METABOLIC_PATHWAY, AUTOIMMUNE_PATHWAY, SENSORY_PATHWAY]
    for (const pathway of pathways) {
      const { unmount } = render(
        <PathwayCard pathway={pathway} onClick={onClick} />,
      )
      expect(screen.getByText(pathway.pathway_name)).toBeInTheDocument()
      unmount()
    }
  })
})
