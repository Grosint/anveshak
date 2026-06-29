interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  if (totalPages <= 1) return null

  const pages = buildPageNumbers(page, totalPages)

  return (
    <div className="flex items-center justify-between pt-3 border-t border-anveshak-border">
      <span className="text-xs text-text-secondary">
        {Math.min(page * pageSize + 1, total)}–{Math.min((page + 1) * pageSize, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
          className="px-2 py-1 text-xs rounded text-text-secondary hover:text-text-primary hover:bg-anveshak-muted disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          aria-label="Previous page"
        >
          &lt;
        </button>
        {pages.map((p, i) =>
          p === '...' ? (
            <span key={`ellipsis-${i}`} className="px-1 text-xs text-text-secondary">...</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p as number)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                p === page
                  ? 'bg-anveshak-accent text-white'
                  : 'text-text-secondary hover:text-text-primary hover:bg-anveshak-muted'
              }`}
            >
              {(p as number) + 1}
            </button>
          ),
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1}
          className="px-2 py-1 text-xs rounded text-text-secondary hover:text-text-primary hover:bg-anveshak-muted disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          aria-label="Next page"
        >
          &gt;
        </button>
      </div>
    </div>
  )
}

/** Build page number array with ellipsis for large ranges. */
function buildPageNumbers(current: number, total: number): (number | '...')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i)

  const pages: (number | '...')[] = [0]

  if (current > 2) pages.push('...')

  const start = Math.max(1, current - 1)
  const end = Math.min(total - 2, current + 1)
  for (let i = start; i <= end; i++) pages.push(i)

  if (current < total - 3) pages.push('...')

  pages.push(total - 1)
  return pages
}
