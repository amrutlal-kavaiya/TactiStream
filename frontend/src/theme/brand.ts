import { type BrandVariants, createDarkTheme, createLightTheme, type Theme } from '@fluentui/react-components'

/** TactiStream Blue (#3B82F6) at step 80, shaded towards near-black below and tinted towards white above. */
export const brandRamp: BrandVariants = {
  10: '#060E20',
  20: '#0D1C39',
  30: '#132B54',
  40: '#1B3B72',
  50: '#224C92',
  60: '#2B5EB4',
  70: '#3371D6',
  80: '#3B82F6',
  90: '#4F8FF7',
  100: '#629BF8',
  110: '#78A9F9',
  120: '#8DB7FA',
  130: '#A3C4FB',
  140: '#BAD3FC',
  150: '#D2E2FD',
  160: '#E9F1FE',
}

// #3B82F6 is lighter than Fluent's default step 80, so white-on-brand and brand-on-white text would fall below
// 4.5:1. Brand fills and brand text move to darker steps; strokes and tints keep the factory values.
const brandFills: Partial<Theme> = {
  colorBrandBackground: brandRamp[60],
  colorBrandBackgroundPressed: brandRamp[40],
  colorBrandBackgroundSelected: brandRamp[50],
  colorCompoundBrandBackground: brandRamp[60],
  colorCompoundBrandBackgroundPressed: brandRamp[40],
}

const lightOverrides: Partial<Theme> = {
  ...brandFills,
  colorBrandBackgroundHover: brandRamp[50],
  colorCompoundBrandBackgroundHover: brandRamp[50],
  colorBrandForeground1: brandRamp[60],
  colorBrandForeground2: brandRamp[50],
  colorBrandForeground2Hover: brandRamp[40],
  colorBrandForegroundLink: brandRamp[60],
  colorBrandForegroundLinkHover: brandRamp[50],
  colorBrandForegroundLinkSelected: brandRamp[60],
  colorCompoundBrandForeground1: brandRamp[60],
  colorCompoundBrandForeground1Hover: brandRamp[50],
  colorCompoundBrandForeground1Pressed: brandRamp[40],
  colorBrandForegroundOnLight: brandRamp[60],
  colorBrandForegroundOnLightHover: brandRamp[50],
  colorBrandForegroundOnLightPressed: brandRamp[40],
}

const darkOverrides: Partial<Theme> = {
  ...brandFills,
  colorBrandBackgroundHover: brandRamp[70],
}

export const lightTheme: Theme = { ...createLightTheme(brandRamp), ...lightOverrides }
export const darkTheme: Theme = { ...createDarkTheme(brandRamp), ...darkOverrides }

export type ThemeName = 'dark' | 'light'

export const themes: Record<ThemeName, Theme> = { dark: darkTheme, light: lightTheme }
