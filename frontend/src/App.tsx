import { useEffect, useRef, useState } from 'react'

import {
  ApiError,
  control,
  type ControlAction,
  createSession,
  getEvidence,
  type SessionInfo,
  wsUrl,
} from './api/client'
import { MatchSocket } from './api/socket'
import { EventList } from './components/EventList'
import { EvidenceDrawer } from './components/EvidenceDrawer'
import { InsightCard } from './components/InsightCard'
import { PlaybackControls } from './components/PlaybackControls'
import { TopBar } from './components/TopBar'
import type { InsightPacket } from './contracts/generated'
import type { MessageKey } from './i18n/en'
import { useT } from './i18n/useT'
import { useMatchStore } from './store/matchStore'

function startErrorKey(error: unknown): MessageKey {
  if (!(error instanceof ApiError)) return 'errorStart'
  switch (error.code) {
    case 'invalid_scenario':
      return 'errorInvalidScenario'
    case 'session_start_timeout':
      return 'errorStartTimeout'
    case 'network_error':
      return 'errorNetwork'
    default:
      return 'errorStart'
  }
}

export default function App() {
  const t = useT()
  const matchId = useMatchStore((s) => s.matchId)
  const language = useMatchStore((s) => s.prefs.language)
  const packet = useMatchStore((s) => s.variantFor(s.prefs))
  const [starting, setStarting] = useState(false)
  const [errorKey, setErrorKey] = useState<MessageKey | null>(null)
  const [evidenceId, setEvidenceId] = useState<string | null>(null)
  const socketRef = useRef<MatchSocket | null>(null)

  useEffect(
    () => () => {
      socketRef.current?.close()
    },
    [],
  )

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  async function start() {
    setStarting(true)
    setErrorKey(null)
    setEvidenceId(null)
    try {
      let session: SessionInfo
      try {
        session = await createSession('skeleton')
      } catch (error) {
        setErrorKey(startErrorKey(error))
        return
      }
      socketRef.current?.close()
      useMatchStore.getState().startSession(session.match_id)
      const socket = new MatchSocket({
        url: wsUrl(session.ws_path),
        onMessage: (message) => {
          useMatchStore.getState().applyMessage(message)
        },
        getLastSeq: () => useMatchStore.getState().lastSeq,
      })
      socketRef.current = socket
      socket.connect()
      try {
        await control(session.match_id, 'play')
      } catch {
        setErrorKey('errorPlayNotStarted')
      }
    } finally {
      setStarting(false)
    }
  }

  async function sendControl(action: ControlAction) {
    if (!matchId) return
    setErrorKey(null)
    try {
      await control(matchId, action)
    } catch {
      setErrorKey('errorControl')
    }
  }

  function acknowledge(displayed: InsightPacket) {
    const { insightSeq, lastSeq } = useMatchStore.getState()
    socketRef.current?.ackDisplay(
      'insight',
      displayed.insight_id,
      insightSeq[displayed.insight_id] ?? lastSeq,
    )
  }

  return (
    <>
      <div className="app" inert={evidenceId !== null}>
        <TopBar />
        <main className="main">
          <div className="panel">
            <div className="controls">
              <button
                type="button"
                className="button button--primary"
                disabled={starting}
                onClick={() => void start()}
              >
                {starting ? t('starting') : t('startDemo')}
              </button>
              <PlaybackControls
                disabled={matchId === null}
                onControl={(action) => void sendControl(action)}
              />
            </div>
            {errorKey && (
              <p className="error" role="alert">
                {t(errorKey)}
              </p>
            )}
            {matchId === null && !errorKey && <p className="muted">{t('idleHint')}</p>}
          </div>
          <EventList />
          <div aria-live="polite">
            {packet && (
              <InsightCard packet={packet} onOpenEvidence={setEvidenceId} onDisplayed={acknowledge} />
            )}
          </div>
        </main>
      </div>
      {evidenceId && matchId && (
        <EvidenceDrawer
          key={evidenceId}
          evidenceId={evidenceId}
          load={(id) => getEvidence(matchId, id, language)}
          onClose={() => {
            setEvidenceId(null)
          }}
        />
      )}
    </>
  )
}
