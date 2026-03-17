/** Tests for the Ancestry UI (P3-27, P3-34). */

import { describe, it, expect, vi } from "vitest"
import { render, screen } from "./test-utils"
import AncestryResultCard from "@/components/ancestry/AncestryResultCard"
import AdmixtureBar from "@/components/ancestry/AdmixtureBar"
import PCAScatter from "@/components/ancestry/PCAScatter"
import HaplogroupCard from "@/components/ancestry/HaplogroupCard"
import type {
  AncestryFindingResponse,
  HaplogroupAssignment,
  PCACoordinatesResponse,
} from "@/types/ancestry"

// Mock react-plotly.js to avoid canvas issues in tests
vi.mock("react-plotly.js", () => ({
  default: (props: { data: unknown[]; "data-testid"?: string }) => (
    <div data-testid="plotly-chart" data-traces={JSON.stringify(props.data)} />
  ),
}))

// ── Fixtures ──────────────────────────────────────────────────────────

const ANCESTRY_FINDING: AncestryFindingResponse = {
  top_population: "EUR",
  pc_scores: [0.012, -0.004, 0.001, 0.002, -0.001, 0.000],
  population_distances: {
    AFR: 0.85,
    AMR: 0.32,
    EAS: 0.71,
    EUR: 0.04,
    SAS: 0.45,
    OCE: 0.92,
  },
  admixture_fractions: {
    EUR: 0.82,
    AMR: 0.11,
    EAS: 0.04,
    SAS: 0.02,
    AFR: 0.01,
    OCE: 0.00,
  },
  population_ranking: [
    { population: "EUR", distance: 0.04 },
    { population: "AMR", distance: 0.32 },
    { population: "SAS", distance: 0.45 },
    { population: "EAS", distance: 0.71 },
    { population: "AFR", distance: 0.85 },
    { population: "OCE", distance: 0.92 },
  ],
  snps_used: 112,
  snps_total: 128,
  coverage_fraction: 0.875,
  projection_time_ms: 45.3,
  is_sufficient: true,
  evidence_level: 2,
  finding_text: "Primary ancestry component: European (82.0%)",
}

const LOW_COVERAGE_FINDING: AncestryFindingResponse = {
  ...ANCESTRY_FINDING,
  snps_used: 20,
  snps_total: 128,
  coverage_fraction: 0.156,
  is_sufficient: false,
  finding_text: "Primary ancestry component: European (70.0%) — low coverage",
}

const PCA_COORDINATES: PCACoordinatesResponse = {
  user: [0.012, -0.004, 0.001, 0.002, -0.001, 0.000],
  reference_samples: {
    EUR: [
      [0.01, -0.005],
      [0.015, -0.003],
    ],
    AFR: [
      [-0.02, 0.03],
      [-0.025, 0.035],
    ],
  },
  centroids: {
    EUR: [0.012, -0.004],
    AFR: [-0.022, 0.032],
  },
  population_labels: {
    EUR: "European",
    AFR: "African",
  },
  n_components: 6,
  pc_labels: ["PC1", "PC2", "PC3", "PC4", "PC5", "PC6"],
  top_population: "EUR",
}

// ── AncestryResultCard tests ─────────────────────────────────────────

describe("AncestryResultCard", () => {
  it("renders top population badge", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(screen.getByTestId("top-population-badge")).toHaveTextContent("European")
  })

  it("renders finding text", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(
      screen.getByText("Primary ancestry component: European (82.0%)"),
    ).toBeInTheDocument()
  })

  it("renders SNP coverage stats", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(screen.getByText(/112 \/ 128 AIMs used \(88%\)/)).toBeInTheDocument()
  })

  it("renders evidence stars", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(screen.getByLabelText("2 of 4 stars evidence")).toBeInTheDocument()
  })

  it("shows low coverage warning when insufficient", () => {
    render(<AncestryResultCard finding={LOW_COVERAGE_FINDING} />)
    expect(
      screen.getByText("Low coverage — results may be unreliable"),
    ).toBeInTheDocument()
  })

  it("does not show low coverage warning when sufficient", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(
      screen.queryByText("Low coverage — results may be unreliable"),
    ).not.toBeInTheDocument()
  })

  it("renders population ranking", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(screen.getByText("Population Ranking")).toBeInTheDocument()
    // "European" appears twice (badge + ranking), so use getAllByText
    expect(screen.getAllByText("European").length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("Admixed American")).toBeInTheDocument()
    expect(screen.getByText("East Asian")).toBeInTheDocument()
    expect(screen.getByText("South Asian")).toBeInTheDocument()
    expect(screen.getByText("African")).toBeInTheDocument()
    expect(screen.getByText("Oceanian")).toBeInTheDocument()
  })

  it("renders population distances", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(screen.getByText("0.0400")).toBeInTheDocument()
    expect(screen.getByText("0.3200")).toBeInTheDocument()
  })

  it("has accessible test id", () => {
    render(<AncestryResultCard finding={ANCESTRY_FINDING} />)
    expect(screen.getByTestId("ancestry-result-card")).toBeInTheDocument()
  })
})

// ── AdmixtureBar tests ──────────────────────────────────────────────

describe("AdmixtureBar", () => {
  it("renders the chart container", () => {
    render(
      <AdmixtureBar admixture_fractions={ANCESTRY_FINDING.admixture_fractions} />,
    )
    expect(screen.getByTestId("admixture-bar")).toBeInTheDocument()
  })

  it("renders plotly chart with traces", () => {
    render(
      <AdmixtureBar admixture_fractions={ANCESTRY_FINDING.admixture_fractions} />,
    )
    expect(screen.getByTestId("plotly-chart")).toBeInTheDocument()
  })

  it("shows empty state when no fractions", () => {
    render(<AdmixtureBar admixture_fractions={{}} />)
    expect(
      screen.getByText("No admixture data available."),
    ).toBeInTheDocument()
  })

  it("filters out near-zero fractions", () => {
    render(
      <AdmixtureBar admixture_fractions={{ EUR: 0.99, AFR: 0.0005 }} />,
    )
    const chart = screen.getByTestId("plotly-chart")
    const traces = JSON.parse(chart.getAttribute("data-traces") ?? "[]")
    // Only EUR should appear (AFR is below 0.001 threshold)
    expect(traces).toHaveLength(1)
    expect(traces[0].name).toBe("European")
  })
})

// ── PCAScatter tests ────────────────────────────────────────────────

describe("PCAScatter", () => {
  it("renders the chart container", () => {
    render(<PCAScatter pcaData={PCA_COORDINATES} />)
    expect(screen.getByTestId("pca-scatter")).toBeInTheDocument()
  })

  it("renders plotly chart", () => {
    render(<PCAScatter pcaData={PCA_COORDINATES} />)
    expect(screen.getByTestId("plotly-chart")).toBeInTheDocument()
  })

  it("includes reference population traces", () => {
    render(<PCAScatter pcaData={PCA_COORDINATES} />)
    const chart = screen.getByTestId("plotly-chart")
    const traces = JSON.parse(chart.getAttribute("data-traces") ?? "[]")
    const names = traces.map((t: { name: string }) => t.name)
    expect(names).toContain("European")
    expect(names).toContain("African")
  })

  it("includes user sample trace", () => {
    render(<PCAScatter pcaData={PCA_COORDINATES} />)
    const chart = screen.getByTestId("plotly-chart")
    const traces = JSON.parse(chart.getAttribute("data-traces") ?? "[]")
    const names = traces.map((t: { name: string }) => t.name)
    expect(names).toContain("You")
  })

  it("includes centroids trace", () => {
    render(<PCAScatter pcaData={PCA_COORDINATES} />)
    const chart = screen.getByTestId("plotly-chart")
    const traces = JSON.parse(chart.getAttribute("data-traces") ?? "[]")
    const names = traces.map((t: { name: string }) => t.name)
    expect(names).toContain("Centroids")
  })
})

// ── HaplogroupCard tests (P3-34) ──────────────────────────────────

const MT_ASSIGNMENT: HaplogroupAssignment = {
  type: "mt",
  haplogroup: "H1a",
  confidence: 0.904,
  defining_snps_present: 47,
  defining_snps_total: 52,
  traversal_path: [
    { haplogroup: "L3", snps_present: 3, snps_total: 3 },
    { haplogroup: "N", snps_present: 5, snps_total: 6 },
    { haplogroup: "R", snps_present: 2, snps_total: 2 },
    { haplogroup: "R0", snps_present: 1, snps_total: 1 },
    { haplogroup: "HV", snps_present: 4, snps_total: 5 },
    { haplogroup: "H", snps_present: 8, snps_total: 9 },
    { haplogroup: "H1", snps_present: 6, snps_total: 7 },
    { haplogroup: "H1a", snps_present: 18, snps_total: 19 },
  ],
  finding_text: "Mitochondrial haplogroup: H1a (47/52 defining SNPs matched, 90% confidence)",
}

const Y_ASSIGNMENT: HaplogroupAssignment = {
  type: "Y",
  haplogroup: "R1b1a",
  confidence: 0.846,
  defining_snps_present: 11,
  defining_snps_total: 13,
  traversal_path: [
    { haplogroup: "CT", snps_present: 2, snps_total: 2 },
    { haplogroup: "F", snps_present: 1, snps_total: 1 },
    { haplogroup: "K", snps_present: 1, snps_total: 2 },
    { haplogroup: "R", snps_present: 2, snps_total: 2 },
    { haplogroup: "R1b", snps_present: 3, snps_total: 3 },
    { haplogroup: "R1b1a", snps_present: 2, snps_total: 3 },
  ],
  finding_text: "Y-chromosome haplogroup: R1b1a (11/13 defining SNPs matched, 85% confidence)",
}

describe("HaplogroupCard", () => {
  it("renders empty state when no assignments", () => {
    render(<HaplogroupCard assignments={[]} />)
    expect(screen.getByTestId("haplogroup-card")).toBeInTheDocument()
    expect(
      screen.getByText(/No haplogroup assignments available/),
    ).toBeInTheDocument()
  })

  it("renders mt assignment with haplogroup name", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(screen.getByTestId("haplogroup-assignment-mt")).toBeInTheDocument()
    expect(screen.getByTestId("haplogroup-name")).toHaveTextContent("H1a")
  })

  it("renders confidence badge", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(screen.getByTestId("haplogroup-confidence-badge")).toHaveTextContent("90% confidence")
  })

  it("renders defining SNP match fraction", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(screen.getByText("47 / 52 defining SNPs matched")).toBeInTheDocument()
  })

  it("renders traversal path with all nodes", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    const path = screen.getByTestId("haplogroup-traversal-path")
    expect(path).toBeInTheDocument()
    expect(screen.getByText("L3")).toBeInTheDocument()
    expect(screen.getByText("N")).toBeInTheDocument()
    // R, H, H1, H1a appear multiple times (in path + haplogroup name + finding text)
    // so verify via traversal path container
    expect(path.textContent).toContain("R")
    expect(path.textContent).toContain("HV")
    expect(path.textContent).toContain("H1")
    expect(path.textContent).toContain("H1a")
  })

  it("shows per-node SNP counts in traversal", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(screen.getByText("3/3")).toBeInTheDocument() // L3
    expect(screen.getByText("5/6")).toBeInTheDocument() // N
    expect(screen.getByText("18/19")).toBeInTheDocument() // H1a
  })

  it("renders finding text", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(
      screen.getByText(/Mitochondrial haplogroup: H1a/),
    ).toBeInTheDocument()
  })

  it("renders both mt and Y assignments", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT, Y_ASSIGNMENT]} />)
    expect(screen.getByTestId("haplogroup-assignment-mt")).toBeInTheDocument()
    expect(screen.getByTestId("haplogroup-assignment-Y")).toBeInTheDocument()
    expect(screen.getByText("Mitochondrial (mtDNA)")).toBeInTheDocument()
    expect(screen.getByText("Y-Chromosome")).toBeInTheDocument()
  })

  it("shows correct tree labels", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(screen.getByText("Mitochondrial (mtDNA)")).toBeInTheDocument()
  })

  it("renders low confidence with warning color", () => {
    const lowConf: HaplogroupAssignment = {
      ...MT_ASSIGNMENT,
      confidence: 0.35,
    }
    render(<HaplogroupCard assignments={[lowConf]} />)
    expect(screen.getByTestId("haplogroup-confidence-badge")).toHaveTextContent("35% confidence")
  })

  it("highlights terminal haplogroup in traversal path", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    const path = screen.getByTestId("haplogroup-traversal-path")
    const highlighted = path.querySelectorAll("[data-highlighted]")
    expect(highlighted.length).toBeGreaterThanOrEqual(1)
  })

  it("has accessible card test id", () => {
    render(<HaplogroupCard assignments={[MT_ASSIGNMENT]} />)
    expect(screen.getByTestId("haplogroup-card")).toBeInTheDocument()
  })
})
