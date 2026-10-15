import { useId } from 'react'

import { formatClock, useT } from '../i18n/useT'
import { useMatchStore } from '../store/matchStore'

export function EventList() {
  const t = useT()
  const headingId = useId()
  const events = useMatchStore((s) => s.events)

  return (
    <section className="panel">
      <h2 id={headingId}>{t('events')}</h2>
      {events.length === 0 ? (
        <p className="muted">{t('noEvents')}</p>
      ) : (
        <ol className="event-list" aria-labelledby={headingId}>
          {events.map((e) => (
            <li key={e.event_id}>
              {formatClock(e.session_clock_ms)} · {e.event_type} · {e.player_id}
              {e.recipient_id ? ` → ${e.recipient_id}` : ''}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
