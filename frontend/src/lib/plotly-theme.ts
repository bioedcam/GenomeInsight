/** Plotly layout overrides for dark mode (P4-26a).
 *
 * Provides a function that returns Plotly layout properties
 * that adapt to the current theme. Charts always use transparent
 * backgrounds; this adjusts font, grid, and shape colors.
 */

export interface PlotlyThemeOverrides {
  font: { color: string }
  paper_bgcolor: string
  plot_bgcolor: string
  /** Color for gridlines and shape outlines. */
  gridColor: string
  /** Color for annotation text (e.g., mean lines). */
  annotationColor: string
}

/** Get Plotly layout colors based on current resolved theme. */
export function getPlotlyTheme(isDark: boolean): PlotlyThemeOverrides {
  if (isDark) {
    return {
      font: { color: '#94A3B8' },       // slate-400 — readable on dark bg
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      gridColor: 'rgba(148,163,184,0.15)', // slate-400 at 15%
      annotationColor: '#94A3B8',
    }
  }
  return {
    font: { color: '#64748B' },          // slate-500 — readable on light bg
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    gridColor: 'rgba(100,116,139,0.15)',   // slate-500 at 15%
    annotationColor: '#64748B',
  }
}
