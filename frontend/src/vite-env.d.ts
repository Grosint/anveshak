/// <reference types="vite/client" />

declare global {
  interface Window {
    /**
     * Base map style URL, injected at deploy time.
     *
     * A sovereign or air-gapped deployment points this at its own tile server
     * so the workbench never reaches a public CDN. Unset means the default
     * public style in `GeoMap.tsx`.
     */
    __ANVESHAK_MAP_TILE_URL__?: string
  }
}

export {}
