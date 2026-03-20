/** Saved queries panel (P4-02).
 *
 * Lists saved queries with load/delete actions.
 * Shows a save dialog for naming new queries.
 */

import { useState } from "react"
import { Loader2, Save, Trash2, FolderOpen, Clock } from "lucide-react"
import { useSavedQueries, useSaveQuery, useDeleteSavedQuery } from "@/api/query-builder"
import type { RuleGroupModel, SavedQuery } from "@/types/query-builder"

interface SavedQueriesPanelProps {
  currentFilter: RuleGroupModel
  onLoad: (query: SavedQuery) => void
}

export default function SavedQueriesPanel({
  currentFilter,
  onLoad,
}: SavedQueriesPanelProps) {
  const [saveName, setSaveName] = useState("")
  const [showSaveInput, setShowSaveInput] = useState(false)

  const savedQueries = useSavedQueries()
  const saveQuery = useSaveQuery()
  const deleteQuery = useDeleteSavedQuery()

  const handleSave = () => {
    const name = saveName.trim()
    if (!name) return
    saveQuery.mutate(
      { name, filter: currentFilter },
      {
        onSuccess: () => {
          setSaveName("")
          setShowSaveInput(false)
        },
      },
    )
  }

  const handleDelete = (name: string) => {
    if (!window.confirm(`Delete query "${name}"?`)) return
    deleteQuery.mutate(name)
  }

  const hasRules = currentFilter.rules && currentFilter.rules.length > 0

  return (
    <div className="rounded-lg border border-border bg-card" data-testid="saved-queries-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Saved Queries</h3>
        </div>
        {!showSaveInput && (
          <button
            type="button"
            onClick={() => setShowSaveInput(true)}
            disabled={!hasRules}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={hasRules ? "Save current query" : "Add rules to save a query"}
            data-testid="save-query-btn"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        )}
      </div>

      {/* Save input */}
      {showSaveInput && (
        <div className="px-4 py-3 border-b border-border bg-muted/30">
          <label htmlFor="query-name-input" className="text-xs font-medium text-muted-foreground mb-1 block">
            Query name
          </label>
          <div className="flex gap-2">
            <input
              id="query-name-input"
              type="text"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="e.g., Pathogenic rare variants"
              className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave()
                if (e.key === "Escape") setShowSaveInput(false)
              }}
              data-testid="query-name-input"
              autoFocus
            />
            <button
              type="button"
              onClick={handleSave}
              disabled={!saveName.trim() || saveQuery.isPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {saveQuery.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setShowSaveInput(false)
                setSaveName("")
              }}
              className="rounded-md border border-input px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
            >
              Cancel
            </button>
          </div>
          {saveQuery.isError && (
            <p className="text-xs text-destructive mt-1">
              {saveQuery.error instanceof Error ? saveQuery.error.message : "Failed to save"}
            </p>
          )}
        </div>
      )}

      {/* Query list */}
      <div className="max-h-[300px] overflow-y-auto">
        {savedQueries.isLoading && (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {savedQueries.data && savedQueries.data.length === 0 && (
          <div className="px-4 py-6 text-center">
            <p className="text-sm text-muted-foreground">No saved queries yet.</p>
            <p className="text-xs text-muted-foreground mt-1">
              Build a query and click Save to store it for later.
            </p>
          </div>
        )}

        {savedQueries.data && savedQueries.data.length > 0 && (
          <ul className="divide-y divide-border" data-testid="saved-queries-list">
            {savedQueries.data.map((q) => (
              <li key={q.name} className="group flex items-center justify-between px-4 py-2.5 hover:bg-muted/30 transition-colors">
                <button
                  type="button"
                  onClick={() => onLoad(q)}
                  className="flex-1 text-left min-w-0"
                  data-testid="load-query-btn"
                >
                  <p className="text-sm font-medium truncate">{q.name}</p>
                  {(() => {
                    const ruleCount = countRules(q.filter)
                    return (
                      <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <Clock className="h-3 w-3" />
                        {new Date(q.updated_at).toLocaleDateString()}
                        <span className="mx-1">·</span>
                        {ruleCount} rule{ruleCount !== 1 ? "s" : ""}
                      </p>
                    )
                  })()}
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(q.name)
                  }}
                  className="opacity-0 group-hover:opacity-100 rounded-md p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
                  aria-label={`Delete query "${q.name}"`}
                  data-testid="delete-query-btn"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

/** Count total rules (recursively) in a filter tree. */
function countRules(filter: RuleGroupModel): number {
  let count = 0
  for (const rule of filter.rules ?? []) {
    if ("combinator" in rule) {
      count += countRules(rule as RuleGroupModel)
    } else {
      count += 1
    }
  }
  return count
}
