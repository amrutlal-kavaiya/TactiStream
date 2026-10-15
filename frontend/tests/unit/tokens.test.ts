/// <reference types="node" />
import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const css = readFileSync(`${import.meta.dirname}/../../src/styles/tokens.css`, 'utf8')

function token(name: string): string {
  const match = new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`).exec(css)
  if (!match?.[1]) throw new Error(`missing color token --${name}`)
  return match[1]
}

function luminance(hex: string): number {
  const channel = (offset: number) => {
    const c = parseInt(hex.slice(offset, offset + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

describe('design tokens', () => {
  it('use the brand Blue and Amber', () => {
    expect(token('color-blue').toUpperCase()).toBe('#3B82F6')
    expect(token('color-amber').toUpperCase()).toBe('#F59E0B')
  })

  it.each([
    ['color-text', 'color-surface'],
    ['color-text', 'color-surface-raised'],
    ['color-text-muted', 'color-surface'],
    ['color-text-muted', 'color-surface-raised'],
    ['color-link', 'color-surface-raised'],
    ['color-danger', 'color-surface-raised'],
    ['color-on-accent', 'color-blue'],
    ['color-on-accent', 'color-amber'],
  ])('%s on %s has contrast of at least 4.5:1', (fg, bg) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5)
  })
})
