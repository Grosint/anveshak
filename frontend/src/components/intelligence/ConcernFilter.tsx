import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { concernApi } from '../../api/concern'

/**
 * Concern category filter — issue #36, ADR 0001.
 *
 * Collapsed by default and fetched only when opened, because the system does
 * not tell an analyst what to be concerned about; it offers the categories
 * when they ask for them.
 *
 * Selecting a category changes which narratives are listed. It never
 * reorders them. There is deliberately no "sort by concern" control here,
 * and a test asserts the list ordering is unchanged by a selection.
 */

interface ConcernFilterProps {
  selected: string[]
  onChange: (categories: string[]) => void
}

export function ConcernFilter({ selected, onChange }: ConcernFilterProps) {
  const [open, setOpen] = useState(false)

  const { data: taxonomy } = useQuery({
    queryKey: ['concern-taxonomy'],
    queryFn: () => concernApi.taxonomy(),
    // Fetched on demand. The categories are never surfaced unprompted.
    enabled: open,
    staleTime: Infinity,
  })

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((c) => c !== id) : [...selected, id])
  }

  return (
    <div className="text-[11px]">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="text-text-muted hover:text-text-primary transition-colors"
      >
        Filter by concern category{selected.length > 0 && ` (${selected.length})`}
      </button>

      {open && (
        <div className="mt-2 p-2 rounded border border-anveshak-border bg-anveshak-bg">
          {!taxonomy ? (
            <p className="text-text-muted">Loading categories...</p>
          ) : taxonomy.categories.length === 0 ? (
            <p className="text-text-muted">No taxonomy is configured.</p>
          ) : (
            <>
              <ul className="space-y-1.5">
                {taxonomy.categories.map((category) => (
                  <li key={category.id}>
                    <label className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selected.includes(category.id)}
                        onChange={() => toggle(category.id)}
                        className="mt-0.5 accent-anveshak-accent"
                        aria-label={category.label}
                      />
                      <span>
                        <span className="block text-text-primary">{category.label}</span>
                        <span className="block text-[10px] text-text-muted">
                          {category.definition}
                        </span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              <p className="text-[10px] text-text-muted mt-2 pt-2 border-t border-anveshak-border/50">
                Filtering changes which narratives are listed. The order stays as it was:
                by how a narrative is spreading, not by category. Taxonomy v
                {taxonomy.version}
                {taxonomy.owner && `, owned by the ${taxonomy.owner}`}.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}
