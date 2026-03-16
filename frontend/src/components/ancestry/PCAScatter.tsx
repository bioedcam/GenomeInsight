/** PCA scatter plot — user projected onto reference panel PCA space (P3-27).
 *
 * Displays an interactive scatter plot with:
 * - Reference panel samples colored by population
 * - User sample as a prominent marker (star)
 * - Population centroids as diamond markers
 * Uses react-plotly.js for interactivity.
 */

import Plot from "react-plotly.js"
import type { PCACoordinatesResponse } from "@/types/ancestry"
import { POPULATION_COLORS, POPULATION_LABELS } from "./constants"

interface PCAScatterProps {
  pcaData: PCACoordinatesResponse
}

export default function PCAScatter({ pcaData }: PCAScatterProps) {
  const traces: Plotly.Data[] = []

  // Reference population samples (PC1 vs PC2)
  for (const [pop, coords] of Object.entries(pcaData.reference_samples)) {
    if (coords.length === 0) continue
    const label = POPULATION_LABELS[pop] ?? pop
    const color = POPULATION_COLORS[pop] ?? "#94A3B8"

    traces.push({
      x: coords.map((c) => c[0]),
      y: coords.map((c) => c[1]),
      mode: "markers",
      type: "scatter",
      name: label,
      marker: {
        color,
        size: 5,
        opacity: 0.5,
      },
      hovertemplate: `${label}<br>PC1: %{x:.4f}<br>PC2: %{y:.4f}<extra></extra>`,
    })
  }

  // Population centroids
  const centroidPops = Object.keys(pcaData.centroids).filter(
    (p) => pcaData.centroids[p]?.length >= 2
  )
  if (centroidPops.length > 0) {
    traces.push({
      x: centroidPops.map((p) => pcaData.centroids[p][0]),
      y: centroidPops.map((p) => pcaData.centroids[p][1]),
      mode: "text+markers",
      type: "scatter",
      name: "Centroids",
      text: centroidPops.map((p) => POPULATION_LABELS[p] ?? p),
      textposition: "top center",
      textfont: { size: 9, color: "#64748B" },
      marker: {
        symbol: "diamond",
        size: 10,
        color: centroidPops.map((p) => POPULATION_COLORS[p] ?? "#94A3B8"),
        line: { width: 1, color: "#1E293B" },
      },
      hovertemplate: "%{text}<br>PC1: %{x:.4f}<br>PC2: %{y:.4f}<extra>Centroid</extra>",
      showlegend: false,
    })
  }

  // User sample (prominent star marker)
  if (pcaData.user.length >= 2) {
    const userLabel = POPULATION_LABELS[pcaData.top_population] ?? pcaData.top_population
    traces.push({
      x: [pcaData.user[0]],
      y: [pcaData.user[1]],
      mode: "markers",
      type: "scatter",
      name: "You",
      marker: {
        symbol: "star",
        size: 16,
        color: "#0D9488",
        line: { width: 2, color: "#FFFFFF" },
      },
      hovertemplate: `Your sample<br>PC1: %{x:.4f}<br>PC2: %{y:.4f}<br>Top: ${userLabel}<extra></extra>`,
    })
  }

  return (
    <div data-testid="pca-scatter">
      <Plot
        data={traces}
        layout={{
          xaxis: {
            title: { text: pcaData.pc_labels[0] ?? "PC1", font: { size: 12 } },
            zeroline: false,
          },
          yaxis: {
            title: { text: pcaData.pc_labels[1] ?? "PC2", font: { size: 12 } },
            zeroline: false,
          },
          showlegend: true,
          legend: {
            orientation: "v" as const,
            x: 1.02,
            y: 1,
            font: { size: 10 },
          },
          margin: { t: 20, b: 50, l: 60, r: 140 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "#64748B" },
          height: 450,
          hovermode: "closest",
        }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: "100%" }}
      />
    </div>
  )
}
