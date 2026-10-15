import { createDarkTheme, createLightTheme, Tooltip } from '@fluentui/react-components'
import { act, render, renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { brandRamp, darkTheme, lightTheme } from '../../src/theme/brand'
import { AppShell } from '../../src/theme/AppShell'
import { THEME_STORAGE_KEY, useThemePreference } from '../../src/theme/useThemePreference'

function preferLight(light: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: light && query === '(prefers-color-scheme: light)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
}

function luminance(hex: string): number {
  const channel = (offset: number) => {
    const c = parseInt(hex.slice(offset, offset + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
}

beforeEach(() => {
  localStorage.clear()
  preferLight(false)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useThemePreference', () => {
  it('defaults to dark', () => {
    const { result } = renderHook(() => useThemePreference())
    expect(result.current.themeName).toBe('dark')
  })

  it('toggles to light and persists the choice', () => {
    const { result } = renderHook(() => useThemePreference())
    act(() => {
      result.current.toggleTheme()
    })
    expect(result.current.themeName).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
    expect(THEME_STORAGE_KEY).toBe('tactistream.theme')
  })

  it('prefers the stored value over prefers-color-scheme', () => {
    preferLight(true)
    localStorage.setItem('tactistream.theme', 'dark')
    const { result } = renderHook(() => useThemePreference())
    expect(result.current.themeName).toBe('dark')
  })

  it('follows prefers-color-scheme: light when nothing is stored', () => {
    preferLight(true)
    const { result } = renderHook(() => useThemePreference())
    expect(result.current.themeName).toBe('light')
  })

  it('ignores an invalid stored value', () => {
    localStorage.setItem('tactistream.theme', 'sepia')
    const { result } = renderHook(() => useThemePreference())
    expect(result.current.themeName).toBe('dark')
  })
})

describe('brand theme', () => {
  const keys = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160] as const

  it('is a 16-step ramp centred on TactiStream Blue at step 80', () => {
    expect(Object.keys(brandRamp).map(Number)).toEqual([...keys])
    expect(brandRamp[80]).toBe('#3B82F6')
  })

  it('gets monotonically lighter', () => {
    const lum = keys.map((k) => luminance(brandRamp[k]))
    for (let i = 1; i < lum.length; i++) expect(lum[i]).toBeGreaterThan(lum[i - 1] ?? 0)
  })

  it.each([
    ['dark', darkTheme, createDarkTheme],
    ['light', lightTheme, createLightTheme],
  ] as const)(
    'builds the %s theme from the Fluent factory, overriding only brand tokens',
    (_, theme, factory) => {
      const base = factory(brandRamp)
      expect(Object.keys(theme).sort()).toEqual(Object.keys(base).sort())
      const overridden = Object.keys(base).filter(
        (k) => theme[k as keyof typeof theme] !== base[k as keyof typeof base],
      )
      expect(overridden.length).toBeGreaterThan(0)
      for (const key of overridden) expect(key).toMatch(/^color(Compound)?Brand/)
    },
  )
})

describe('AppShell', () => {
  function Shell() {
    const { themeName, toggleTheme } = useThemePreference()
    return (
      <AppShell
        themeName={themeName}
        header={
          <button type="button" onClick={toggleTheme}>
            toggle
          </button>
        }
        commandBar={<div>commands</div>}
        stage={<div>stage</div>}
        rail={<div>rail</div>}
      />
    )
  }

  it('applies the dark theme by default and switches to light', async () => {
    const user = userEvent.setup()
    render(<Shell />)
    const shell = screen.getByTestId('app-shell')
    expect(shell).toHaveAttribute('data-theme', 'dark')
    expect(screen.getByRole('banner')).toHaveTextContent('toggle')
    expect(screen.getByRole('main')).toHaveTextContent('stage')
    expect(screen.getByRole('complementary')).toHaveTextContent('rail')

    await user.click(screen.getByRole('button', { name: 'toggle' }))
    expect(shell).toHaveAttribute('data-theme', 'light')
    expect(localStorage.getItem('tactistream.theme')).toBe('light')
  })

  it('does not size the portal mount nodes to the viewport (they would overlay the page)', () => {
    render(
      <AppShell
        themeName="dark"
        header={
          <Tooltip content="hint" relationship="description">
            <button type="button">with tooltip</button>
          </Tooltip>
        }
        commandBar={null}
        stage={null}
        rail={null}
      />,
    )
    const portals = document.querySelectorAll<HTMLElement>('[data-portal-node]')
    expect(portals.length).toBeGreaterThan(0)
    const rules = [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules])
    for (const portal of portals) {
      const sizing = rules
        .filter(
          (rule): rule is CSSStyleRule => rule instanceof CSSStyleRule && portal.matches(rule.selectorText),
        )
        .filter((rule) => rule.style.minHeight || rule.style.height)
        .map((rule) => rule.cssText)
      expect(sizing).toEqual([])
    }
  })
})
