# Hindi Glossary & Review Plan (006)

Deliverable: `docs/glossary-hi.md` (source of truth for canonical terms) plus reviewed
`backend/src/tactistream/narrative/catalog/hi.json` and `frontend/src/i18n/hi.ts`. This file is the plan and the
proposed initial term table; the docs file is what tests read.

## Principles

1. **One canonical Hindi term per concept**, used in narrative templates and UI chrome alike. Fan templates may avoid a
   technical concept entirely (e.g., say "पास के लिए जगह" instead of naming the channel) but never use a competing term.
2. **Common football Hindi over literary Sanskritised Hindi**: transliterate established English football loanwords
   (पास, शॉट, डिफ़ेंडर) and translate plain concepts (दबाव, जगह, दौड़).
3. **Numbers and identities are invariant**: Western Arabic digits with "." decimals; player names "{टीम} {shirt}"
   (ब्लू 9); evidence IDs untranslated.
4. **Hedged causality survives translation**: "helped create" → "बनाने में मदद की"; never "बनाया" (created) for
   interpretations; "Interpretation" label always shown.
5. **Units**: metres → "मीटर" (full word, avoids ambiguity of "मी"); score units → "स्कोर (0–100)".

## Proposed canonical terms (initial; to be confirmed in review)

| English (en) | Canonical Hindi | Notes / rejected alternatives |
|---|---|---|
| Blue (team) | ब्लू | transliteration keeps the colour-name brand; rejected नीला (adjective form varies by gender) |
| Amber (team) | एम्बर | transliteration; rejected पीली/कहरुबा (unfamiliar) |
| off-ball run | बिना गेंद की दौड़ | plain and self-explanatory; rejected ऑफ़-बॉल रन (jargon for fans) |
| passing channel | पासिंग चैनल | analyst term; fan templates use "पास के लिए जगह" |
| pressure | दबाव | standard |
| space | जगह | standard; rejected स्पेस |
| interpretation | व्याख्या | label text; rejected अनुमान (implies guess) |
| synthetic (data) | सिंथेटिक | badge; tooltip "कृत्रिम रूप से बनाया गया मैच डेटा" |
| insufficient tracking | अपर्याप्त ट्रैकिंग | message: "इस व्याख्या के लिए ट्रैकिंग पर्याप्त नहीं है" |
| partial tracking | आंशिक ट्रैकिंग | badge |
| verified fact | सत्यापित तथ्य | evidence status |
| evidence | साक्ष्य | drawer title; rejected सबूत (legal connotation) |
| forward pass | आगे की ओर पास | |
| defender | डिफ़ेंडर | |
| metre(s) | मीटर | unit label |
| recap | रीकैप | rejected सारांश (means "summary", used for `summary` text) |
| summary | सारांश | |
| Fan (mode) | फ़ैन | |
| Analyst (mode) | विश्लेषक | |
| pin / unpin player | खिलाड़ी पिन करें / पिन हटाएँ | |
| key moment | अहम पल | |
| replay / tactical replay | रीप्ले / टैक्टिकल रीप्ले | |
| Why? | क्यों? | |
| direct (involvement) | सीधी भागीदारी | badge |
| off-ball (involvement) | बिना गेंद की भागीदारी | badge |

Reference sentences (fan/analyst, hero):

- en fan: "Blue 9's run helped create room for the pass." → hi fan: "ब्लू 9 की बिना गेंद की दौड़ ने पास के लिए जगह बनाने में मदद की।"
- en analyst: "The defender shifted toward Blue 9 while the central channel widened. The next forward pass used that space."
  → hi analyst: "डिफ़ेंडर एम्बर 4 ब्लू 9 की ओर खिसका, जबकि बीच का पासिंग चैनल 1.9 मीटर से 5.3 मीटर तक चौड़ा हुआ। अगले आगे की ओर पास ने उसी जगह का इस्तेमाल किया।"
  (Analyst en template likewise names Amber 4 and the metre values, so number/identity multisets match.)

## `docs/glossary-hi.md` format (machine-checked)

```markdown
# Hindi Glossary
Review status: internal review · Reviewer: <initials> · Date: 2026-10-2x

| en | hi | context | rationale |
|---|---|---|---|
| off-ball run | बिना गेंद की दौड़ | narrative, chrome | … |
```

`backend/tests/unit/test_glossary_consistency.py` parses the table: for each row, every en catalog template (both
modes) whose text contains the `en` term (case-insensitive, word boundary) MUST have a hi counterpart containing the
`hi` term; and no hi template may contain a listed rejected alternative (column `rejected`, optional, comma-separated).

## Review protocol

1. Draft (005/004 drafts exist) → builder self-review against the principles above → fix.
2. Read every template aloud in context (fan and analyst, all slots from the hero, press and switch seeds) using
   `uv run tactistream-catalog preview --language hi` (prints rendered examples per key).
3. Record the outcome in `docs/glossary-hi.md` header and catalog `_meta.review` as `internal_review` with reviewer
   initials and date. Use `native_review` / `expert_review` only when that reviewer is named in the doc with consent.
4. Log any template that fails review in `docs/glossary-hi.md` "Open issues"; by 21 Oct such templates are removed
   from the active set (stop rule) and their claims fall back to reviewed factual templates.

## Font

Noto Sans Devanagari (SIL Open Font License 1.1), self-hosted via `@fontsource/noto-sans-devanagari` (weights 400, 600),
stack `"Inter", "Noto Sans Devanagari", system-ui, sans-serif`; entry in `docs/permitted-assets.md` with licence URL.
