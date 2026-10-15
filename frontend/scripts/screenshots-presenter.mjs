// Captures docs/screenshots/009-presenter.png and 009-watch.png from a local server started with a presenter key:
// `BASE_URL=http://localhost:8400 PRESENTER_KEY=dev node scripts/screenshots-presenter.mjs`.
// It publishes the e2e sample media and clears it afterwards, so it refuses to run against anything but localhost.
import { mkdir, readFile } from 'node:fs/promises'
import { chromium, request as http } from '@playwright/test'

const baseUrl = process.env.BASE_URL ?? 'http://localhost:8400'
const key = process.env.PRESENTER_KEY
if (!key) throw new Error('PRESENTER_KEY is required')
if (!['localhost', '127.0.0.1'].includes(new URL(baseUrl).hostname)) throw new Error('local servers only')

const outDir = new URL('../../docs/screenshots/', import.meta.url)
const fixture = (name) => new URL(`../tests/e2e/fixtures/${name}`, import.meta.url)
const headers = { 'X-Presenter-Key': key }

await mkdir(outDir, { recursive: true })
const api = await http.newContext({ baseURL: baseUrl, extraHTTPHeaders: headers })

async function put(path, contentType, data) {
  const response = await api.put(path, { headers: contentType ? { 'Content-Type': contentType } : {}, data })
  if (!response.ok()) throw new Error(`${path}: ${String(response.status())} ${await response.text()}`)
}

const browser = await chromium.launch()
try {
  await put(
    '/api/presenter/media/main?filename=demo.mp4&duration_s=115&width=1920&height=1080',
    'video/mp4',
    await readFile(fixture('sample.mp4')),
  )
  await put(
    '/api/presenter/media/captions?filename=demo.vtt',
    'text/vtt',
    await readFile(fixture('sample.vtt')),
  )
  await put('/api/presenter/media/backup', undefined, { url: 'https://youtu.be/backup-take' })
  await put('/api/presenter/publish', undefined, { published: true })

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.addInitScript((value) => {
    localStorage.setItem('tactistream.theme', 'dark')
    sessionStorage.setItem('tactistream.presenter.key', value)
  }, key)

  await page.goto(`${baseUrl}/presenter`, { waitUntil: 'networkidle' })
  await page.getByRole('region', { name: 'Main demo video' }).getByText('demo.mp4').waitFor()
  await page.getByRole('button', { name: 'Start timer' }).click()
  await page.waitForTimeout(2200)
  await page.getByRole('button', { name: 'Pause timer' }).click()
  await page.screenshot({ path: new URL('009-presenter.png', outDir).pathname, fullPage: true })

  await page.goto(`${baseUrl}/watch`, { waitUntil: 'networkidle' })
  await page.waitForFunction(() => (document.querySelector('video')?.readyState ?? 0) >= 2)
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        const video = document.querySelector('video')
        video.addEventListener('seeked', resolve, { once: true })
        video.currentTime = 0.5
      }),
  )
  await page.waitForTimeout(800)
  await page.screenshot({ path: new URL('009-watch.png', outDir).pathname })
} finally {
  await browser.close()
  await api.put('/api/presenter/publish', { data: { published: false } })
  for (const slot of ['main', 'backup', 'captions']) await api.delete(`/api/presenter/media/${slot}`)
  await api.dispose()
}
