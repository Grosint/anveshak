import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'

// ── Animated brand mark ───────────────────────────────────────────────────────
// Inline SVG so CSS animations (radar-scan dots, inner-ring breathe, amber
// glow) work without a separate asset fetch and without a build-step import.
//
// Design language: mirrors the Drishti family mark.
//   Drishti  (दृष्टि  = sight)   — downward triangle, receiving
//   Anveshak (अन्वेषक = seeker)  — upward  triangle, reaching outward

function BrandMark({ size = 148 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      width={size}
      height={size}
      className="brand-mark-glow"
      aria-hidden
    >
      {/* Horizontal data-horizon line */}
      <line
        x1="-6" y1="12" x2="106" y2="12"
        stroke="#F5A623" strokeWidth="2.8" strokeLinecap="square"
      />

      {/* Outer orbit ring */}
      <circle cx="50" cy="55" r="43" stroke="#C47A0B" strokeWidth="2" />

      {/* Cardinal orbital markers — radar-scan animation E → S → W → N */}
      <circle cx="93" cy="55" r="3.2" fill="#D4956A" className="dot-east"  />
      <circle cx="50" cy="98" r="3.2" fill="#D4956A" className="dot-south" />
      <circle cx="7"  cy="55" r="3.2" fill="#D4956A" className="dot-west"  />
      <circle cx="50" cy="12" r="3.2" fill="#D4956A" className="dot-north" />

      {/* Inner focus ring — breathes */}
      <g className="orbit-inner-anim">
        <circle cx="50" cy="55" r="29" stroke="#F5A623" strokeWidth="2" />
      </g>

      {/* Upward triangle — Investigator's Prism */}
      <polygon
        points="50,30 28,67 72,67"
        fill="#FAF0E0" stroke="#F5A623" strokeWidth="1.6" strokeLinejoin="miter"
      />

      {/* Centre focal dot */}
      <circle cx="50" cy="55" r="4.8" fill="#F5A623" />
    </svg>
  )
}

// ── Feature row ───────────────────────────────────────────────────────────────
function Feature({ icon, label }: { icon: string; label: string }) {
  return (
    <li className="flex items-center gap-3 text-sm text-[#4a5568]">
      <span className="text-[#F5A623] text-base leading-none shrink-0">{icon}</span>
      {label}
    </li>
  )
}

// ── Login page ────────────────────────────────────────────────────────────────
export default function Login() {
  const [username, setUsername]     = useState('')
  const [password, setPassword]     = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError]           = useState('')
  const [loading, setLoading]       = useState(false)
  const { login }  = useAuth()
  const navigate   = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await axios.post<{ access_token: string }>(
        '/api/v1/auth/login',
        { username, password },
      )
      login(data.access_token)
      navigate('/topics', { replace: true })
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError('Invalid username or password.')
      } else {
        setError('Unable to reach the server. Try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0C1018] overflow-hidden relative">

      {/* ── Intelligence scan line ─────────────────────────────────────────── */}
      <div className="scan-line" aria-hidden />

      {/* ── Classification bar ─────────────────────────────────────────────── */}
      <div className="shrink-0 w-full border-b border-[#F5A623]/12 py-1.5 px-4 text-center"
           style={{ background: 'rgba(245,166,35,0.04)' }}>
        <span className="text-[9px] font-mono tracking-[0.35em] text-[#F5A623]/45 uppercase select-none">
          Unclassified&nbsp;&nbsp;·&nbsp;&nbsp;For Official Use Only
          &nbsp;&nbsp;·&nbsp;&nbsp;iDEX ADITI 4.0 · PS-18
        </span>
      </div>

      <div className="flex flex-1 min-h-0">

        {/* ════════════════════════════════════════════════════════════════════
            LEFT — Brand panel
            ════════════════════════════════════════════════════════════════════ */}
        <div className="hidden lg:flex flex-col justify-between w-[58%] px-16 py-14 bg-[#0E1420] relative overflow-hidden select-none">

          {/* Ambient amber radial glow behind the mark */}
          <div
            className="absolute top-[38%] left-[42%] -translate-x-1/2 -translate-y-1/2 w-[520px] h-[520px] rounded-full pointer-events-none"
            style={{ background: 'radial-gradient(circle, rgba(245,166,35,0.055) 0%, transparent 62%)' }}
            aria-hidden
          />

          {/* Subtle dot-grid texture */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: 'radial-gradient(circle, rgba(245,166,35,0.09) 1px, transparent 1px)',
              backgroundSize: '30px 30px',
              opacity: 0.4,
            }}
            aria-hidden
          />

          {/* Top: logo + wordmark */}
          <div className="relative z-10">
            <BrandMark size={148} />

            <h1 className="mt-7 font-bold tracking-[0.18em] text-white leading-none"
                style={{ fontSize: '2.5rem' }}>
              ANVESHAK
            </h1>
            <p
              className="mt-2.5 text-xl tracking-[0.1em] text-[#F5A623]"
              style={{ fontFamily: "'Noto Sans Devanagari', 'Mangal', 'Devanagari MT', serif" }}
            >
              अन्वेषक
            </p>
            <p className="mt-3 text-[10px] tracking-[0.28em] text-[#374151] uppercase">
              AI · OSINT · Intelligence Platform
            </p>
          </div>

          {/* Middle: description + features */}
          <div className="relative z-10 space-y-7">
            <p className="text-sm text-[#374151] leading-relaxed max-w-xs">
              Sovereign, standalone intelligence analysis for defence and law enforcement.
              Monitor open sources, verify media, and generate auditable, traceable
              reports — data never leaves your deployment boundary.
            </p>
            <ul className="space-y-3.5">
              <Feature icon="◉" label="Real-time signal monitoring across social platforms" />
              <Feature icon="◈" label="Deepfake and synthetic media verification" />
              <Feature icon="◎" label="LLM-grounded intelligence report generation" />
              <Feature icon="◬" label="GIS-mapped entity and threat intelligence" />
            </ul>
          </div>

          {/* Bottom: deployment info */}
          <div className="relative z-10">
            <div className="w-10 h-px mb-4" style={{ background: 'rgba(245,166,35,0.22)' }} />
            <p className="text-[11px] text-[#2d3748] tracking-wide">
              iDEX ADITI 4.0 · PS-18
            </p>
            <p className="text-[10px] text-[#1e2535] mt-0.5 tracking-wide">
              Anveshak v1.0.0 · Standalone Deployment
            </p>
          </div>
        </div>

        {/* ════════════════════════════════════════════════════════════════════
            RIGHT — Form panel
            ════════════════════════════════════════════════════════════════════ */}
        <div className="flex-1 flex items-center justify-center px-6 py-10 relative">

          {/* Thin amber gradient across the very top of the form panel —
              echoes the brand mark's data-horizon line */}
          <div
            className="absolute top-0 left-0 right-0 h-[2px]"
            style={{ background: 'linear-gradient(to right, transparent, rgba(245,166,35,0.28), transparent)' }}
          />

          <div className="w-full max-w-[360px] animate-fade-in">

            {/* Mobile-only compact logo (hidden on lg) */}
            <div className="lg:hidden flex items-center gap-3 mb-10">
              <BrandMark size={44} />
              <div>
                <p className="text-base font-bold tracking-[0.15em] text-white">ANVESHAK</p>
                <p
                  className="text-xs text-[#F5A623]"
                  style={{ fontFamily: "'Noto Sans Devanagari', 'Mangal', serif" }}
                >
                  अन्वेषक
                </p>
              </div>
            </div>

            {/* Form header */}
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-white tracking-tight">
                Sign in to continue
              </h2>
              <p className="text-sm mt-1.5" style={{ color: '#3d4e63' }}>
                Access your intelligence workbench
              </p>
            </div>

            {/* ── Form ── */}
            <form onSubmit={handleSubmit} className="space-y-5" noValidate>

              {/* Username */}
              <div>
                <label
                  htmlFor="username"
                  className="block text-[10px] font-semibold mb-2 tracking-[0.14em] uppercase"
                  style={{ color: '#4a5568' }}
                >
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="analyst"
                  className="
                    w-full rounded-[6px] px-3.5 py-2.5 text-sm text-white
                    placeholder:text-[#2d3748]
                    focus:outline-none transition-colors duration-150
                  "
                  style={{
                    background: '#111827',
                    border: '1px solid #1f2d3d',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = '#F5A623'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(245,166,35,0.12)' }}
                  onBlur={e  => { e.currentTarget.style.borderColor = '#1f2d3d'; e.currentTarget.style.boxShadow = 'none' }}
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="password"
                  className="block text-[10px] font-semibold mb-2 tracking-[0.14em] uppercase"
                  style={{ color: '#4a5568' }}
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="
                      w-full rounded-[6px] px-3.5 py-2.5 pr-10 text-sm text-white
                      placeholder:text-[#2d3748]
                      focus:outline-none transition-colors duration-150
                    "
                    style={{
                      background: '#111827',
                      border: '1px solid #1f2d3d',
                    }}
                    onFocus={e => { e.currentTarget.style.borderColor = '#F5A623'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(245,166,35,0.12)' }}
                    onBlur={e  => { e.currentTarget.style.borderColor = '#1f2d3d'; e.currentTarget.style.boxShadow = 'none' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4a5568] hover:text-[#F5A623] transition-colors duration-150"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? (
                      /* Eye-off icon */
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                        <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/>
                        <line x1="1" y1="1" x2="23" y2="23"/>
                      </svg>
                    ) : (
                      /* Eye icon */
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 text-xs rounded-[6px] px-3.5 py-2.5"
                  style={{ background: 'rgba(127,29,29,0.25)', border: '1px solid rgba(153,27,27,0.35)', color: '#fca5a5' }}
                >
                  {/* Warning triangle icon */}
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className="shrink-0 mt-0.5" aria-hidden>
                    <path d="M6.5 1.5 12 11H1L6.5 1.5Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/>
                    <path d="M6.5 5v2.5M6.5 9v.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/>
                  </svg>
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading || !username || !password}
                className="
                  w-full mt-1 rounded-[6px] py-2.5 px-4
                  text-sm font-semibold tracking-wide
                  flex items-center justify-center gap-2
                  transition-colors duration-150
                "
                style={{
                  background: loading || !username || !password
                    ? 'rgba(245,166,35,0.25)'
                    : '#F5A623',
                  color: loading || !username || !password
                    ? 'rgba(245,166,35,0.5)'
                    : '#1A0800',
                  cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
                }}
                onMouseEnter={e => {
                  if (!loading && username && password)
                    e.currentTarget.style.background = '#E8960E'
                }}
                onMouseLeave={e => {
                  if (!loading && username && password)
                    e.currentTarget.style.background = '#F5A623'
                }}
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" aria-hidden>
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25"/>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                    </svg>
                    Authenticating…
                  </>
                ) : (
                  <>
                    Sign in
                    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
                      <path d="M2 6.5h9M8 3l4 3.5L8 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </>
                )}
              </button>
            </form>

            {/* Footer */}
            <div className="mt-8 pt-5" style={{ borderTop: '1px solid #131c29' }}>
              <div className="flex items-center justify-center gap-2" style={{ color: '#1e2d3d' }}>
                {/* Lock icon */}
                <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden>
                  <rect x="1.5" y="4.5" width="8" height="5.5" rx="1"
                        stroke="currentColor" strokeWidth="1.1"/>
                  <path d="M3.5 4.5V3A2 2 0 0 1 7.5 3v1.5"
                        stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
                </svg>
                <p className="text-[10px] tracking-wide text-center">
                  Sovereign deployment — intelligence data never leaves this system
                </p>
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  )
}
