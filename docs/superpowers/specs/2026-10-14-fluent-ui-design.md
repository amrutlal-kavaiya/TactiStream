# Fluent UI shell — design (2026-10-14)

Status: approved by user 2026-10-14 ("Use Microsoft like UI and create like a Pro"; chose official Fluent UI React v9,
dark default with light/dark toggle).

## Goal

Give TactiStream a professional Microsoft (Fluent 2) look consistent with Teams / Azure portal, without weakening any
constitution rule (evidence-first, synthetic honesty, accessibility, contract-first).

## Decisions

- Library: `@fluentui/react-components` (v9) and `@fluentui/react-icons`, exact-pinned. No other UI library.
- Theme: `FluentProvider` with a TactiStream brand ramp (`createDarkTheme` / `createLightTheme` from a 16-step
  `BrandVariants` ramp built around Blue `#3B82F6`). Default dark; toggle in the header; persisted in
  `localStorage["tactistream.theme"]` (`"dark" | "light"`); respects `prefers-color-scheme` only when nothing is stored.
- Typography: Fluent defaults (Segoe UI Variable / system stack). No web-font download.
- Team colours remain app tokens (`--ts-team-blue: #3B82F6`, `--ts-team-amber: #F59E0B`) plus pitch colours, in
  `src/styles/tokens.css`; everything else uses Fluent tokens (`tokens.colorNeutralBackground1`, …) via `makeStyles`.
- Styling: Griffel `makeStyles` co-located per component; `app.css` reduced to global reset + layout grid only.

## Layout

```
┌ Header: TactiStream · match title · [Synthetic] · ● Live/Paused/Offline · (006: Fan|Analyst · EN|HI) · ☾/☀ ┐
├ Command bar (Toolbar): Start demo · Play · Pause · Reset · session clock                             ┤
├──────────────────────────────── stage (pitch) ───────────────────┬── right rail (360 px) ───────────┤
│ placeholder Card "Pitch view arrives in 005" (R3F later)         │ Active InsightCard               │
│                                                                  │ Events (compact list)            │
└──────────────────────────────────────────────────────────────────┴──────────────────────────────────┘
```

Below 900 px wide the right rail stacks under the stage.

## Component map (registry for 005/006/008)

| App component        | Fluent v9 building blocks                                                       |
|----------------------|---------------------------------------------------------------------------------|
| `AppShell`           | `FluentProvider`, CSS grid, `makeStyles`                                         |
| `TopBar`             | `Text`, `Badge` (Synthetic, `appearance="filled"` informative), `PresenceBadge`-style status dot + label, `ToggleButton` theme; slot for `TabList` mode + `Menu` language (added in 006) |
| `SourceBadge`        | `Badge` with `DataUsage` icon; text "Synthetic" always visible                   |
| `PlaybackControls`   | `Toolbar`, `ToolbarButton` + `Play24Regular`, `Pause24Regular`, `ArrowReset24Regular`; `Tooltip` labels |
| `InsightCard`        | `Card`, `CardHeader`, `Body1`, evidence chips as `Button size="small" appearance="outline"` with `Tag`-like styling (must stay real buttons) |
| `EvidenceDrawer`     | `OverlayDrawer` (position end) + `DrawerHeader`/`DrawerHeaderTitle`/`DrawerBody`; `Spinner` while loading; `MessageBar intent="warning"` "Evidence unavailable" on 404 |
| `EventList`          | `Table size="extra-small"` (time · type · player) or `List`; newest last, auto-scroll only when at bottom |
| Errors / notices     | `MessageBar` (`intent="error"` start failure, `"warning"` play failure / reconnecting) |
| Theme                | `ThemeProvider` hook `useThemePreference()` in `src/theme/`                      |

## Rules carried over (must stay true)

1. Card title/body text only from server `InsightPacket`s — never composed client-side.
2. Synthetic label always visible in header and on every card.
3. Evidence chips are real `<button>`s; click and Enter/Space open the drawer.
4. Drawer is a labelled dialog; focus returns to the invoking chip on close (Fluent `OverlayDrawer` handles trap +
   restore; keep the StrictMode/inert unit test, adapted).
5. Text contrast ≥ 4.5:1 in both themes; team colours checked against both Fluent neutral backgrounds.
6. `display_ack` after first paint unchanged.

## Testing

- Existing Vitest suites updated to Fluent roles (`dialog`, `button`, `toolbar`); behaviour assertions unchanged.
- Theme tests: default dark; toggle switches and persists; stored value wins over `prefers-color-scheme`.
- Contrast test: team colours vs `webDarkTheme.colorNeutralBackground1` and `webLightTheme.colorNeutralBackground1`.
- e2e skeleton spec unchanged in behaviour (card text, evidence drawer, keyboard open, focus return, pause/reset) plus
  `@axe-core/playwright` scan with zero serious/critical violations in dark and light.
- Bundle: report gzipped JS size before/after in the batch report (no hard gate; flag if > 350 KB gz).

## Out of scope

Pitch rendering (005), mode/language behaviour (006), evidence page (008). The Fan/Analyst `TabList` and EN/HI `Menu`
are NOT rendered until 006 wires them (constitution VII — no dead UI); the header reserves their slot.

## Governance

- Constitution v1.2.0 (MINOR): platform constraints add Fluent UI React v9 + Fluent icons as the frontend component
  library.
- `specs/README.md`: registry gains the component map above; 005/006/008 plans reference it.
