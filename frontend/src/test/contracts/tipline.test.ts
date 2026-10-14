/**
 * Tipline ingest contract - the frontend type is the generated one.
 *
 * Seam 10: Backend Pydantic → Frontend TypeScript interface.
 *
 * These checks are compile-time only: expectTypeOf does nothing at runtime.
 * Unlike the rest of src/test/, this directory is type-checked by
 * `tsc -p tsconfig.contracts.json` as part of `npm run build`. Rename a field
 * on TiplineIngestResponse in services/api, run `make gen-api-types`, and this
 * file stops compiling, so the build fails rather than a reader getting
 * `undefined`.
 */
import { describe, it, expectTypeOf } from 'vitest'
import type { TiplineIngestRequest, TiplineIngestResponse } from '../../api/tipline'

describe('TiplineIngestResponse contract', () => {
  it('has exactly the fields the API returns', () => {
    expectTypeOf<TiplineIngestResponse>().toEqualTypeOf<{
      id: string
      content_hash: string
      status: 'queued' | 'duplicate'
      duplicate: boolean
    }>()
  })
})

describe('TiplineIngestRequest contract', () => {
  it('requires the text and the topic', () => {
    expectTypeOf<TiplineIngestRequest['text']>().toEqualTypeOf<string>()
    expectTypeOf<TiplineIngestRequest['topic_id']>().toEqualTypeOf<string>()
  })
})
