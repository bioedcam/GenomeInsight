/** Settings page with sub-navigation (P4-18, P4-21b).
 *
 * Sub-routes: /settings → redirects to /settings/updates
 *   - /settings/general   (placeholder)
 *   - /settings/updates   (Update Manager — P4-18)
 *   - /settings/health    (placeholder)
 *   - /settings/about     (placeholder)
 */

import { NavLink, Routes, Route, Navigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Settings2, RefreshCw, Activity, Info } from 'lucide-react'
import UpdateManager from '@/components/settings/UpdateManager'
import PlaceholderPage from '@/components/PlaceholderPage'

const NAV_ITEMS = [
  { to: '/settings/general', label: 'General', icon: Settings2 },
  { to: '/settings/updates', label: 'Update Manager', icon: RefreshCw },
  { to: '/settings/health', label: 'System Health', icon: Activity },
  { to: '/settings/about', label: 'About', icon: Info },
] as const

function SettingsNav() {
  return (
    <nav aria-label="Settings sections" className="flex flex-col gap-0.5">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
              'hover:bg-muted/50',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              isActive
                ? 'bg-muted font-medium text-foreground'
                : 'text-muted-foreground',
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

function GeneralPlaceholder() {
  return (
    <PlaceholderPage
      moduleName="General Settings"
      phase={4}
      description="Application preferences, dark mode, storage path configuration."
    />
  )
}

function HealthPlaceholder() {
  return (
    <PlaceholderPage
      moduleName="System Health"
      phase={4}
      description="Log explorer, database stats, disk usage, and service status."
    />
  )
}

function AboutPlaceholder() {
  return (
    <PlaceholderPage
      moduleName="About"
      phase={4}
      description="Version info, licenses, and update notifications."
    />
  )
}

export default function Settings() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <div className="flex gap-6">
        {/* Mini sidebar */}
        <div className="w-48 shrink-0">
          <SettingsNav />
        </div>

        {/* Content area */}
        <div className="flex-1 min-w-0">
          <Routes>
            <Route index element={<Navigate to="updates" replace />} />
            <Route path="general" element={<GeneralPlaceholder />} />
            <Route path="updates" element={<UpdateManager />} />
            <Route path="health" element={<HealthPlaceholder />} />
            <Route path="about" element={<AboutPlaceholder />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
