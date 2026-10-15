import { Toolbar, ToolbarButton, ToolbarDivider, Tooltip } from '@fluentui/react-components'
import { ArrowReset24Regular, Pause24Regular, Play24Regular, Rocket24Regular } from '@fluentui/react-icons'
import type { ReactElement } from 'react'

import type { ControlAction } from '../api/client'
import type { MessageKey } from '../i18n/en'
import { useT } from '../i18n/useT'

export interface PlaybackControlsProps {
  starting: boolean
  disabled: boolean
  onStart: () => void
  onControl: (action: ControlAction) => void
}

const ACTIONS: [ControlAction, MessageKey, MessageKey, ReactElement][] = [
  ['play', 'play', 'playHint', <Play24Regular key="play" />],
  ['pause', 'pause', 'pauseHint', <Pause24Regular key="pause" />],
  ['reset', 'reset', 'resetHint', <ArrowReset24Regular key="reset" />],
]

export function PlaybackControls({ starting, disabled, onStart, onControl }: PlaybackControlsProps) {
  const t = useT()
  return (
    <Toolbar aria-label={t('playback')} size="medium">
      <ToolbarButton appearance="primary" icon={<Rocket24Regular />} disabled={starting} onClick={onStart}>
        {starting ? t('starting') : t('startDemo')}
      </ToolbarButton>
      <ToolbarDivider />
      {ACTIONS.map(([action, label, hint, icon]) => (
        <Tooltip key={action} content={t(hint)} relationship="description">
          <ToolbarButton
            icon={icon}
            disabled={disabled}
            onClick={() => {
              onControl(action)
            }}
          >
            {t(label)}
          </ToolbarButton>
        </Tooltip>
      ))}
    </Toolbar>
  )
}
