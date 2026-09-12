/**
 * Theme context object and hook.
 *
 * Separate from `ThemeContext.tsx` so that file exports only the provider
 * component, which is what Vite's fast refresh needs to hot-swap it.
 */
import { createContext, useContext } from 'react'

export type Theme = 'dark' | 'light'

export interface ThemeContextValue {
  theme: Theme
  toggle: () => void
  isDark: boolean
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
