import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { navigate } from '../../src/routes/navigation'
import { Router } from '../../src/routes/router'
import { json, stubFetch } from './http'

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  stubFetch({
    'GET /api/config': json(200, { demo_media: null }),
    'GET /api/presenter/state': json(404, { error: 'presenter_disabled', detail: '' }),
  })
})

function at(path: string) {
  window.history.pushState({}, '', path)
  return render(<Router />)
}

describe('Router', () => {
  it('renders the match app at /', () => {
    at('/')
    expect(screen.getByRole('button', { name: 'Start demo match' })).toBeInTheDocument()
  })

  it('renders the match app for unknown paths so SPA deep links keep working', () => {
    at('/demo?seed=42')
    expect(screen.getByRole('button', { name: 'Start demo match' })).toBeInTheDocument()
  })

  it('renders the presenter page at /presenter', async () => {
    at('/presenter')
    expect(await screen.findByRole('heading', { name: 'Presenter' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start demo match' })).not.toBeInTheDocument()
  })

  it('renders the watch page at /watch', async () => {
    at('/watch')
    expect(await screen.findByRole('heading', { name: 'Demo video' })).toBeInTheDocument()
  })

  it('navigate() pushes history and re-renders; Back returns to the previous page', async () => {
    at('/')
    act(() => {
      navigate('/watch')
    })
    expect(window.location.pathname).toBe('/watch')
    expect(await screen.findByRole('heading', { name: 'Demo video' })).toBeInTheDocument()

    act(() => {
      window.history.back()
    })
    expect(await screen.findByRole('button', { name: 'Start demo match' })).toBeInTheDocument()
  })
})
