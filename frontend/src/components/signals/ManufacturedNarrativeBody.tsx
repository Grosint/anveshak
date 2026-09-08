/**
 * Type-specific card body for a Manufactured Narrative signal — issue #32.
 *
 * A timeline, an evidence list and an extracted date cannot share one
 * generic card, so each signal type that needs one gets a body.
 *
 * This body shows the repeated claim across accounts and the arithmetic that
 * fired the signal, including each threshold and the margin by which it was
 * crossed. The wording states that the spread lacks independent sourcing and
 * never that the narrative is false: nothing measured here is about truth.
 * See ADR 0001.
 */

export interface ManufacturedEvidence {
  item_count?: number
  account_count?: number
  independent_source_count?: number
  thresholds?: {
    min_item_count?: number
    min_account_count?: number
    max_independent_sources?: number
  }
  margins?: {
    item_count?: number
    account_count?: number
    independent_sources_below_ceiling?: number
  }
  repeated_claim?: string
  content_item_ids?: string[]
}

function Crossed({
  measured,
  unit,
  gate,
  margin,
}: {
  measured: number
  unit: string
  gate?: number
  margin?: number
}) {
  return (
    <span className="text-[11px] text-text-secondary">
      <span className="font-semibold text-text-primary">
        {measured} {unit}
      </span>
      {gate !== undefined && <span className="text-text-muted"> vs gate {gate}</span>}
      {margin !== undefined && margin >= 0 && (
        <span className="text-text-muted"> (+{margin})</span>
      )}
    </span>
  )
}

export function ManufacturedNarrativeBody({
  evidence,
}: {
  evidence: ManufacturedEvidence | null | undefined
}) {
  if (!evidence) return null

  const thresholds = evidence.thresholds ?? {}
  const margins = evidence.margins ?? {}

  return (
    <div className="px-4 pb-2 space-y-2">
      {evidence.repeated_claim && (
        <blockquote className="text-[11px] text-text-secondary italic border-l-2 border-anveshak-border pl-2 leading-snug">
          {evidence.repeated_claim}
        </blockquote>
      )}

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {evidence.item_count !== undefined && (
          <Crossed
            measured={evidence.item_count}
            unit="items"
            gate={thresholds.min_item_count}
            margin={margins.item_count}
          />
        )}
        {evidence.account_count !== undefined && (
          <Crossed
            measured={evidence.account_count}
            unit="accounts"
            gate={thresholds.min_account_count}
            margin={margins.account_count}
          />
        )}
        {evidence.independent_source_count !== undefined && (
          <Crossed
            measured={evidence.independent_source_count}
            unit="independent sources"
            gate={thresholds.max_independent_sources}
          />
        )}
      </div>

      <p className="text-[11px] text-text-muted">
        Spread lacks independent sourcing.
        {evidence.content_item_ids && evidence.content_item_ids.length > 0 &&
          ` ${evidence.content_item_ids.length} items carry the claim.`}
      </p>
    </div>
  )
}
