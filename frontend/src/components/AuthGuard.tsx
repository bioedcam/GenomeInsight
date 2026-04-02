/**
 * AuthGuard — redirects unauthenticated users to /login (P4-21a)
 * and fresh installs to /setup.
 *
 * Wraps protected routes. On fresh install (needs_setup), redirects
 * to the setup wizard. When auth is enabled and the user has no
 * valid session, redirects to the login page. Otherwise renders
 * children immediately.
 */
import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuthStatus } from "@/api/auth"
import { useSetupStatus } from "@/api/setup"

export default function AuthGuard() {
  const { data: authStatus, isLoading: authLoading } = useAuthStatus()
  const { data: setupStatus, isLoading: setupLoading } = useSetupStatus()
  const location = useLocation()

  // While loading, show nothing (avoids flash)
  if (authLoading || setupLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  // Fresh install → redirect to setup wizard (unless already there)
  if (setupStatus?.needs_setup && !location.pathname.startsWith("/setup")) {
    return <Navigate to="/setup" replace />
  }

  // Auth is enabled but user is not authenticated — redirect to login
  if (authStatus?.auth_enabled && !authStatus.authenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
