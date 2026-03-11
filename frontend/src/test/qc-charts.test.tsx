/** Tests for QC charts (P1-21).
 *
 * Tests the QualityControl component with QC stats data,
 * and verifies chart components render correctly.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from './test-utils'
import QualityControl from '@/components/dashboard/QualityControl'
import ChromosomeBarChart from '@/components/charts/ChromosomeBarChart'
import HeterozygosityHistogram from '@/components/charts/HeterozygosityHistogram'
import type { QCStats, ChromosomeQCStats } from '@/types/variants'

// Mock react-plotly.js since it requires a browser canvas
vi.mock('react-plotly.js', () => ({
  default: ({ data, layout }: { data: unknown[]; layout: { title?: { text?: string } } }) => (
    <div data-testid="plotly-chart" data-title={layout?.title?.text}>
      <span data-testid="plotly-trace-count">{data.length}</span>
    </div>
  ),
}))

const MOCK_QC_STATS: QCStats = {
  total_variants: 623841,
  called_variants: 610000,
  nocall_variants: 13841,
  het_count: 210000,
  hom_count: 400000,
  call_rate: 0.977817,
  heterozygosity_rate: 0.344262,
  per_chromosome: [
    { chrom: '1', total: 50000, het_count: 17000, hom_count: 32000, nocall_count: 1000 },
    { chrom: '2', total: 45000, het_count: 15500, hom_count: 28500, nocall_count: 1000 },
    { chrom: '3', total: 38000, het_count: 13000, hom_count: 24000, nocall_count: 1000 },
    { chrom: 'X', total: 22000, het_count: 4000, hom_count: 17500, nocall_count: 500 },
    { chrom: 'MT', total: 800, het_count: 0, hom_count: 780, nocall_count: 20 },
  ],
}

// ─── QualityControl with QC stats ────────────────────────────────────

describe('QualityControl with QC stats', () => {
  it('shows call rate and het rate when qcStats provided', () => {
    render(<QualityControl variantCount={623841} qcStats={MOCK_QC_STATS} />)
    fireEvent.click(screen.getByText('Sample QC'))
    expect(screen.getByText('97.78%')).toBeInTheDocument()
    expect(screen.getByText('34.43%')).toBeInTheDocument()
  })

  it('renders charts when qcStats is provided', () => {
    render(<QualityControl variantCount={623841} qcStats={MOCK_QC_STATS} />)
    fireEvent.click(screen.getByText('Sample QC'))
    const charts = screen.getAllByTestId('plotly-chart')
    expect(charts).toHaveLength(2)
  })

  it('shows placeholder text when qcStats is null', () => {
    render(<QualityControl variantCount={623841} qcStats={null} />)
    fireEvent.click(screen.getByText('Sample QC'))
    expect(screen.getByText(/Detailed QC charts/)).toBeInTheDocument()
    expect(screen.queryByTestId('plotly-chart')).not.toBeInTheDocument()
  })

  it('shows placeholder text when qcStats is undefined', () => {
    render(<QualityControl variantCount={623841} />)
    fireEvent.click(screen.getByText('Sample QC'))
    expect(screen.getByText(/Detailed QC charts/)).toBeInTheDocument()
  })

  it('shows dashes for call rate and het rate when no qcStats', () => {
    render(<QualityControl variantCount={623841} qcStats={null} />)
    fireEvent.click(screen.getByText('Sample QC'))
    // variant count is shown, call rate and het rate are dashes
    expect(screen.getByText('623,841')).toBeInTheDocument()
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBe(2)
  })
})

// ─── ChromosomeBarChart ──────────────────────────────────────────────

describe('ChromosomeBarChart', () => {
  it('renders a Plotly chart with 3 traces (het, hom, nocall)', () => {
    render(<ChromosomeBarChart data={MOCK_QC_STATS.per_chromosome} />)
    const chart = screen.getByTestId('plotly-chart')
    expect(chart).toBeInTheDocument()
    expect(chart.getAttribute('data-title')).toBe('Variants per Chromosome')
    expect(screen.getByTestId('plotly-trace-count').textContent).toBe('3')
  })
})

// ─── HeterozygosityHistogram ─────────────────────────────────────────

describe('HeterozygosityHistogram', () => {
  it('renders a Plotly chart with 1 trace', () => {
    render(
      <HeterozygosityHistogram
        data={MOCK_QC_STATS.per_chromosome}
        overallRate={MOCK_QC_STATS.heterozygosity_rate}
      />,
    )
    const chart = screen.getByTestId('plotly-chart')
    expect(chart).toBeInTheDocument()
    expect(chart.getAttribute('data-title')).toBe('Heterozygosity Rate by Chromosome')
    expect(screen.getByTestId('plotly-trace-count').textContent).toBe('1')
  })

  it('filters out chromosomes with 0 called variants', () => {
    const dataWithZero: ChromosomeQCStats[] = [
      { chrom: '1', total: 100, het_count: 30, hom_count: 70, nocall_count: 0 },
      { chrom: '2', total: 50, het_count: 0, hom_count: 0, nocall_count: 50 }, // all nocall
    ]
    render(<HeterozygosityHistogram data={dataWithZero} overallRate={0.3} />)
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })
})
