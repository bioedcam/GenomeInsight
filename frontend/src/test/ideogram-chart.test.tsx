/** Tests for per-chromosome ideogram with density overlay (P2-24).
 *
 * T2-22: Ideogram renders heatmap with correct chromosome layout.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from './test-utils'
import ChromosomeIdeogram from '@/components/charts/ChromosomeIdeogram'
import type { DensityBin } from '@/types/variants'

// Mock react-plotly.js since it requires a browser canvas.
vi.mock('react-plotly.js', () => ({
  default: ({
    data,
    layout,
  }: {
    data: Array<{ z?: unknown[][]; type?: string }>
    layout: { title?: { text?: string }; shapes?: unknown[] }
  }) => (
    <div data-testid="plotly-chart" data-title={layout?.title?.text}>
      <span data-testid="plotly-trace-count">{data.length}</span>
      <span data-testid="plotly-trace-type">{data[0]?.type}</span>
      <span data-testid="plotly-shape-count">{layout?.shapes?.length ?? 0}</span>
      {data[0]?.z && (
        <span data-testid="plotly-row-count">{(data[0].z as unknown[][]).length}</span>
      )}
    </div>
  ),
}))

const MOCK_BINS: DensityBin[] = [
  { chrom: '1', bin_start: 0, bin_end: 1_000_000, high: 1, moderate: 5, low: 3, modifier: 10, total: 19 },
  { chrom: '1', bin_start: 1_000_000, bin_end: 2_000_000, high: 0, moderate: 2, low: 1, modifier: 8, total: 11 },
  { chrom: '2', bin_start: 0, bin_end: 1_000_000, high: 2, moderate: 3, low: 0, modifier: 5, total: 10 },
  { chrom: 'X', bin_start: 0, bin_end: 1_000_000, high: 0, moderate: 0, low: 1, modifier: 4, total: 5 },
]

describe('ChromosomeIdeogram', () => {
  it('renders a Plotly heatmap chart', () => {
    render(<ChromosomeIdeogram bins={MOCK_BINS} />)
    const chart = screen.getByTestId('plotly-chart')
    expect(chart).toBeInTheDocument()
    expect(chart.getAttribute('data-title')).toBe('Chromosome Ideogram — Variant Density')
    expect(screen.getByTestId('plotly-trace-type').textContent).toBe('heatmap')
  })

  it('creates one row per chromosome (25 total)', () => {
    render(<ChromosomeIdeogram bins={MOCK_BINS} />)
    expect(screen.getByTestId('plotly-row-count').textContent).toBe('25')
  })

  it('creates chromosome outline shapes (25 total)', () => {
    render(<ChromosomeIdeogram bins={MOCK_BINS} />)
    expect(screen.getByTestId('plotly-shape-count').textContent).toBe('25')
  })

  it('shows empty state when bins array is empty', () => {
    render(<ChromosomeIdeogram bins={[]} />)
    expect(screen.getByText('No variant density data available for ideogram.')).toBeInTheDocument()
    expect(screen.queryByTestId('plotly-chart')).not.toBeInTheDocument()
  })

  it('renders with single bin', () => {
    const singleBin: DensityBin[] = [
      { chrom: '1', bin_start: 0, bin_end: 1_000_000, high: 0, moderate: 0, low: 0, modifier: 3, total: 3 },
    ]
    render(<ChromosomeIdeogram bins={singleBin} />)
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })

  it('renders with bins across all chromosomes', () => {
    const allChromBins: DensityBin[] = [
      '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
      '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
      '21', '22', 'X', 'Y', 'MT',
    ].map((chrom) => ({
      chrom,
      bin_start: 0,
      bin_end: 1_000_000,
      high: 1,
      moderate: 2,
      low: 3,
      modifier: 4,
      total: 10,
    }))
    render(<ChromosomeIdeogram bins={allChromBins} />)
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
    expect(screen.getByTestId('plotly-row-count').textContent).toBe('25')
  })
})
