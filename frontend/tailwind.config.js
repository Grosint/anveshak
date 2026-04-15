/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  // Toggled by ThemeContext: adds/removes 'light' class on <html>
  // (we default to dark, so we invert the convention — 'light' class = light mode)
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // All tokens driven by CSS variables so theme toggle is instant with no re-render
        'anveshak-bg':     'var(--anveshak-bg)',
        'anveshak-card':   'var(--anveshak-card)',
        'anveshak-border': 'var(--anveshak-border)',
        'anveshak-accent': 'var(--anveshak-accent)',
        'anveshak-muted':  'var(--anveshak-muted)',
        'text-primary':    'var(--text-primary)',
        'text-secondary':  'var(--text-secondary)',
        'text-muted':      'var(--text-muted)',
        'signal-high':     'var(--signal-high)',
        'signal-med':      'var(--signal-med)',
        'signal-low':      'var(--signal-low)',
        'cred-high':       'var(--credibility-high)',
        'cred-mid':        'var(--credibility-mid)',
        'cred-low':        'var(--credibility-low)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '6px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.4)',
      },
    },
  },
  plugins: [],
}
