import { Outlet } from 'react-router-dom'
import TopNav from './TopNav'
import Sidebar from './Sidebar'
import SkipNav from './SkipNav'

export default function AppLayout() {
  return (
    <div className="h-screen flex flex-col">
      <SkipNav />
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main id="main-content" className="flex-1 overflow-y-auto" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
