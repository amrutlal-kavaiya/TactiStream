import { FluentProvider, makeStyles, mergeClasses, tokens } from '@fluentui/react-components'
import type { ReactNode } from 'react'

import { type ThemeName, themes } from './brand'

export interface AppShellProps {
  themeName: ThemeName
  header: ReactNode
  commandBar: ReactNode
  stage: ReactNode
  rail: ReactNode
  /** Rendered outside the inert region, e.g. a modal drawer. */
  overlay?: ReactNode
  /** Makes the page behind an open modal unreachable. */
  inert?: boolean
}

const useStyles = makeStyles({
  provider: {
    minHeight: '100vh',
    backgroundColor: tokens.colorNeutralBackground2,
    color: tokens.colorNeutralForeground1,
  },
  dark: { colorScheme: 'dark' },
  light: { colorScheme: 'light' },
  shell: {
    minHeight: '100vh',
    display: 'grid',
    gridTemplateRows: 'auto auto 1fr',
    gridTemplateColumns: 'minmax(0, 1fr) 360px',
    gridTemplateAreas: '"header header" "commands commands" "stage rail"',
    '@media (max-width: 899px)': {
      gridTemplateRows: 'auto auto auto auto',
      gridTemplateColumns: 'minmax(0, 1fr)',
      gridTemplateAreas: '"header" "commands" "stage" "rail"',
    },
  },
  header: {
    gridArea: 'header',
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStroke2}`,
  },
  commands: {
    gridArea: 'commands',
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStroke2}`,
    boxShadow: tokens.shadow2,
  },
  stage: {
    gridArea: 'stage',
    minWidth: 0,
    padding: tokens.spacingHorizontalXXL,
    display: 'grid',
    alignContent: 'start',
    gap: tokens.spacingVerticalL,
    '@media (max-width: 899px)': { padding: tokens.spacingHorizontalL },
  },
  rail: {
    gridArea: 'rail',
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
    padding: tokens.spacingHorizontalL,
    backgroundColor: tokens.colorNeutralBackground1,
    borderLeft: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStroke2}`,
    boxShadow: tokens.shadow4,
    '@media (max-width: 899px)': {
      borderLeft: 'none',
      borderTop: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStroke2}`,
    },
  },
})

export function AppShell({ themeName, header, commandBar, stage, rail, overlay, inert }: AppShellProps) {
  const styles = useStyles()
  return (
    <FluentProvider
      theme={themes[themeName]}
      className={mergeClasses(styles.provider, styles[themeName])}
      data-theme={themeName}
      data-testid="app-shell"
    >
      <div className={styles.shell} inert={inert}>
        <header className={styles.header}>{header}</header>
        <div className={styles.commands}>{commandBar}</div>
        <main className={styles.stage}>{stage}</main>
        <aside className={styles.rail}>{rail}</aside>
      </div>
      {overlay}
    </FluentProvider>
  )
}
