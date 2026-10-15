import { readFileSync } from 'node:fs'

import { type APIRequestContext, expect, type Locator, type Page, test } from '@playwright/test'

import { seriousViolations } from './axe.ts'

// Matches TACTISTREAM_PRESENTER_KEY in playwright.config.ts.
const KEY = 'e2e-key'
const headers = { 'X-Presenter-Key': KEY }
const fixture = (name: string) => new URL(`./fixtures/${name}`, import.meta.url).pathname
const BACKUP_URL = 'https://youtu.be/e2e-backup'

/** The slice of `HTMLVideoElement` read in the page; this tsconfig has no DOM lib. */
interface VideoState {
  readyState: number
  textTracks: ArrayLike<{ kind: string; mode: string }>
  seekable: { length: number; end: (index: number) => number }
}

async function resetMedia(request: APIRequestContext) {
  for (const slot of ['main', 'backup', 'captions']) {
    expect((await request.delete(`/api/presenter/media/${slot}`, { headers })).ok()).toBe(true)
  }
  expect((await request.put('/api/presenter/publish', { headers, data: { published: false } })).ok()).toBe(
    true,
  )
}

async function publishFixtures(request: APIRequestContext) {
  const main = await request.put(
    '/api/presenter/media/main?filename=sample.mp4&duration_s=2&width=320&height=180',
    {
      headers: { ...headers, 'Content-Type': 'video/mp4' },
      data: readFileSync(fixture('sample.mp4')),
    },
  )
  expect(main.ok()).toBe(true)
  const captions = await request.put('/api/presenter/media/captions?filename=sample.vtt', {
    headers: { ...headers, 'Content-Type': 'text/vtt' },
    data: readFileSync(fixture('sample.vtt')),
  })
  expect(captions.ok()).toBe(true)
  expect(
    (await request.put('/api/presenter/media/backup', { headers, data: { url: BACKUP_URL } })).ok(),
  ).toBe(true)
  expect((await request.put('/api/presenter/publish', { headers, data: { published: true } })).ok()).toBe(
    true,
  )
}

async function unlock(page: Page, key = KEY) {
  await page.goto('/presenter')
  await page.getByLabel('Presenter key').fill(key)
  await page.getByRole('button', { name: 'Unlock' }).click()
}

/** Loads `path` and waits until the header has settled on whether demo media is published. */
async function gotoJudgePage(page: Page, path: string) {
  const config = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/config')
  await page.goto(path)
  await config
}

async function expectPlayableWithCaptions(video: Locator) {
  await expect
    .poll(() => video.evaluate((v: VideoState) => v.readyState), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(2)
  await expect
    .poll(() =>
      video.evaluate((v: VideoState) => Array.from(v.textTracks, (track) => `${track.kind}:${track.mode}`)),
    )
    .toEqual(['captions:showing'])
  // Seekable beyond the first second means the server answered Range requests.
  expect(
    await video.evaluate((v: VideoState) => (v.seekable.length > 0 ? v.seekable.end(0) : 0)),
  ).toBeGreaterThan(1)
}

test.beforeEach(async ({ request }) => {
  await resetMedia(request)
})

test.afterEach(async ({ request }) => {
  await resetMedia(request)
})

test('a wrong presenter key is refused and stores nothing', async ({ page, request }) => {
  await unlock(page, 'not-the-key')
  await expect(page.getByText('That presenter key was refused.')).toBeVisible()
  await expect(page.getByRole('heading', { name: '1. Rehearse' })).toBeHidden()

  const refused = await request.put('/api/presenter/media/main', {
    headers: { 'X-Presenter-Key': 'not-the-key', 'Content-Type': 'video/mp4' },
    data: readFileSync(fixture('sample.mp4')),
  })
  expect(refused.status()).toBe(401)
  expect(await (await request.get('/api/presenter/state', { headers })).json()).toMatchObject({ slots: {} })
})

test('presenter uploads and publishes; judges watch with captions; unpublish hides it again', async ({
  page,
}) => {
  await unlock(page)
  await expect(page.getByRole('heading', { name: '1. Rehearse' })).toBeVisible()

  const main = page.getByRole('region', { name: 'Main demo video' })
  await main.getByLabel('Choose file').setInputFiles(fixture('sample.mp4'))
  await expect(main.getByText('320×180')).toBeVisible()
  await expect(main.getByText('0:02')).toBeVisible()
  await expect(main.getByText('Duration outside 1:50–1:59')).toBeVisible()
  await expect(main.getByText('Not 1920×1080')).toBeVisible()
  await main.getByRole('button', { name: 'Upload' }).click()
  await expect(main.getByText('Selected — not uploaded yet')).toBeHidden()
  await expect(main.getByText('sample.mp4')).toBeVisible()

  const captions = page.getByRole('region', { name: 'Captions' })
  await captions.getByLabel('Choose file').setInputFiles(fixture('sample.vtt'))
  await captions.getByRole('button', { name: 'Upload' }).click()
  await expect(captions.getByText('sample.vtt')).toBeVisible()

  const backup = page.getByRole('region', { name: 'Backup recording' })
  await backup.getByLabel(/YouTube URL/).fill(BACKUP_URL)
  await backup.getByRole('button', { name: 'Save link' }).click()
  await expect(backup.getByRole('link', { name: BACKUP_URL })).toBeVisible()

  await gotoJudgePage(page, '/')
  await expect(page.getByRole('button', { name: 'Watch demo video' })).toBeHidden()
  await gotoJudgePage(page, '/watch')
  await expect(page.getByText('The demo video is not published yet')).toBeVisible()

  await page.goto('/presenter')
  const publish = page.getByRole('switch', { name: 'Publish to judges' })
  await publish.click()
  await expect(publish).toBeChecked()

  await gotoJudgePage(page, '/')
  await page.getByRole('banner').getByRole('button', { name: 'Watch demo video' }).click()
  const dialog = page.getByRole('dialog', { name: 'Demo video' })
  await expectPlayableWithCaptions(dialog.locator('video'))
  await expect(dialog.getByRole('link', { name: 'Backup recording' })).toHaveAttribute('href', BACKUP_URL)
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()

  await gotoJudgePage(page, '/watch')
  await expectPlayableWithCaptions(page.locator('video'))
  await expect(page.getByRole('link', { name: 'Backup recording' })).toHaveAttribute('href', BACKUP_URL)

  await page.goto('/presenter')
  await publish.click()
  await expect(publish).not.toBeChecked()
  await gotoJudgePage(page, '/')
  await expect(page.getByRole('button', { name: 'Watch demo video' })).toBeHidden()
  await gotoJudgePage(page, '/watch')
  await expect(page.getByText('The demo video is not published yet')).toBeVisible()
  await expect(page.locator('video')).toHaveCount(0)
})

for (const theme of ['dark', 'light'] as const) {
  test(`/presenter, /watch and the video dialog have no serious or critical axe violations (${theme})`, async ({
    page,
    request,
  }) => {
    await publishFixtures(request)
    await page.addInitScript(
      ([value, key]) => {
        localStorage.setItem('tactistream.theme', value)
        sessionStorage.setItem('tactistream.presenter.key', key)
      },
      [theme, KEY] as const,
    )

    await page.goto('/presenter')
    await expect(page.getByRole('region', { name: 'Main demo video' }).getByText('sample.mp4')).toBeVisible()
    await expect(page.getByTestId('app-shell')).toHaveAttribute('data-theme', theme)
    expect(await seriousViolations(page)).toEqual([])

    await gotoJudgePage(page, '/watch')
    await expect(page.getByRole('link', { name: 'Backup recording' })).toBeVisible()
    expect(await seriousViolations(page)).toEqual([])

    await gotoJudgePage(page, '/')
    await page.getByRole('button', { name: 'Watch demo video' }).click()
    await expect(page.getByRole('dialog', { name: 'Demo video' }).locator('video')).toBeVisible()
    expect(await seriousViolations(page)).toEqual([])
  })
}
