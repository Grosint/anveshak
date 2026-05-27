import { useState } from 'react'
import { CatalogSuggestionsPanel } from './CatalogSuggestionsPanel'
import { DiscoveredSourcesPanel } from './DiscoveredSourcesPanel'

type Tab = 'catalog' | 'discovered'

export function SourceDiscoveryTab({ topicId }: { topicId: string }) {
  const [tab, setTab] = useState<Tab>('catalog')

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-anveshak-border pb-2">
        <button
          className={`text-sm px-3 py-1.5 rounded-t ${
            tab === 'catalog'
              ? 'bg-anveshak-accent/10 text-anveshak-accent border-b-2 border-anveshak-accent'
              : 'text-text-secondary hover:text-text-primary'
          }`}
          onClick={() => setTab('catalog')}
        >
          Curated Catalog
        </button>
        <button
          className={`text-sm px-3 py-1.5 rounded-t ${
            tab === 'discovered'
              ? 'bg-anveshak-accent/10 text-anveshak-accent border-b-2 border-anveshak-accent'
              : 'text-text-secondary hover:text-text-primary'
          }`}
          onClick={() => setTab('discovered')}
        >
          Discovered
        </button>
      </div>

      {tab === 'catalog' && <CatalogSuggestionsPanel topicId={topicId} />}
      {tab === 'discovered' && <DiscoveredSourcesPanel topicId={topicId} />}
    </div>
  )
}
