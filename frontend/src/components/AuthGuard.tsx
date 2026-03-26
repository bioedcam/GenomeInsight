/**
 * AuthGuard — redirects unauthenticated users to /login (P4-21a).
 *
 * Wraps protected routes. When auth is enabled and the user has no
 * valid session, redirects to the login page. When auth is disabled,
 * renders children immediately.
 */
import { Navigate, Outlet } from "react-router-dom"
import { useAuthStatus } from "@/api/auth"

export default function AuthGuard() {
  const { data: authStatus, isLoading } = useAuthStatus()

  // While loading auth status, show nothing (avoids flash)
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  // Auth is enabled but user is not authenticated — redirect to login
  if (authStatus?.auth_enabled && !authStatus.authenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
