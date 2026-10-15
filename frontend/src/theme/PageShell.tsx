import { FluentProvider, makeStyles, mergeClasses, tokens } from '@fluentui/react-components'
import type { ReactNode } from 'react'

import { type ThemeName, themes } from './brand'

export interface PageShellProps {
  themeName: ThemeName
  header: ReactNode
  children: ReactNode
}

const useStyles = makeStyles({
  provider: { color: tokens.colorNeutralForeground1 },
  dark: { colorScheme: 'dark' },
  light: { colorScheme: 'light' },
  shell: {
    minHeight: '100vh',
    backgroundColor: tokens.colorNeutralBackground2,
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
  },
  header: {
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStroke2}`,
  },
  main: {
    width: '100%',
    maxWidth: '1200px',
    boxSizing: 'border-box',
    justifySelf: 'center',
    padding: tokens.spacingHorizontalXXL,
    display: 'grid',
    alignContent: 'start',
    gap: tokens.spacingVerticalL,
    '@media (max-width: 899px)': { padding: tokens.spacingHorizontalL },
  },
})

/** Single-column page (presenter, watch) with the same provider setup as `AppShell`. */
export function PageShell({ themeName, header, children }: PageShellProps) {
  const styles = useStyles()
  return (
    <FluentProvider
      theme={themes[themeName]}
      className={mergeClasses(styles.provider, styles[themeName])}
      data-theme={themeName}
      data-testid="app-shell"
    >
      <div className={styles.shell}>
        <header className={styles.header}>{header}</header>
        <main className={styles.main}>{children}</main>
      </div>
    </FluentProvider>
  )
}
