import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { InsightCard } from '../../src/components/InsightCard'
import type { InsightPacket } from '../../src/contracts/generated'
import { insight } from './fixtures'

function fanEnglish(overrides: Partial<InsightPacket> = {}): InsightPacket {
  const packet = insight('ins-0042').variants[0]
  if (!packet) throw new Error('fixture has no variants')
  return { ...packet, ...overrides }
}

let frames: FrameRequestCallback[]

beforeEach(() => {
  frames = []
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const flushFrames = () => {
  for (const cb of frames.splice(0)) cb(0)
}

describe('InsightCard', () => {
  it('renders the server title and body', () => {
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'ins-0042 title fan en' })).toBeInTheDocument()
    expect(screen.getByText('ins-0042 body fan en')).toBeInTheDocument()
  })

  it('shows the Synthetic and Verified fact labels', () => {
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={vi.fn()} />)

    expect(screen.getByText('Synthetic')).toBeInTheDocument()
    expect(screen.getByText('Verified fact')).toBeInTheDocument()
  })

  it('omits the Synthetic label when the packet is not labelled synthetic', () => {
    render(<InsightCard packet={fanEnglish({ labels: [] })} onOpenEvidence={vi.fn()} />)

    expect(screen.queryByText('Synthetic')).not.toBeInTheDocument()
  })

  it('renders each evidence id as a button', () => {
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'evt-0042' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'met-fp-evt-0042' })).toBeInTheDocument()
  })

  it('opens evidence on click', async () => {
    const onOpenEvidence = vi.fn()
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={onOpenEvidence} />)

    await userEvent.click(screen.getByRole('button', { name: 'evt-0042' }))
    expect(onOpenEvidence).toHaveBeenCalledWith('evt-0042')
  })

  it('opens evidence with Enter', async () => {
    const user = userEvent.setup()
    const onOpenEvidence = vi.fn()
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={onOpenEvidence} />)

    screen.getByRole('button', { name: 'met-fp-evt-0042' }).focus()
    await user.keyboard('{Enter}')
    expect(onOpenEvidence).toHaveBeenCalledWith('met-fp-evt-0042')
  })

  it('opens evidence with Space', async () => {
    const user = userEvent.setup()
    const onOpenEvidence = vi.fn()
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={onOpenEvidence} />)

    screen.getByRole('button', { name: 'evt-0042' }).focus()
    await user.keyboard(' ')
    expect(onOpenEvidence).toHaveBeenCalledWith('evt-0042')
  })

  it('is an article labelled by the server title', () => {
    render(<InsightCard packet={fanEnglish()} onOpenEvidence={vi.fn()} />)

    expect(screen.getByRole('article', { name: 'ins-0042 title fan en' })).toBeInTheDocument()
  })

  it('reports the card as displayed once, after the first paint', () => {
    const onDisplayed = vi.fn()
    const packet = fanEnglish()
    const { rerender } = render(
      <InsightCard packet={packet} onOpenEvidence={vi.fn()} onDisplayed={onDisplayed} />,
    )
    expect(onDisplayed).not.toHaveBeenCalled()

    flushFrames()
    rerender(<InsightCard packet={{ ...packet }} onOpenEvidence={vi.fn()} onDisplayed={onDisplayed} />)
    flushFrames()

    expect(onDisplayed).toHaveBeenCalledTimes(1)
    expect(onDisplayed).toHaveBeenCalledWith(packet)
  })
})
