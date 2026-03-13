/** Tests for consequence type donut chart (P2-25).
 *
 * T2-22: Consequence donut shows expected distribution for test data.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from './test-utils'
import ConsequenceDonut from '@/components/charts/ConsequenceDonut'
import type { ConsequenceCount } from '@/types/variants'

// Mock react-plotly.js since it requires a browser canvas
vi.mock('react-plotly.js', () => ({
  default: ({ data, layout }: { data: Array<{ labels?: string[]; values?: number[] }>; layout: { title?: { text?: string }; annotations?: Array<{ text?: string }> } }) => (
    <div data-testid="plotly-chart" data-title={layout?.title?.text}>
      <span data-testid="plotly-labels">{data[0]?.labels?.join(',')}</span>
      <span data-testid="plotly-values">{data[0]?.values?.join(',')}</span>
      <span data-testid="plotly-center">{layout?.annotations?.[0]?.text}</span>
    </div>
  ),
}))

const MOCK_ITEMS: ConsequenceCount[] = [
  { consequence: 'intron_variant', count: 350, tier: 'MODIFIER' },
  { consequence: 'missense_variant', count: 120, tier: 'MODERATE' },
  { consequence: 'synonymous_variant', count: 80, tier: 'LOW' },
  { consequence: 'frameshift_variant', count: 10, tier: 'HIGH' },
  { consequence: 'unknown', count: 40, tier: 'MODIFIER' },
]

const MOCK_TOTAL = 600

describe('ConsequenceDonut', () => {
  it('renders a Plotly donut chart with correct title', () => {
    render(<ConsequenceDonut items={MOCK_ITEMS} total={MOCK_TOTAL} />)
    const chart = screen.getByTestId('plotly-chart')
    expect(chart).toBeInTheDocument()
    expect(chart.getAttribute('data-title')).toBe('Consequence Types')
  })

  it('shows empty state message when items array is empty', () => {
    render(<ConsequenceDonut items={[]} total={0} />)
    expect(screen.getByText('No consequence data available.')).toBeInTheDocument()
    expect(screen.queryByTestId('plotly-chart')).not.toBeInTheDocument()
  })

  it('renders formatted consequence labels', () => {
    render(<ConsequenceDonut items={MOCK_ITEMS} total={MOCK_TOTAL} />)
    const labels = screen.getByTestId('plotly-labels').textContent
    expect(labels).toContain('Intron Variant')
    expect(labels).toContain('Missense Variant')
    expect(labels).toContain('Synonymous Variant')
    expect(labels).toContain('Frameshift Variant')
  })

  it('passes correct values to Plotly', () => {
    render(<ConsequenceDonut items={MOCK_ITEMS} total={MOCK_TOTAL} />)
    const values = screen.getByTestId('plotly-values').textContent
    expect(values).toBe('350,120,80,10,40')
  })

  it('displays total count in center annotation', () => {
    render(<ConsequenceDonut items={MOCK_ITEMS} total={MOCK_TOTAL} />)
    expect(screen.getByTestId('plotly-center').textContent).toBe('600')
  })

  it('renders with single item', () => {
    const singleItem: ConsequenceCount[] = [
      { consequence: 'missense_variant', count: 42, tier: 'MODERATE' },
    ]
    render(<ConsequenceDonut items={singleItem} total={42} />)
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })

  it('renders with many consequence types', () => {
    const manyItems: ConsequenceCount[] = Array.from({ length: 20 }, (_, i) => ({
      consequence: `type_${i}`,
      count: 100 - i * 5,
      tier: ['HIGH', 'MODERATE', 'LOW', 'MODIFIER'][i % 4],
    }))
    const total = manyItems.reduce((sum, item) => sum + item.count, 0)
    render(<ConsequenceDonut items={manyItems} total={total} />)
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })
})
