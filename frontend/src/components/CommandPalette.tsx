/**
 * Command palette (P2-18, prerequisite for P4-26e).
 *
 * cmdk-based palette triggered by Cmd+K / Ctrl+K.
 * Supports:
 *   - IGV navigation: gene symbol, rsid, or genomic coordinates
 *   - Page navigation: jump to any sidebar page
 *
 * Search + navigation only — no destructive or state-changing actions.
 */
import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Command } from "cmdk"
import {
  LayoutDashboard,
  Table2,
  Pill,
  Apple,
  ShieldAlert,
  HeartPulse,
  Brain,
  Baby,
  Globe,
  Dna,
  FileText,
  Settings,
  MapPin,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { isGenomicQuery } from "@/lib/genomic-query"

const pages = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/variants", icon: Table2, label: "Variant Explorer" },
  { to: "/pharmacogenomics", icon: Pill, label: "Pharmacogenomics" },
  { to: "/nutrigenomics", icon: Apple, label: "Nutrigenomics" },
  { to: "/cancer", icon: ShieldAlert, label: "Cancer" },
  { to: "/cardiovascular", icon: HeartPulse, label: "Cardiovascular" },
  { to: "/apoe", icon: Brain, label: "APOE" },
  { to: "/carrier-status", icon: Baby, label: "Carrier Status" },
  { to: "/ancestry", icon: Globe, label: "Ancestry" },
  { to: "/genome-browser", icon: Dna, label: "Genome Browser" },
  { to: "/reports", icon: FileText, label: "Reports" },
  { to: "/settings", icon: Settings, label: "Settings" },
]

export interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate()
  const [search, setSearch] = useState("")

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) setSearch("")
      onOpenChange(next)
    },
    [onOpenChange],
  )

  const navigateToLocus = useCallback(
    (locus: string) => {
      navigate(`/genome-browser?locus=${encodeURIComponent(locus.trim())}`)
      handleOpenChange(false)
    },
    [navigate, handleOpenChange],
  )

  const navigateToPage = useCallback(
    (path: string) => {
      navigate(path)
      handleOpenChange(false)
    },
    [navigate, handleOpenChange],
  )

  const showGenomicAction = search.trim().length > 0 && isGenomicQuery(search)

  return (
    <Command.Dialog
      open={open}
      onOpenChange={handleOpenChange}
      label="Command Menu"
      className={cn(
        "fixed inset-0 z-50",
        "[&_[cmdk-overlay]]:fixed [&_[cmdk-overlay]]:inset-0 [&_[cmdk-overlay]]:bg-black/50",
      )}
    >
      <div
        data-cmdk-overlay=""
        className="fixed inset-0 bg-black/50"
        onClick={() => handleOpenChange(false)}
      />
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-lg z-50">
        <div className="bg-background border border-border rounded-lg shadow-lg overflow-hidden">
          <Command.Input
            value={search}
            onValueChange={setSearch}
            placeholder="Search pages, genes, rsids, or coordinates..."
            className="w-full px-4 py-3 text-sm bg-transparent border-b border-border outline-none placeholder:text-muted-foreground"
            data-testid="command-palette-input"
          />
          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>

            {showGenomicAction && (
              <Command.Group heading="Genome Browser">
                <Command.Item
                  value={`navigate-igv-${search.trim()}`}
                  onSelect={() => navigateToLocus(search)}
                  className="flex items-center gap-2 px-2 py-1.5 text-sm rounded-md cursor-pointer data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground"
                  data-testid="command-palette-igv-item"
                >
                  <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span>
                    Jump to <strong>{search.trim()}</strong> in Genome Browser
                  </span>
                </Command.Item>
              </Command.Group>
            )}

            <Command.Group heading="Pages">
              {pages.map(({ to, icon: Icon, label }) => (
                <Command.Item
                  key={to}
                  value={label}
                  onSelect={() => navigateToPage(to)}
                  className="flex items-center gap-2 px-2 py-1.5 text-sm rounded-md cursor-pointer data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground"
                >
                  <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span>{label}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </div>
      </div>
    </Command.Dialog>
  )
}
