// Captures the README/submission screenshots from a running app: `BASE_URL=http://localhost:8000 npm run screenshots`.
import { mkdir } from 'node:fs/promises'
import { chromium } from '@playwright/test'

const baseUrl = process.env.BASE_URL ?? 'http://localhost:8000'
const outDir = new URL('../../docs/screenshots/', import.meta.url)
const card = 'Blue 8 played a forward pass to Blue 11 (13.1 m forward).'

await mkdir(outDir, { recursive: true })
const browser = await chromium.launch()

async function capture(theme, withDrawer) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.addInitScript((value) => localStorage.setItem('tactistream.theme', value), theme)
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Start demo match' }).click()
  await page.getByText(card).waitFor({ timeout: 10_000 })
  if (withDrawer) {
    await page.getByRole('button', { name: 'evt-0042' }).first().click()
    await page.getByRole('dialog', { name: 'Evidence evt-0042' }).filter({ hasText: 'blue-08' }).waitFor()
    await page.waitForTimeout(400)
  }
  const name = withDrawer ? 'drawer' : theme
  await page.screenshot({ path: new URL(`001-fluent-${name}.png`, outDir).pathname })
  await page.request.post(`${baseUrl}/api/matches/demo-blue-amber-001/control`, { data: { action: 'reset' } })
  await page.close()
}

try {
  await capture('dark', false)
  await capture('light', false)
  await capture('dark', true)
} finally {
  await browser.close()
}
