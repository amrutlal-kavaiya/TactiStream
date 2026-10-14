import { expect, test } from '@playwright/test'

const CARD_TEXT = 'Blue 8 played a forward pass to Blue 11 (13.1 m forward).'

test('Start demo match shows a verified card whose evidence opens; Pause and Reset hide it', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Start demo match' }).click()

  await expect(page.getByTestId('source-badge')).toHaveText('Synthetic')
  const card = page.getByTestId('insight-card')
  await expect(card.getByText(CARD_TEXT)).toBeVisible({ timeout: 6000 })
  await expect(card).toContainText('Verified fact')

  await card.getByRole('button', { name: 'evt-0042' }).click()
  const drawer = page.getByRole('dialog', { name: 'Evidence evt-0042' })
  await expect(drawer).toContainText('pass')
  await expect(drawer).toContainText('blue-08')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()

  await page.getByRole('button', { name: 'Pause' }).click()
  await page.getByRole('button', { name: 'Reset' }).click()
  await expect(card).toBeHidden()
})
