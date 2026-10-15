/// <reference types="node" />
import { readFileSync } from 'node:fs'

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RehearsalTimer } from '../../src/components/RehearsalTimer'
import { BEATS, CHECKLIST_STORAGE_KEY } from '../../src/presenter/beats'
import { PresenterPage } from '../../src/routes/PresenterPage'
import { type FetchCall, json, MockXHR, mockVideoMetadata, type Route, stubFetch } from './http'

const KEY_STORAGE = 'tactistream.presenter.key'
const empty = { slots: {}, published: false }
const mainRecord = {
  slot: 'main',
  kind: 'file',
  filename: 'demo.mp4',
  content_type: 'video/mp4',
  bytes: 12_345_678,
  sha256: 'a'.repeat(64),
  duration_s: 115,
  width: 1920,
  height: 1080,
  client_reported: ['duration_s', 'width', 'height'],
  uploaded_at: '2026-10-15T06:00:00Z',
}

let routes: Record<string, Route>
let calls: FetchCall[]

/** The state route answers 401 unless the request carries `key`. */
function keyed(key: string, state: unknown): Route {
  return (init) =>
    new Headers(init?.headers).get('X-Presenter-Key') === key
      ? new Response(JSON.stringify(state), { status: 200 })
      : new Response(JSON.stringify({ error: 'presenter_key_invalid', detail: '' }), { status: 401 })
}

async function unlocked(state: unknown = empty) {
  sessionStorage.setItem(KEY_STORAGE, 'k1')
  routes['GET /api/presenter/state'] = keyed('k1', state)
  render(<PresenterPage />)
  await screen.findByRole('heading', { name: '1. Rehearse' })
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  MockXHR.instances = []
  routes = { 'GET /api/presenter/state': keyed('k1', empty) }
  calls = stubFetch(routes)
  vi.stubGlobal('XMLHttpRequest', MockXHR)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('PresenterPage access', () => {
  it('says presenter mode is disabled when the state API answers 404', async () => {
    routes['GET /api/presenter/state'] = json(404, { error: 'presenter_disabled', detail: '' })
    render(<PresenterPage />)
    expect(await screen.findByText('Presenter mode is disabled on this server')).toBeInTheDocument()
    expect(screen.queryByLabelText('Presenter key')).not.toBeInTheDocument()
  })

  it('asks for the key, keeps it in sessionStorage only and sends it as X-Presenter-Key', async () => {
    render(<PresenterPage />)
    await userEvent.type(await screen.findByLabelText('Presenter key'), 'k1')
    await userEvent.click(screen.getByRole('button', { name: 'Unlock' }))

    expect(await screen.findByRole('heading', { name: '1. Rehearse' })).toBeInTheDocument()
    expect(sessionStorage.getItem(KEY_STORAGE)).toBe('k1')
    const stored = Array.from({ length: localStorage.length }, (_, i) =>
      localStorage.getItem(localStorage.key(i) ?? ''),
    )
    expect(stored).not.toContain('k1')
    expect(calls.at(-1)?.headers.get('X-Presenter-Key')).toBe('k1')
  })

  it('refuses a wrong key, forgets it and keeps the steps hidden', async () => {
    render(<PresenterPage />)
    await userEvent.type(await screen.findByLabelText('Presenter key'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Unlock' }))

    expect(await screen.findByText('That presenter key was refused.')).toBeInTheDocument()
    expect(sessionStorage.getItem(KEY_STORAGE)).toBeNull()
    expect(screen.queryByRole('heading', { name: '1. Rehearse' })).not.toBeInTheDocument()
  })
})

describe('Media slots', () => {
  function mainSlot() {
    return within(screen.getByRole('region', { name: 'Main demo video' }))
  }

  it('shows duration and resolution of a selected MP4 before upload, then uploads with the key and metadata', async () => {
    mockVideoMetadata({ duration: 115, width: 1920, height: 1080 })
    await unlocked()
    const file = new File([new Uint8Array(16)], 'demo.mp4', { type: 'video/mp4' })
    await userEvent.upload(mainSlot().getByLabelText('Choose file'), file)

    expect(await mainSlot().findByText('1:55')).toBeInTheDocument()
    expect(mainSlot().getByText('1920×1080')).toBeInTheDocument()
    expect(mainSlot().getByText('Meets video spec')).toBeInTheDocument()
    expect(MockXHR.instances).toHaveLength(0)

    await userEvent.click(mainSlot().getByRole('button', { name: 'Upload' }))
    const xhr = MockXHR.instances[0]
    expect(xhr?.method).toBe('PUT')
    const url = new URL(xhr?.url ?? '', 'http://x')
    expect(url.pathname).toBe('/api/presenter/media/main')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      filename: 'demo.mp4',
      duration_s: '115',
      width: '1920',
      height: '1080',
    })
    expect(xhr?.headers['x-presenter-key']).toBe('k1')
    expect(xhr?.headers['content-type']).toBe('video/mp4')
    expect(xhr?.body).toBe(file)

    await act(async () => {
      xhr?.respond(200, mainRecord)
      await Promise.resolve()
    })
    expect(mainSlot().queryByText('Selected — not uploaded yet')).not.toBeInTheDocument()
    expect(mainSlot().getByText('demo.mp4')).toBeInTheDocument()
    expect(mainSlot().getByText('11.8 MB')).toBeInTheDocument()
  })

  it('warns, without blocking upload, when a video is outside 110–119 s or not 1920×1080', async () => {
    mockVideoMetadata({ duration: 130, width: 1280, height: 720 })
    await unlocked()
    await userEvent.upload(
      mainSlot().getByLabelText('Choose file'),
      new File([new Uint8Array(16)], 'long.mp4', { type: 'video/mp4' }),
    )

    expect(await mainSlot().findByText('2:10')).toBeInTheDocument()
    expect(mainSlot().getByText('Duration outside 1:50–1:59')).toBeInTheDocument()
    expect(mainSlot().getByText('Not 1920×1080')).toBeInTheDocument()
    expect(mainSlot().queryByText('Meets video spec')).not.toBeInTheDocument()
    expect(mainSlot().getByRole('button', { name: 'Upload' })).toBeEnabled()
  })

  it('saves a YouTube link as JSON with the key', async () => {
    await unlocked()
    routes['PUT /api/presenter/media/backup'] = json(200, {
      slot: 'backup',
      kind: 'link',
      url: 'https://youtu.be/b',
    })
    const backup = within(screen.getByRole('region', { name: 'Backup recording' }))
    await userEvent.type(backup.getByLabelText(/YouTube URL/), 'https://youtu.be/b')
    await userEvent.click(backup.getByRole('button', { name: 'Save link' }))

    await waitFor(() => {
      expect(calls.at(-1)?.key).toBe('PUT /api/presenter/media/backup')
    })
    expect(calls.at(-1)?.body).toEqual({ url: 'https://youtu.be/b' })
    expect(calls.at(-1)?.headers.get('X-Presenter-Key')).toBe('k1')
    expect(await backup.findByRole('link', { name: 'https://youtu.be/b' })).toBeInTheDocument()
  })
})

describe('Record checklist', () => {
  it('persists ticks in localStorage across visits', async () => {
    await unlocked()
    const box = screen.getByRole('checkbox', { name: 'Exported as H.264 MP4' })
    expect(box).not.toBeChecked()
    await userEvent.click(box)
    expect(JSON.parse(localStorage.getItem(CHECKLIST_STORAGE_KEY) ?? '[]')).toEqual(['h264'])
  })

  it('restores stored ticks', async () => {
    localStorage.setItem(CHECKLIST_STORAGE_KEY, JSON.stringify(['h264', 'resolution']))
    await unlocked()
    expect(screen.getByRole('checkbox', { name: 'Exported as H.264 MP4' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Exactly 1920×1080' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Between 1:50 and 1:59/ })).not.toBeChecked()
  })
})

describe('Publish', () => {
  it('turns publishing on through the API with the key', async () => {
    await unlocked({ slots: { main: mainRecord }, published: false })
    routes['PUT /api/presenter/publish'] = json(200, { slots: { main: mainRecord }, published: true })
    const toggle = screen.getByRole('switch', { name: 'Publish to judges' })
    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)

    await waitFor(() => {
      expect(toggle).toBeChecked()
    })
    const call = calls.find((c) => c.key === 'PUT /api/presenter/publish')
    expect(call?.body).toEqual({ published: true })
    expect(call?.headers.get('X-Presenter-Key')).toBe('k1')
  })

  it('is disabled until the main video is uploaded or linked', async () => {
    await unlocked()
    expect(screen.getByRole('switch', { name: 'Publish to judges' })).toBeDisabled()
    expect(screen.getByText('Upload or link the main video before publishing.')).toBeInTheDocument()
  })

  it('shows off once the main video is cleared', async () => {
    await unlocked({ slots: { main: mainRecord }, published: true })
    routes['DELETE /api/presenter/media/main'] = json(200, { slots: {}, published: false })
    const toggle = screen.getByRole('switch', { name: 'Publish to judges' })
    expect(toggle).toBeChecked()
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Main demo video' })).getByRole('button', { name: 'Clear' }),
    )

    await waitFor(() => {
      expect(toggle).toBeDisabled()
    })
    expect(toggle).not.toBeChecked()
  })
})

describe('Rehearsal', () => {
  it('uses the beats from the demo script', () => {
    const script = readFileSync(`${import.meta.dirname}/../../../specs/009-submission/demo-script.md`, 'utf8')
    const timeline = script.slice(script.indexOf('## Timeline'), script.indexOf('## Shot list'))
    const rows = timeline
      .split('\n')
      .filter((line) => /^\| \d:\d\d–\d:\d\d \|/.test(line))
      .map((line) =>
        line
          .split('|')
          .slice(1, 4)
          .map((cell) => cell.trim()),
      )
    expect(BEATS.map((b) => [b.time, b.action, b.intent])).toEqual(rows)
    expect(rows).toHaveLength(8)
  })

  it('highlights the beat for the elapsed time and flags over-time', () => {
    vi.useFakeTimers()
    render(<RehearsalTimer />)
    const rowOf = (time: string) => screen.getByRole('row', { name: new RegExp(`^${time}`) })
    expect(rowOf('0:00–0:08')).toHaveAttribute('aria-current', 'step')

    fireEvent.click(screen.getByRole('button', { name: 'Start timer' }))
    act(() => {
      vi.advanceTimersByTime(45_000)
    })
    expect(screen.getByText('0:45')).toBeInTheDocument()
    expect(rowOf('0:43–0:58')).toHaveAttribute('aria-current', 'step')
    expect(rowOf('0:30–0:43')).not.toHaveAttribute('aria-current')

    act(() => {
      vi.advanceTimersByTime(75_000)
    })
    expect(screen.getByText(/Over 1:55/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reset timer' }))
    expect(screen.getByText('0:00')).toBeInTheDocument()
    expect(rowOf('0:00–0:08')).toHaveAttribute('aria-current', 'step')
  })
})
