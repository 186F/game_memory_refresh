# KCD2 save compendium guide

Read this file when the user asks for an HTML guide, encyclopedia, compendium, wiki, returning-player site, or multi-page “game so far” artifact.

## Construction workflow

1. Complete the save-analysis workflow and spoiler check in `SKILL.md` first.
2. Convert only supported conclusions into a UTF-8 JSON content file using the schema below. This is a narrative evidence product, not a dump of `evidence.json`.
3. Keep each paragraph short and encyclopedic. Separate encountered/present characters from figures only discussed.
4. Run:

   ```powershell
   python scripts/build_compendium.py --content "C:\path\compendium.json" --output "C:\path\kcd2-compendium"
   ```

   The builder copies reusable assets from `assets/compendium/`, generates five pages, and validates local links and anchors. Add `--force` only for a known generated compendium directory.
5. Open `index.html` when requested. Preserve earlier user-authored artifacts unless replacement is explicit.

## Content schema

All fields below are required unless marked optional. Arrays may be empty only when the save has no supported evidence for that category.

```json
{
  "title": "The game so far",
  "subtitle": "An indexed account limited to events already encountered.",
  "save": {
    "quest": "Current localized quest title",
    "objective": "Latest player-facing objective",
    "position": "Exact safe checkpoint",
    "region": "Localized region or map",
    "build": "Game build",
    "save_type": "Exit save",
    "background": "Confirmed build/background",
    "last_result": "Most recent confirmed outcome",
    "source_note": "Original save was analyzed read-only and was not modified."
  },
  "summary": ["Two or three evidence-based overview paragraphs."],
  "spoiler_boundary": "Plain-language statement of where knowledge ends without naming what happens next.",
  "chronicle": [
    {
      "id": "safe-kebab-id",
      "label": "Short phase label",
      "title": "Event title",
      "paragraphs": ["What occurred and why it matters."],
      "objectives": ["Optional confirmed objective"]
    }
  ],
  "people": {
    "encountered": [
      {"id": "henry", "initials": "HS", "name": "Henry", "role": "Protagonist", "summary": "Supported description."}
    ],
    "discussed": [
      {"id": "patron", "name": "Known figure", "role": "Mission relevance", "summary": "What the player has heard."}
    ]
  },
  "politics": [
    {"group": "Known interest", "figures": "Named people", "knowledge": "Only what the player knows."}
  ],
  "henry": {
    "profile": ["Save-specific interpretation grounded in confirmed choices."],
    "traits": ["Professional", "Cautious"],
    "choices": [
      {"title": "Choice title", "summary": "Selected approach", "outcome": "Confirmed result"}
    ]
  },
  "resume": {
    "what_doing": "Mission context",
    "just_happened": "Latest completed event",
    "next_action": "Exact current objective in practical terms",
    "known_state": [
      {"label": "Position", "value": "Current location"}
    ]
  },
  "confidence": "Concise evidence and limitation note."
}
```

## Editorial rules

- Treat every string as user-facing copy. Never insert raw future-facing concept paths.
- Use localized quest, objective, character, and location names.
- Put disputed or inferred material in prose with calibrated language; do not present it as an infobox fact.
- Give encountered characters initials; do not use invented portraits.
- Keep the chronology ordered by objective/sequence evidence, not payload order.
- Describe ambient sequences as atmosphere only.
- Keep the current objective prominent on every page.
- State that the original save was not modified.

## UX standard

The bundled template intentionally resembles a compact reference encyclopedia:

- persistent desktop sidebar and mobile drawer;
- search across generated entries using `/` or Ctrl+K;
- separate overview, chronology, people, Henry, and checkpoint pages;
- compact infoboxes, tables, contents lists, and evidence notes;
- responsive and printable layouts;
- no external runtime dependencies.

Do not add generic dashboard widgets, oversized hero sections, invented coat-of-arms art, or speculative metrics. Prefer dense, readable reference presentation. Use the bundled KCD2 logo lightly and include the unofficial fan-made disclaimer.

## Final spoiler audit

Before delivery, inspect the generated pages and confirm:

- every timeline event is in the private evidence table;
- every encountered character has direct evidence;
- every discussed character is clearly labeled as discussed;
- the checkpoint page ends at the latest objective;
- search entries do not expose excluded names or later quests;
- the spoiler boundary does not reveal the nature of the next event.
