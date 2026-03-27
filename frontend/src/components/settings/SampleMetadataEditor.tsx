/** Sample metadata CRUD editor (P4-21f).
 *
 * Displays all samples with editable metadata fields:
 * name, notes, date_collected, source, custom JSON extra.
 * Includes individual sample deletion with confirmation.
 */

import { useState } from "react"
import { Pencil, Trash2, Save, X, ChevronDown, ChevronUp, Plus, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatFileFormat } from "@/lib/format"
import { useSamples, useSample, useUpdateSample, useDeleteSample } from "@/api/samples"
import type { SampleUpdate } from "@/types/samples"

function ExtraFieldEditor({
  extra,
  onChange,
}: {
  extra: Record<string, unknown>
  onChange: (extra: Record<string, unknown>) => void
}) {
  const [newKey, setNewKey] = useState("")
  const [newValue, setNewValue] = useState("")

  const entries = Object.entries(extra)

  function handleAdd() {
    const key = newKey.trim()
    if (!key) return
    onChange({ ...extra, [key]: newValue })
    setNewKey("")
    setNewValue("")
  }

  function handleRemove(key: string) {
    const next = { ...extra }
    delete next[key]
    onChange(next)
  }

  function handleValueChange(key: string, value: string) {
    onChange({ ...extra, [key]: value })
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-foreground">
        Custom Fields
      </label>
      {entries.length > 0 && (
        <div className="space-y-1.5">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-sm font-mono text-muted-foreground w-32 truncate shrink-0">
                {key}
              </span>
              <input
                type="text"
                value={String(value ?? "")}
                onChange={(e) => handleValueChange(key, e.target.value)}
                className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="button"
                onClick={() => handleRemove(key)}
                className="shrink-0 p-1.5 text-muted-foreground hover:text-red-500 transition-colors"
                aria-label={`Remove ${key}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Key"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          className="w-32 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          data-testid="extra-new-key"
        />
        <input
          type="text"
          placeholder="Value"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              handleAdd()
            }
          }}
          className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          data-testid="extra-new-value"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!newKey.trim()}
          className="shrink-0 inline-flex items-center gap-1 rounded-md border border-input px-2.5 py-1.5 text-sm hover:bg-muted disabled:opacity-50 transition-colors"
          data-testid="extra-add-btn"
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </button>
      </div>
    </div>
  )
}

function SampleEditForm({
  sampleId,
  onClose,
}: {
  sampleId: number
  onClose: () => void
}) {
  const { data: sample, isLoading } = useSample(sampleId)
  const updateSample = useUpdateSample()
  const [name, setName] = useState<string | null>(null)
  const [notes, setNotes] = useState<string | null>(null)
  const [dateCollected, setDateCollected] = useState<string | null>(null)
  const [source, setSource] = useState<string | null>(null)
  const [extra, setExtra] = useState<Record<string, unknown> | null>(null)
  const [saved, setSaved] = useState(false)

  if (isLoading || !sample) {
    return <p className="text-sm text-muted-foreground py-4">Loading metadata...</p>
  }

  const currentName = name ?? sample.name
  const currentNotes = notes ?? sample.notes ?? ""
  const currentDate = dateCollected ?? sample.date_collected ?? ""
  const currentSource = source ?? sample.source ?? ""
  const currentExtra = extra ?? sample.extra ?? {}

  const hasChanges =
    (name !== null && name !== sample.name) ||
    (notes !== null && notes !== (sample.notes ?? "")) ||
    (dateCollected !== null && dateCollected !== (sample.date_collected ?? "")) ||
    (source !== null && source !== (sample.source ?? "")) ||
    (extra !== null && JSON.stringify(extra) !== JSON.stringify(sample.extra ?? {}))

  function handleSave() {
    const data: SampleUpdate = {}
    if (name !== null) data.name = name
    if (notes !== null) data.notes = notes
    if (dateCollected !== null) data.date_collected = dateCollected
    if (source !== null) data.source = source
    if (extra !== null) data.extra = extra

    updateSample.mutate(
      { sampleId, data },
      {
        onSuccess: () => {
          setSaved(true)
          // Reset local state so it picks up the new values from the query
          setName(null)
          setNotes(null)
          setDateCollected(null)
          setSource(null)
          setExtra(null)
          setTimeout(() => setSaved(false), 2000)
        },
      }
    )
  }

  return (
    <div className="space-y-4 p-4 border border-border rounded-lg bg-card" data-testid="sample-edit-form">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor={`name-${sampleId}`} className="block text-sm font-medium text-foreground mb-1">
            Name
          </label>
          <input
            id={`name-${sampleId}`}
            type="text"
            value={currentName}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="sample-name-input"
          />
        </div>

        <div>
          <label htmlFor={`source-${sampleId}`} className="block text-sm font-medium text-foreground mb-1">
            Source / Lab
          </label>
          <input
            id={`source-${sampleId}`}
            type="text"
            value={currentSource}
            onChange={(e) => setSource(e.target.value)}
            placeholder="e.g., 23andMe, Clinical Lab"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="sample-source-input"
          />
        </div>

        <div>
          <label htmlFor={`date-${sampleId}`} className="block text-sm font-medium text-foreground mb-1">
            Date Collected
          </label>
          <input
            id={`date-${sampleId}`}
            type="date"
            value={currentDate}
            onChange={(e) => setDateCollected(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="sample-date-input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">
            Format
          </label>
          <p className="text-sm text-foreground py-2">
            {formatFileFormat(sample.file_format)}
          </p>
        </div>
      </div>

      <div>
        <label htmlFor={`notes-${sampleId}`} className="block text-sm font-medium text-foreground mb-1">
          Notes
        </label>
        <textarea
          id={`notes-${sampleId}`}
          rows={3}
          value={currentNotes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Free-text notes about this sample..."
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary"
          data-testid="sample-notes-input"
        />
      </div>

      <ExtraFieldEditor extra={currentExtra} onChange={setExtra} />

      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          disabled={!hasChanges || updateSample.isPending}
          onClick={handleSave}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          data-testid="sample-save-btn"
        >
          <Save className="h-3.5 w-3.5" />
          {updateSample.isPending ? "Saving..." : "Save Changes"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
        >
          <X className="h-3.5 w-3.5" />
          Close
        </button>
        {saved && (
          <span className="text-sm text-green-600 dark:text-green-400" data-testid="save-success">
            Saved!
          </span>
        )}
        {updateSample.isError && (
          <span className="text-sm text-red-600 dark:text-red-400" role="alert">
            Error: {updateSample.error.message}
          </span>
        )}
      </div>
    </div>
  )
}

function DeleteSampleConfirm({
  sampleId,
  sampleName,
  onCancel,
  onDeleted,
}: {
  sampleId: number
  sampleName: string
  onCancel: () => void
  onDeleted: () => void
}) {
  const deleteSample = useDeleteSample()

  function handleConfirm() {
    deleteSample.mutate(sampleId, { onSuccess: onDeleted })
  }

  return (
    <div
      role="alertdialog"
      aria-labelledby={`delete-title-${sampleId}`}
      className="rounded-lg border-2 border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4 space-y-3"
      data-testid="delete-confirm-dialog"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
        <div>
          <h4 id={`delete-title-${sampleId}`} className="text-sm font-semibold text-red-800 dark:text-red-300">
            Delete &ldquo;{sampleName}&rdquo;?
          </h4>
          <p className="text-sm text-red-700 dark:text-red-400 mt-1">
            This will permanently remove the sample database file and all associated data
            (variants, annotations, findings, tags). This action cannot be undone.
          </p>
        </div>
      </div>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleConfirm}
          disabled={deleteSample.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
          data-testid="delete-confirm-btn"
        >
          {deleteSample.isPending ? "Deleting..." : "Delete Sample"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={deleteSample.isPending}
          className="inline-flex items-center rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          data-testid="delete-cancel-btn"
        >
          Cancel
        </button>
      </div>
      {deleteSample.isError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          Delete failed: {deleteSample.error.message}
        </p>
      )}
    </div>
  )
}

export default function SampleMetadataEditor() {
  const { data: samples, isLoading } = useSamples()
  const [editingSampleId, setEditingSampleId] = useState<number | null>(null)
  const [deletingSampleId, setDeletingSampleId] = useState<number | null>(null)

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading samples...</p>
  }

  if (!samples || samples.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-center" data-testid="no-samples">
        <p className="text-sm text-muted-foreground">
          No samples loaded. Upload a file from the dashboard to get started.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4" data-testid="sample-metadata-editor">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Sample Management</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Edit sample metadata, add notes, or delete individual samples.
        </p>
      </div>

      <div className="space-y-3">
        {samples.map((sample) => {
          const isEditing = editingSampleId === sample.id
          const isDeleting = deletingSampleId === sample.id

          return (
            <div key={sample.id} className="rounded-lg border border-border bg-card">
              {/* Sample header row */}
              <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <button
                    type="button"
                    onClick={() => setEditingSampleId(isEditing ? null : sample.id)}
                    className="shrink-0 p-1 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={isEditing ? "Collapse" : "Expand"}
                    aria-expanded={isEditing}
                    data-testid={`sample-expand-${sample.id}`}
                  >
                    {isEditing ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {sample.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileFormat(sample.file_format)}
                      {sample.created_at && (
                        <>
                          {" \u00B7 "}
                          Imported {new Date(sample.created_at).toLocaleDateString()}
                        </>
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingSampleId(isEditing ? null : sample.id)
                      setDeletingSampleId(null)
                    }}
                    className={cn(
                      "p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors",
                      isEditing && "text-primary bg-primary/10"
                    )}
                    aria-label={`Edit ${sample.name}`}
                    data-testid={`sample-edit-${sample.id}`}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDeletingSampleId(isDeleting ? null : sample.id)
                      setEditingSampleId(null)
                    }}
                    className={cn(
                      "p-2 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors",
                      isDeleting && "text-red-500 bg-red-50 dark:bg-red-950/30"
                    )}
                    aria-label={`Delete ${sample.name}`}
                    data-testid={`sample-delete-${sample.id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Expanded edit form */}
              {isEditing && (
                <div className="border-t border-border">
                  <SampleEditForm
                    sampleId={sample.id}
                    onClose={() => setEditingSampleId(null)}
                  />
                </div>
              )}

              {/* Delete confirmation */}
              {isDeleting && (
                <div className="border-t border-border p-4">
                  <DeleteSampleConfirm
                    sampleId={sample.id}
                    sampleName={sample.name}
                    onCancel={() => setDeletingSampleId(null)}
                    onDeleted={() => setDeletingSampleId(null)}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
