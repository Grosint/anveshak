/**
 * Generated API types contract - `src/api/generated/schema.ts` is exactly what
 * openapi-typescript produces from the committed `openapi.json`.
 *
 * Seam 10: Backend Pydantic → Frontend TypeScript interface.
 *
 * tests/contracts/test_openapi_schema_committed.py checks that openapi.json
 * matches the API service. This checks the second link: a hand edit to
 * schema.ts, or an openapi.json regenerated without regenerating the types,
 * would otherwise let the frontend compile against a shape the API never
 * serves. Either failure is fixed by `make gen-api-types`.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect } from 'vitest'
import openapiTS, { astToString, COMMENT_HEADER } from 'openapi-typescript'

// import.meta.url is an http: URL under jsdom, so resolve from the file path.
const generatedDir = resolve(__dirname, '../../api/generated')
const schemaPath = resolve(generatedDir, 'openapi.json')
const typesPath = resolve(generatedDir, 'schema.ts')

describe('generated API types', () => {
  it('match the committed OpenAPI schema', async () => {
    // Same call and defaults as the openapi-typescript CLI behind `npm run gen:api`.
    const schema = readFileSync(schemaPath, 'utf8')
    const expected = `${COMMENT_HEADER}${astToString(await openapiTS(schema))}`

    const committed = readFileSync(typesPath, 'utf8')

    expect(
      committed === expected,
      'src/api/generated/schema.ts is stale. Run `make gen-api-types` and commit the result.',
    ).toBe(true)
  })
})
