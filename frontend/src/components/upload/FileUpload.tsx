/** File upload component with drag-and-drop, progress, and parse status (P1-16). */

import { useState, useRef, useCallback } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useIngestFile } from "@/api/samples"
import type { IngestResult } from "@/types/samples"

type UploadState = "idle" | "dragging" | "uploading" | "parsing" | "complete" | "error"

export default function FileUpload() {
  const [state, setState] = useState<UploadState>("idle")
  const [fileName, setFileName] = useState<string | null>(null)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const [, setSearchParams] = useSearchParams()

  const ingestMutation = useIngestFile()

  const handleFile = useCallback(
    async (file: File) => {
      setFileName(file.name)
      setError(null)
      setState("uploading")

      try {
        // Brief uploading state, then parsing
        setState("parsing")
        const res = await ingestMutation.mutateAsync(file)
        setResult(res)
        setState("complete")

        // Update URL with the new sample_id so other components pick it up
        setSearchParams({ sample_id: String(res.sample_id) })
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Upload failed"
        // Try to parse FastAPI error detail
        try {
          const parsed = JSON.parse(message)
          setError(parsed.detail || message)
        } catch {
          setError(message)
        }
        setState("error")
      }
    },
    [ingestMutation, setSearchParams],
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setState((prev) => (prev === "idle" ? "dragging" : prev))
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setState((prev) => (prev === "dragging" ? "idle" : prev))
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const onFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const resetUpload = useCallback(() => {
    setState("idle")
    setFileName(null)
    setResult(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }, [])

  // Idle / dragging — show drop zone
  if (state === "idle" || state === "dragging") {
    return (
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click()
        }}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
          state === "dragging"
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-accent/50",
        )}
      >
        <Upload className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">
          Drop your 23andMe file here or click to browse
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Supports 23andMe raw data files (v3, v4, v5)
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.csv,.tsv"
          onChange={onFileSelect}
          className="hidden"
          aria-label="Upload 23andMe file"
        />
      </div>
    )
  }

  // Uploading / parsing — show progress
  if (state === "uploading" || state === "parsing") {
    return (
      <div className="border rounded-lg p-6 text-center">
        <Loader2 className="h-8 w-8 mx-auto mb-3 text-primary animate-spin" />
        <p className="text-sm font-medium text-foreground flex items-center justify-center gap-2">
          <FileText className="h-4 w-4" />
          {fileName}
        </p>
        <p className="text-xs text-muted-foreground mt-2">
          {state === "uploading" ? "Uploading..." : "Parsing variants..."}
        </p>
        <div className="mt-3 h-1.5 bg-muted rounded-full overflow-hidden max-w-xs mx-auto">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 animate-pulse"
            style={{ width: state === "uploading" ? "30%" : "70%" }}
          />
        </div>
      </div>
    )
  }

  // Complete — show result
  if (state === "complete" && result) {
    return (
      <div className="border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/30 rounded-lg p-6">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground flex items-center gap-2">
              <FileText className="h-4 w-4 shrink-0" />
              <span className="truncate">{fileName}</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {result.variant_count.toLocaleString()} variants parsed
              {result.nocall_count > 0 && ` · ${result.nocall_count.toLocaleString()} no-calls`}
              {" · "}
              {result.file_format.replace("23andme_", "23andMe ").toUpperCase()}
            </p>
            <div className="flex gap-2 mt-3">
              <button
                type="button"
                onClick={() =>
                  navigate(`/variants?sample_id=${result.sample_id}`)
                }
                className="text-xs font-medium text-primary hover:text-primary/80 transition-colors"
              >
                View variants &rarr;
              </button>
              <button
                type="button"
                onClick={resetUpload}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Upload another
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  return (
    <div className="border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 rounded-lg p-6">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground">Upload failed</p>
          <p className="text-xs text-muted-foreground mt-1">{error}</p>
          <button
            type="button"
            onClick={resetUpload}
            className="text-xs font-medium text-primary hover:text-primary/80 mt-3 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    </div>
  )
}
