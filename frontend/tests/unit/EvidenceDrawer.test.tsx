import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError, type EvidenceResponse } from '../../src/api/client'
import { EvidenceDrawer } from '../../src/components/EvidenceDrawer'
import type { MetricResult } from '../../src/contracts/generated'
import { event, MATCH_ID } from './fixtures'

const eventEvidence: EvidenceResponse = { evidence_id: 'evt-0042', kind: 'event', record: event('evt-0042') }

const metric: MetricResult = {
  schema_version: '1.0',
  match_id: MATCH_ID,
  metric_id: 'met-fp-evt-0042',
  kind: 'forward_progress',
  definition_version: '1.0',
  status: 'ok',
  value: 13.1,
  unit: 'm',
  subject_ids: ['blue-08'],
  window: { start_ms: 3000, end_ms: 3900 },
  inputs: { event_ids: ['evt-0042'], frame_ids: [] },
  state_version: 5,
}

function field(dialog: HTMLElement, term: string) {
  return within(dialog).getByText(term, { selector: 'dt' }).nextElementSibling?.textContent
}

describe('EvidenceDrawer', () => {
  it('shows loading, then the key fields of an event', async () => {
    render(
      <EvidenceDrawer evidenceId="evt-0042" load={() => Promise.resolve(eventEvidence)} onClose={vi.fn()} />,
    )
    expect(screen.getByText('Loading evidence…')).toBeInTheDocument()

    const dialog = screen.getByRole('dialog')
    expect(await within(dialog).findByText('Type', { selector: 'dt' })).toBeInTheDocument()
    expect(field(dialog, 'Type')).toBe('pass')
    expect(field(dialog, 'Player')).toBe('blue-08')
    expect(field(dialog, 'Recipient')).toBe('blue-11')
    expect(field(dialog, 'Start (m)')).toBe('58.1, 32.4')
    expect(field(dialog, 'End (m)')).toBe('71.2, 28.0')
    expect(field(dialog, 'Period clock')).toBe('P1 00:03.0')
    expect(field(dialog, 'Session clock')).toBe('00:03.0')
    expect(field(dialog, 'Source')).toBe('synthetic')
  })

  it('shows the value and window of a metric', async () => {
    const metricEvidence: EvidenceResponse = { evidence_id: metric.metric_id, kind: 'metric', record: metric }
    render(
      <EvidenceDrawer
        evidenceId={metric.metric_id}
        load={() => Promise.resolve(metricEvidence)}
        onClose={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog')
    await within(dialog).findByText('Metric', { selector: 'dt' })
    expect(field(dialog, 'Metric')).toBe('forward_progress')
    expect(field(dialog, 'Value')).toBe('13.1 m')
    expect(field(dialog, 'Window')).toBe('00:03.0 – 00:03.9')
    expect(field(dialog, 'Input events')).toBe('evt-0042')
  })

  it('shows "Evidence unavailable" on 404', async () => {
    const load = () => Promise.reject(new ApiError(404, 'evidence_not_found', 'evt-9999 is not available'))
    render(<EvidenceDrawer evidenceId="evt-9999" load={load} onClose={vi.fn()} />)

    expect(await screen.findByText('Evidence unavailable')).toBeInTheDocument()
  })

  it('is a dialog labelled by its heading', () => {
    render(
      <EvidenceDrawer evidenceId="evt-0042" load={() => Promise.resolve(eventEvidence)} onClose={vi.fn()} />,
    )

    expect(screen.getByRole('dialog', { name: 'Evidence evt-0042' })).toBeInTheDocument()
  })

  it('closes with Escape and with the close button', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <EvidenceDrawer evidenceId="evt-0042" load={() => Promise.resolve(eventEvidence)} onClose={onClose} />,
    )

    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('moves focus into the dialog and returns it to the invoking chip on close', async () => {
    const user = userEvent.setup()
    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button
            onClick={() => {
              setOpen(true)
            }}
          >
            evt-0042
          </button>
          {open && (
            <EvidenceDrawer
              evidenceId="evt-0042"
              load={() => Promise.resolve(eventEvidence)}
              onClose={() => {
                setOpen(false)
              }}
            />
          )}
        </>
      )
    }
    render(<Harness />)
    const chip = screen.getByRole('button', { name: 'evt-0042' })

    await user.click(chip)
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement)

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chip).toHaveFocus()
  })
})
