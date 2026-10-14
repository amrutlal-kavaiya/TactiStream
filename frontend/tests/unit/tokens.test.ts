/// <reference types="node" />
import { readFileSync } from 'node:fs'

import type { Theme } from '@fluentui/react-components'
import { describe, expect, it } from 'vitest'

import { darkTheme, lightTheme } from '../../src/theme/brand'

const css = readFileSync(`${import.meta.dirname}/../../src/styles/tokens.css`, 'utf8')

function block(selector: string): string {
  const start = css.indexOf(`${selector} {`)
  if (start < 0) throw new Error(`missing ${selector} block`)
  return css.slice(start, css.indexOf('}', start))
}

function token(name: string, theme: 'dark' | 'light' = 'dark'): string {
  const pattern = new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`)
  const own = theme === 'light' ? pattern.exec(block("[data-theme='light']")) : null
  const match = own ?? pattern.exec(block(':root'))
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

const themes = [
  ['dark', darkTheme],
  ['light', lightTheme],
] as const

const backgrounds = ['colorNeutralBackground1', 'colorNeutralBackground2'] as const

const textTokens = [
  'colorNeutralForeground1',
  'colorNeutralForeground2',
  'colorNeutralForeground3',
  'colorBrandForeground1',
  'colorBrandForegroundLink',
] as const

describe('app tokens', () => {
  it('keep the brand team Blue and Amber', () => {
    expect(token('ts-team-blue').toUpperCase()).toBe('#3B82F6')
    expect(token('ts-team-amber').toUpperCase()).toBe('#F59E0B')
  })

  it('contain only team and pitch colours', () => {
    const names = [...css.matchAll(/--([a-z0-9-]+):/g)].map((m) => m[1])
    for (const name of names) expect(name).toMatch(/^ts-(team|pitch)-/)
  })

  it('draw pitch lines at 3:1 or more on the grass', () => {
    expect(contrast(token('ts-pitch-line'), token('ts-pitch-grass'))).toBeGreaterThanOrEqual(3)
  })
})

describe.each(themes)('%s theme contrast', (name, theme: Theme) => {
  describe.each(backgrounds)('on %s', (background) => {
    it.each(textTokens)('%s text is at least 4.5:1', (fg) => {
      expect(contrast(theme[fg], theme[background])).toBeGreaterThanOrEqual(4.5)
    })

    it.each(['ts-team-blue', 'ts-team-amber'])('%s swatch is at least 3:1', (team) => {
      expect(contrast(token(team, name), theme[background])).toBeGreaterThanOrEqual(3)
    })
  })

  it('white-on-brand button text is at least 4.5:1 at rest and on hover', () => {
    expect(contrast(theme.colorNeutralForegroundOnBrand, theme.colorBrandBackground)).toBeGreaterThanOrEqual(
      4.5,
    )
    expect(
      contrast(theme.colorNeutralForegroundOnBrand, theme.colorBrandBackgroundHover),
    ).toBeGreaterThanOrEqual(4.5)
  })
})
