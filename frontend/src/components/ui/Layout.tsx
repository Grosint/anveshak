import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
import { useWS } from '../../contexts/WSContext'

const navItems = [
  { to: '/topics',  label: 'Topics',        icon: <TargetIcon /> },
  { to: '/signals', label: 'Signals',        icon: <ZapIcon /> },
  { to: '/vision',  label: 'Image Analysis', icon: <EyeIcon /> },
  { to: '/reports', label: 'Reports',        icon: <FileIcon /> },
  { to: '/sources', label: 'Sources',        icon: <RadioIcon /> },
]

export default function Layout() {
  const { toggle, isDark } = useTheme()
  const { user, logout } = useAuth()
  const { status: wsStatus } = useWS()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen bg-anveshak-bg overflow-hidden">
      {/* ── Sidebar (desktop) ────────────────────────────────────────────────── */}
      <nav
        aria-label="Main navigation"
        className="hidden md:flex w-56 shrink-0 bg-anveshak-card border-r border-anveshak-border flex-col"
      >
        {/* Logo + WS status dot */}
        <div className="px-4 py-4 border-b border-anveshak-border">
          <div className="flex items-center gap-2">
            <span className="text-anveshak-accent font-bold text-lg tracking-tight">Anveshak</span>
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                wsStatus === 'connected' ? 'bg-cred-high pulse-ring' : 'bg-text-muted'
              }`}
              title={`WebSocket: ${wsStatus}`}
              aria-label={`WebSocket ${wsStatus}`}
            />
          </div>
          <p className="text-xs text-text-muted mt-0.5">OSINT Platform</p>
        </div>

        {/* Nav links */}
        <div className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-anveshak-accent text-white font-medium'
                    : 'text-text-secondary hover:bg-anveshak-muted hover:text-text-primary'
                }`
              }
            >
              <span className="w-4 h-4 shrink-0" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>

        {/* Footer: theme toggle + logout */}
        <div className="p-2 border-t border-anveshak-border space-y-0.5">
          <button
            onClick={toggle}
            className="flex items-center gap-2 w-full px-3 py-2 rounded text-sm text-text-secondary hover:bg-anveshak-muted hover:text-text-primary transition-colors"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <span className="w-4 h-4 shrink-0" aria-hidden="true">
              {isDark ? <SunIcon /> : <MoonIcon />}
            </span>
            <span>{isDark ? 'Light mode' : 'Dark mode'}</span>
          </button>
          {user && (
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 w-full px-3 py-2 rounded text-sm text-text-muted hover:text-signal-high hover:bg-signal-high/10 transition-colors"
              aria-label="Sign out"
            >
              <span className="w-4 h-4 shrink-0" aria-hidden="true"><LogOutIcon /></span>
              <span className="truncate text-xs">{user.sub}</span>
            </button>
          )}
        </div>
      </nav>

      {/* ── Mobile bottom nav ────────────────────────────────────────────────── */}
      <nav
        aria-label="Mobile navigation"
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-anveshak-card border-t border-anveshak-border flex justify-around py-1.5"
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-2 py-1 rounded text-xs transition-colors ${
                isActive ? 'text-anveshak-accent' : 'text-text-muted'
              }`
            }
          >
            <span className="w-5 h-5" aria-hidden="true">{item.icon}</span>
            <span>{item.label.split(' ')[0]}</span>
          </NavLink>
        ))}
      </nav>

      {/* ── Page content ─────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto pb-14 md:pb-0" id="main-content">
        <Outlet />
      </main>
    </div>
  )
}

// ── Inline SVG icons (zero dep, accessible via aria-hidden on containers) ────

function TargetIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
    </svg>
  )
}
function ZapIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
    </svg>
  )
}
function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
    </svg>
  )
}
function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  )
}
function RadioIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 010 8.49m-8.48-.01a6 6 0 010-8.49m11.31-2.82a10 10 0 010 14.14m-14.14 0a10 10 0 010-14.14"/>
    </svg>
  )
}
function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  )
}
function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
    </svg>
  )
}
function LogOutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
    </svg>
  )
}
