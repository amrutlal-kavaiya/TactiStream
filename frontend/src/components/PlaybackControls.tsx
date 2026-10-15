import type { ControlAction } from '../api/client'
import { useT } from '../i18n/useT'

export interface PlaybackControlsProps {
  disabled: boolean
  onControl: (action: ControlAction) => void
}

export function PlaybackControls({ disabled, onControl }: PlaybackControlsProps) {
  const t = useT()
  const actions: [ControlAction, string][] = [
    ['play', t('play')],
    ['pause', t('pause')],
    ['reset', t('reset')],
  ]
  return (
    <div className="controls" role="group" aria-label={t('playback')}>
      {actions.map(([action, label]) => (
        <button
          key={action}
          type="button"
          className="button"
          disabled={disabled}
          onClick={() => {
            onControl(action)
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
