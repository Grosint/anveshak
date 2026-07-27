import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
import { useWS } from '../../contexts/WSContext'
import { sourcesApi } from '../../api/sources'
import IdentifierSearch from '../search/IdentifierSearch'

const primaryNav = [
  { to: '/topics',      label: 'Topics',      icon: <TargetIcon /> },
  { to: '/signals',     label: 'Signals',     icon: <ZapIcon /> },
  { to: '/cases',       label: 'Cases',       icon: <TrackerIcon /> },
  { to: '/vision',      label: 'Vision',      icon: <EyeIcon /> },
]

const settingsNav = { to: '/settings', label: 'Settings', icon: <GearIcon /> }

function getInitials(name: string): string {
  const clean = name.replace(/@.*/, '')
  const parts = clean.split(/[_.\-\s]+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return clean.slice(0, 2).toUpperCase()
}

export default function Layout() {
  const { toggle, isDark } = useTheme()
  const { user, logout } = useAuth()
  const { status: wsStatus } = useWS()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchInitialQuery, setSearchInitialQuery] = useState('')

  // Open search modal from URL param ?search=...
  useEffect(() => {
    const q = searchParams.get('search')
    if (q) {
      setSearchInitialQuery(q)
      setSearchOpen(true)
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

  // Lightweight poll for down-source count — shown as red badge on Source Health nav item
  const { data: sourcesData } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.list(0, 500),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
  const downCount = sourcesData?.items?.filter((s) => s.health_status === 'down').length ?? 0

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
          {primaryNav.map((item) => (
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
              <span className="flex-1">{item.label}</span>
            </NavLink>
          ))}

          {/* Global identifier search */}
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors text-text-secondary hover:bg-anveshak-muted hover:text-text-primary w-full"
            aria-label="Search identifiers"
          >
            <span className="w-4 h-4 shrink-0" aria-hidden="true"><SearchIcon /></span>
            <span className="flex-1 text-left">Search IDs</span>
            <kbd className="text-[9px] text-text-muted bg-anveshak-muted px-1 rounded">⌘K</kbd>
          </button>
        </div>

        {/* Footer: user profile + utility row */}
        <div className="p-3 border-t border-anveshak-border space-y-2">
          {user && (
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-anveshak-accent/20 text-anveshak-accent flex items-center justify-center text-xs font-bold shrink-0">
                {getInitials(user.username || user.sub)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text-primary font-medium truncate">
                  {user.username || user.sub}
                </p>
                <p className="text-[10px] text-text-muted">
                  {user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : 'Signed in'}
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="p-1.5 rounded hover:bg-signal-high/10 text-text-muted hover:text-signal-high transition-colors shrink-0"
                aria-label="Sign out"
              >
                <span className="w-4 h-4 block"><LogOutIcon /></span>
              </button>
            </div>
          )}
          {/* Utility row: Settings + Theme toggle */}
          <div className="flex items-center gap-1">
            <NavLink
              to={settingsNav.to}
              className={({ isActive }) =>
                `flex items-center gap-2 flex-1 px-2.5 py-1.5 rounded text-xs transition-colors ${
                  isActive
                    ? 'bg-anveshak-accent text-white font-medium'
                    : 'text-text-muted hover:bg-anveshak-muted hover:text-text-primary'
                }`
              }
            >
              <span className="w-3.5 h-3.5 shrink-0" aria-hidden="true">{settingsNav.icon}</span>
              <span>{settingsNav.label}</span>
              {downCount > 0 && (
                <span
                  className="text-[9px] font-bold min-w-[16px] h-[16px] flex items-center justify-center rounded-full bg-signal-high text-white shrink-0 ml-auto"
                  aria-label={`${downCount} source${downCount > 1 ? 's' : ''} down`}
                >
                  {downCount}
                </span>
              )}
            </NavLink>
            <button
              onClick={toggle}
              className="p-1.5 rounded text-text-muted hover:bg-anveshak-muted hover:text-text-primary transition-colors shrink-0"
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              <span className="w-3.5 h-3.5 block" aria-hidden="true">
                {isDark ? <SunIcon /> : <MoonIcon />}
              </span>
            </button>
          </div>
        </div>
      </nav>

      {/* ── Mobile bottom nav ────────────────────────────────────────────────── */}
      <nav
        aria-label="Mobile navigation"
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-anveshak-card border-t border-anveshak-border flex justify-around py-1.5"
      >
        {[...primaryNav, settingsNav].map((item) => (
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

      {/* Global identifier search modal */}
      <IdentifierSearch open={searchOpen} onClose={() => { setSearchOpen(false); setSearchInitialQuery('') }} initialQuery={searchInitialQuery} />
    </div>
  )
}

// ── Inline SVG icons (zero dep, accessible via aria-hidden on containers) ────

function TrackerIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/><path d="M12 5V3"/><path d="M12 21v-2"/>
    </svg>
  )
}
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
function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
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
function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
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
