/** Per-chromosome variant count bar chart (P1-21).
 *
 * Displays a stacked bar chart showing het/hom/nocall counts per chromosome.
 * Uses react-plotly.js for interactive zoom, hover tooltips, and responsive sizing.
 */

import Plot from 'react-plotly.js'
import type { ChromosomeQCStats } from '@/types/variants'

interface ChromosomeBarChartProps {
  data: ChromosomeQCStats[]
}

export default function ChromosomeBarChart({ data }: ChromosomeBarChartProps) {
  const chroms = data.map((d) => `chr${d.chrom}`)

  return (
    <Plot
      data={[
        {
          x: chroms,
          y: data.map((d) => d.het_count),
          type: 'bar',
          name: 'Heterozygous',
          marker: { color: '#0D9488' },
          hovertemplate: '%{x}: %{y:,} het<extra></extra>',
        },
        {
          x: chroms,
          y: data.map((d) => d.hom_count),
          type: 'bar',
          name: 'Homozygous',
          marker: { color: '#5EEAD4' },
          hovertemplate: '%{x}: %{y:,} hom<extra></extra>',
        },
        {
          x: chroms,
          y: data.map((d) => d.nocall_count),
          type: 'bar',
          name: 'No-call',
          marker: { color: '#94A3B8' },
          hovertemplate: '%{x}: %{y:,} no-call<extra></extra>',
        },
      ]}
      layout={{
        barmode: 'stack',
        title: { text: 'Variants per Chromosome', font: { size: 14 } },
        xaxis: {
          title: { text: 'Chromosome' },
          tickangle: -45,
          tickfont: { size: 10 },
        },
        yaxis: {
          title: { text: 'Count' },
          gridwidth: 1,
        },
        margin: { t: 40, b: 60, l: 60, r: 20 },
        legend: { orientation: 'h', y: -0.25 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: '#64748B' },
        height: 300,
      }}
      config={{ responsive: true, displayModeBar: false }}
      useResizeHandler
      style={{ width: '100%' }}
    />
  )
}
