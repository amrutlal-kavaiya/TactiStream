import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../../src/App'
import type { DemoMedia } from '../../src/api/config'
import { WatchDemoButton } from '../../src/components/WatchDemoButton'
import { WatchPage } from '../../src/routes/WatchPage'
import { type FetchCall, json, type Route, stubFetch } from './http'

const fileMedia: DemoMedia = {
  main: { url: '/media/main?v=abc', kind: 'file' },
  backup: { url: '/media/backup?v=bcd', kind: 'file' },
  captions_url: '/media/captions?v=def',
}

let routes: Record<string, Route>
let calls: FetchCall[]

function publish(media: DemoMedia | null) {
  routes['GET /api/config'] = json(200, { demo_media: media })
}

beforeEach(() => {
  localStorage.clear()
  routes = {}
  publish(null)
  calls = stubFetch(routes)
})

describe('WatchDemoButton', () => {
  it('renders nothing while demo media is unpublished', async () => {
    render(<WatchDemoButton />)
    await waitFor(() => {
      expect(calls.map((c) => c.key)).toContain('GET /api/config')
    })
    expect(screen.queryByRole('button', { name: 'Watch demo video' })).not.toBeInTheDocument()
  })

  it('opens a dialog with the main video, a default English captions track and the backup link', async () => {
    publish(fileMedia)
    render(<WatchDemoButton />)
    await userEvent.click(await screen.findByRole('button', { name: 'Watch demo video' }))

    const dialog = await screen.findByRole('dialog', { name: 'Demo video' })
    const video = dialog.querySelector('video')
    expect(video).not.toBeNull()
    expect(video).toHaveAttribute('controls')
    expect(video).toHaveAttribute('src', '/media/main?v=abc')
    const tracks = dialog.querySelectorAll('track')
    expect(tracks).toHaveLength(1)
    expect(tracks[0]).toHaveAttribute('kind', 'captions')
    expect(tracks[0]).toHaveAttribute('default')
    expect(tracks[0]).toHaveAttribute('srclang', 'en')
    expect(tracks[0]).toHaveAttribute('src', '/media/captions?v=def')
    expect(within(dialog).getByRole('link', { name: 'Backup recording' })).toHaveAttribute(
      'href',
      '/media/backup?v=bcd',
    )

    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('links out instead of embedding when the main video is a YouTube URL', async () => {
    publish({ main: { url: 'https://youtu.be/abc', kind: 'link' }, backup: null, captions_url: null })
    render(<WatchDemoButton />)
    await userEvent.click(await screen.findByRole('button', { name: 'Watch demo video' }))

    const dialog = await screen.findByRole('dialog', { name: 'Demo video' })
    expect(dialog.querySelector('video')).toBeNull()
    const link = within(dialog).getByRole('link', { name: /Open the demo video/ })
    expect(link).toHaveAttribute('href', 'https://youtu.be/abc')
    expect(link).toHaveAttribute('target', '_blank')
    expect(within(dialog).queryByRole('link', { name: 'Backup recording' })).not.toBeInTheDocument()
  })
})

describe('header', () => {
  it('shows "Watch demo video" in the match app header only once media is published', async () => {
    publish(fileMedia)
    render(<App />)
    const header = screen.getByRole('banner')
    expect(await within(header).findByRole('button', { name: 'Watch demo video' })).toBeInTheDocument()
  })
})

describe('WatchPage', () => {
  it('says the video is not published yet when demo media is null', async () => {
    render(<WatchPage />)
    expect(await screen.findByText('The demo video is not published yet')).toBeInTheDocument()
    expect(document.querySelector('video')).toBeNull()
  })

  it('shows the player with captions and the backup link when published', async () => {
    publish(fileMedia)
    render(<WatchPage />)
    expect(await screen.findByRole('link', { name: 'Backup recording' })).toHaveAttribute(
      'href',
      '/media/backup?v=bcd',
    )
    const video = document.querySelector('video')
    expect(video).toHaveAttribute('src', '/media/main?v=abc')
    expect(video?.querySelector('track[kind="captions"][default]')).toHaveAttribute('src', '/media/captions?v=def')
    expect(screen.queryByText('The demo video is not published yet')).not.toBeInTheDocument()
  })
})
