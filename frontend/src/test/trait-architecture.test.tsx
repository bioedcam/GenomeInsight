import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import TraitArchitectureCard from "@/components/ui/TraitArchitectureCard"

describe("TraitArchitectureCard", () => {
  it("renders the collapsible explainer", () => {
    render(<TraitArchitectureCard />)
    expect(screen.getByTestId("trait-architecture-card")).toBeInTheDocument()
    expect(screen.getByText("How to read a polygenic score")).toBeInTheDocument()
  })

  it("explains the three architecture points", () => {
    render(<TraitArchitectureCard />)
    expect(screen.getByText(/Most heritability is missing/)).toBeInTheDocument()
    expect(screen.getByText(/h²_twin/)).toBeInTheDocument()
    expect(screen.getByText(/Accuracy drops across ancestries/)).toBeInTheDocument()
    expect(screen.getByText(/Ding et al., Nature 2023/)).toBeInTheDocument()
    expect(screen.getByText(/Calibration is not accuracy/)).toBeInTheDocument()
  })
})
