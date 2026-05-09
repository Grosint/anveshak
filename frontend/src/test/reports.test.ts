/**
 * Unit tests for confidence badge logic — imports the REAL function from lib/domain.
 */
import { describe, it, expect } from 'vitest'
import { confidenceVariant } from '../lib/domain'

describe('confidenceVariant', () => {
  it('high confidence → success', () => expect(confidenceVariant(0.85)).toBe('success'))
  it('medium confidence → warning', () => expect(confidenceVariant(0.55)).toBe('warning'))
  it('low confidence → danger', () => expect(confidenceVariant(0.2)).toBe('danger'))
  it('boundary 0.7 → success', () => expect(confidenceVariant(0.7)).toBe('success'))
  it('boundary 0.4 → warning', () => expect(confidenceVariant(0.4)).toBe('warning'))
})
