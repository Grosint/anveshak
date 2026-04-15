# Pattern: CSS Variable Dark/Light Theming (React + Tailwind)

## When to load: adding or modifying theme support in the frontend

---

## The pattern

Dark mode as default, light mode opt-in. All colour tokens are CSS custom properties on
`:root`. The `html.light` class overrides them. Tailwind reads every colour via `var(--...)`.
No `dark:` prefixes anywhere — switching theme just swaps the `:root` values.

```css
/* index.css */
:root {
  /* dark is default — no class needed */
  --anveshak-bg:       #0f1117;
  --anveshak-card:     #1a1f2e;
  --anveshak-border:   #2d3748;
  --anveshak-accent:   #3b82f6;
  --text-primary:      #f1f5f9;
  --text-muted:        #64748b;
  --cred-high:         #10b981;
  --cred-mid:          #f59e0b;
  --cred-low:          #ef4444;
  /* ... all tokens */
}

html.light {
  --anveshak-bg:       #f1f5f9;
  --anveshak-card:     #ffffff;
  --anveshak-border:   #e2e8f0;
  --text-primary:      #0f172a;
  --text-muted:        #64748b;
  /* override every variable that changes */
}
```

```js
// tailwind.config.js — point every colour at a CSS var
theme: {
  extend: {
    colors: {
      'anveshak-bg':     'var(--anveshak-bg)',
      'anveshak-card':   'var(--anveshak-card)',
      'anveshak-accent': 'var(--anveshak-accent)',
      'text-primary':    'var(--text-primary)',
      'cred-high':       'var(--cred-high)',
      // ...
    },
  },
},
```

```tsx
// ThemeContext.tsx
const STORAGE_KEY = 'anveshak_theme'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    (localStorage.getItem(STORAGE_KEY) as 'dark' | 'light') ?? 'dark'
  )

  useEffect(() => {
    if (theme === 'light') {
      document.documentElement.classList.add('light')
    } else {
      document.documentElement.classList.remove('light')
    }
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
```

## Toggle button in sidebar

```tsx
// Layout.tsx — icon switches based on current theme
const { theme, toggleTheme } = useTheme()
<button onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
  {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
</button>
```

## Why this approach

- **No `dark:` class proliferation** — every component just uses `text-text-primary`, never
  `text-gray-900 dark:text-gray-100`. Single source of truth in CSS.
- **Instant switch** — changing `html.light` is one DOM mutation; browser repaints atomically.
- **Tailwind IntelliSense works** — `bg-anveshak-card` is a real Tailwind token.
- **No flash on load** — set `document.documentElement.className = savedTheme === 'light' ? 'light' : ''`
  in a `<script>` tag in `index.html` before React mounts to prevent FOUC.

## PostCSS gotcha

PostCSS config must use `module.exports`, **not** `export default`:
```js
// postcss.config.js — WRONG on Node 18 CJS
export default { plugins: { tailwindcss: {}, autoprefixer: {} } }

// CORRECT
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }
```
`export default` triggers `SyntaxError: Unexpected token 'export'` on Node 18 CJS resolution.

## tailwind.config.js must also use module.exports

```js
// tailwind.config.js
module.exports = {
  darkMode: 'class',   // 'class' strategy — required for html.light toggle
  content: ['./src/**/*.{ts,tsx}'],
  theme: { extend: { colors: { ... } } },
}
```
