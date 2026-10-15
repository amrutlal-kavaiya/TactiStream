import { AxeBuilder } from '@axe-core/playwright'
import type { Page } from '@playwright/test'

export async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    // Fluent's Tabster focus sentinels are aria-hidden and forward focus on arrival; axe flags them as aria-hidden-focus.
    .exclude('[data-tabster-dummy]')
    .analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, targets: v.nodes.map((n) => n.target.join(' ')) }))
}
