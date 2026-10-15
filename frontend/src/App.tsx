import { makeStyles, MessageBar, MessageBarBody, Text, tokens } from '@fluentui/react-components'
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
import { PitchPlaceholder } from './components/PitchPlaceholder'
import { PlaybackControls } from './components/PlaybackControls'
import { type ConnectionStatus, TopBar } from './components/TopBar'
import type { InsightPacket } from './contracts/generated'
import type { MessageKey } from './i18n/en'
import { formatClock, useT } from './i18n/useT'
import { type Playback, useMatchStore } from './store/matchStore'
import { AppShell } from './theme/AppShell'
import { useThemePreference } from './theme/useThemePreference'

const START_ERRORS = new Set<MessageKey>([
  'errorInvalidScenario',
  'errorStartTimeout',
  'errorNetwork',
  'errorStart',
])

const useStyles = makeStyles({
  commandBar: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalL,
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalXL}`,
  },
  clock: { color: tokens.colorNeutralForeground2 },
  clockValue: {
    color: tokens.colorNeutralForeground1,
    fontFamily: tokens.fontFamilyMonospace,
    fontVariantNumeric: 'tabular-nums',
  },
})

function connectionStatus(
  matchId: string | null,
  connected: boolean,
  playback: Playback | null,
): ConnectionStatus {
  if (matchId === null || !connected) return 'offline'
  return playback?.state === 'playing' ? 'live' : 'paused'
}

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
  const styles = useStyles()
  const { themeName, toggleTheme } = useThemePreference()
  const matchId = useMatchStore((s) => s.matchId)
  const connected = useMatchStore((s) => s.connected)
  const playback = useMatchStore((s) => s.playback)
  const sessionClockMs = useMatchStore((s) => s.sessionClockMs)
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
        onConnectionChange: (isConnected) => {
          useMatchStore.getState().setConnected(isConnected)
        },
      })
      socketRef.current = socket
      socket.connect()
      try {
        const response = await control(session.match_id, 'play')
        useMatchStore.getState().setPlayback(response.playback)
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
      const response = await control(matchId, action)
      useMatchStore.getState().setPlayback(response.playback)
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
    <AppShell
      themeName={themeName}
      inert={evidenceId !== null}
      header={
        <TopBar
          status={connectionStatus(matchId, connected, playback)}
          themeName={themeName}
          onToggleTheme={toggleTheme}
        />
      }
      commandBar={
        <div className={styles.commandBar}>
          <PlaybackControls
            starting={starting}
            disabled={matchId === null}
            onStart={() => void start()}
            onControl={(action) => void sendControl(action)}
          />
          <Text className={styles.clock}>
            {t('sessionClock')}{' '}
            <time className={styles.clockValue} data-testid="session-clock">
              {formatClock(sessionClockMs)}
            </time>
          </Text>
        </div>
      }
      stage={
        <>
          {errorKey && (
            <MessageBar intent={START_ERRORS.has(errorKey) ? 'error' : 'warning'} role="alert">
              <MessageBarBody>{t(errorKey)}</MessageBarBody>
            </MessageBar>
          )}
          <PitchPlaceholder hint={matchId === null ? t('idleHint') : t('pitchPlaceholderHint')} />
        </>
      }
      rail={
        <>
          <div aria-live="polite">
            {packet && (
              <InsightCard packet={packet} onOpenEvidence={setEvidenceId} onDisplayed={acknowledge} />
            )}
          </div>
          <EventList />
        </>
      }
      overlay={
        evidenceId &&
        matchId && (
          <EvidenceDrawer
            key={evidenceId}
            evidenceId={evidenceId}
            load={(id) => getEvidence(matchId, id, language)}
            onClose={() => {
              setEvidenceId(null)
            }}
          />
        )
      }
    />
  )
}
