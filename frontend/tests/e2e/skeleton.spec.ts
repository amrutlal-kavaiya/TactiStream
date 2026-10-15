import { expect, type Page, test } from '@playwright/test'

import { seriousViolations } from './axe.ts'

const CARD_TEXT = 'Blue 8 played a forward pass to Blue 11 (13.1 m forward).'

async function startDemo(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Start demo match' }).click()
  const card = page.getByTestId('insight-card')
  await expect(card.getByText(CARD_TEXT)).toBeVisible({ timeout: 6000 })
  return card
}

test('Start demo match shows a verified card whose evidence opens; Pause and Reset hide it', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Start demo match' }).click()

  await expect(page.getByTestId('source-badge')).toHaveText('Synthetic')
  const card = page.getByTestId('insight-card')
  await expect(card.getByText(CARD_TEXT)).toBeVisible({ timeout: 6000 })
  await expect(card).toContainText('Verified fact')

  const chip = card.getByRole('button', { name: 'evt-0042' })
  await chip.click()
  const drawer = page.getByRole('dialog', { name: 'Evidence evt-0042' })
  await expect(drawer).toContainText('pass')
  await expect(drawer).toContainText('blue-08')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(chip).toBeFocused()

  await chip.focus()
  await page.keyboard.press('Enter')
  await expect(drawer).toContainText('blue-08')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(chip).toBeFocused()

  await page.getByRole('button', { name: 'Pause' }).click()
  await page.getByRole('button', { name: 'Reset' }).click()
  await expect(card).toBeHidden()
})

test.describe('theme', () => {
  test.use({ colorScheme: 'dark' })

  test('defaults to dark; the header toggle switches to light and persists across reload', async ({
    page,
  }) => {
    await page.goto('/')
    const shell = page.getByTestId('app-shell')
    const toggle = page.getByRole('button', { name: 'Light theme' })
    await expect(shell).toHaveAttribute('data-theme', 'dark')
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')

    await toggle.click()
    await expect(shell).toHaveAttribute('data-theme', 'light')
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(await page.evaluate(() => localStorage.getItem('tactistream.theme'))).toBe('light')

    await page.reload()
    await expect(shell).toHaveAttribute('data-theme', 'light')
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')

    await toggle.click()
    await expect(shell).toHaveAttribute('data-theme', 'dark')
    await page.reload()
    await expect(shell).toHaveAttribute('data-theme', 'dark')
  })
})

for (const theme of ['dark', 'light'] as const) {
  test(`has no serious or critical axe violations in the ${theme} theme (card and evidence drawer)`, async ({
    page,
  }) => {
    await page.addInitScript((value) => {
      localStorage.setItem('tactistream.theme', value)
    }, theme)
    const card = await startDemo(page)
    await expect(page.getByTestId('app-shell')).toHaveAttribute('data-theme', theme)
    expect(await seriousViolations(page)).toEqual([])

    await card.getByRole('button', { name: 'evt-0042' }).click()
    await expect(page.getByRole('dialog', { name: 'Evidence evt-0042' })).toContainText('blue-08')
    expect(await seriousViolations(page)).toEqual([])
  })
}
