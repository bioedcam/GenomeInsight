/** React Query hooks and utilities for the report builder API (P4-10). */

import { useMutation } from "@tanstack/react-query"

export interface ReportRequest {
  sample_id: number
  modules?: string[]
  title?: string
}

/**
 * Generate a PDF report and trigger browser download.
 * Calls POST /api/reports/generate with the selected modules.
 */
export function useGenerateReport() {
  return useMutation({
    mutationFn: async (request: ReportRequest): Promise<Blob> => {
      const res = await fetch("/api/reports/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Report generation failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.blob()
    },
  })
}

/**
 * Fetch an HTML preview of the report.
 * Calls POST /api/reports/preview and returns the raw HTML string.
 */
export async function fetchReportPreview(request: ReportRequest): Promise<string> {
  const res = await fetch("/api/reports/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`Report preview failed: ${res.status}${text ? ` - ${text}` : ""}`)
  }
  return res.text()
}
