/**
 * Type-specific card body for a Mobilization signal — issue #33.
 *
 * The exact matched phrase is always shown, even when a date and place were
 * extracted, because the phrase is the evidence and the extractions are
 * conveniences an analyst may need to correct.
 *
 * Nothing here says an event will occur. The card reports what was publicly
 * said, and the analyst decides what that means. See ADR 0001.
 */

export interface MobilizationEvidence {
  matched_phrase?: string
  pattern_id?: string
  lexicon_version?: number
  extracted_date?: string | null
  extracted_place?: string | null
  item_count?: number
  content_item_ids?: string[]
}

export function MobilizationBody({
  evidence,
}: {
  evidence: MobilizationEvidence | null | undefined
}) {
  if (!evidence) return null

  return (
    <div className="px-4 pb-2 space-y-2">
      {evidence.matched_phrase && (
        <blockquote className="text-[11px] text-text-secondary italic border-l-2 border-anveshak-border pl-2 leading-snug">
          {evidence.matched_phrase}
        </blockquote>
      )}

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        <span className="text-text-secondary">
          Date stated:{' '}
          <span className="font-semibold text-text-primary">
            {evidence.extracted_date ?? 'none in the text'}
          </span>
        </span>
        <span className="text-text-secondary">
          Place stated:{' '}
          <span className="font-semibold text-text-primary">
            {evidence.extracted_place ?? 'none in the text'}
          </span>
        </span>
        {evidence.item_count !== undefined && (
          <span className="text-text-secondary">
            <span className="font-semibold text-text-primary">{evidence.item_count}</span> items
          </span>
        )}
      </div>

      <p className="text-[10px] text-text-muted">
        Reports what was publicly said. Check the phrase and correct the extraction if it is
        wrong.
        {evidence.pattern_id && ` Pattern ${evidence.pattern_id}`}
        {evidence.lexicon_version !== undefined && `, lexicon v${evidence.lexicon_version}.`}
      </p>
    </div>
  )
}
