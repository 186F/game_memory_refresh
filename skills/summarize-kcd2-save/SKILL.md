---
name: summarize-kcd2-save
description: "Analyze Kingdom Come: Deliverance II `.whs` save files and produce evidence-based, spoiler-safe recaps or compact multi-page HTML compendiums covering only the story, characters, choices, quest progress, and build decisions the player has already encountered. Use for KCD2 save inspection, checkpoint identification, ''what happened so far'' summaries, encyclopedia-style returning-player guides, save comparisons, or decoding internal quest/dialogue state against an installed game''s localization and Scripts.pak data."
---

# Summarize KCD2 Save

Decode a KCD2 save without modifying it, establish the latest evidenced checkpoint, and produce a prose recap or browsable compendium containing only events at or before that checkpoint.

## Required workflow

1. Read [references/analysis-guide.md](references/analysis-guide.md) completely before interpreting state. Its evidence hierarchy and spoiler rules are mandatory.
2. Preserve the original save. Analyze it in place read-only or make a working copy in a dedicated output directory.
3. Run the bundled parser:

   ```powershell
   python scripts/analyze_whs.py "C:\path\to\save.whs" --output "C:\path\to\analysis" --game-dir "D:\path\to\KingdomComeDeliverance2"
   ```

   Omit `--game-dir` when registry discovery can find Steam App 1771300. Add `--include-payload` only when deeper binary inspection is necessary. Use `--force` only for a known analysis-output directory, never for the save.
4. Inspect `safe_summary.json` first, then `evidence.json` and `concept_state.xml`. Treat `strings.tsv` as an investigative index, not a chronology.
5. Resolve unclear localization keys or saved sequence names with `scripts/inspect_game_data.py`:

   ```powershell
   python scripts/inspect_game_data.py --game-dir "D:\path\to\KingdomComeDeliverance2" localize qname_prepadeni_KsSs
   python scripts/inspect_game_data.py --game-dir "D:\path\to\KingdomComeDeliverance2" list-scripts prepadeni
   python scripts/inspect_game_data.py --game-dir "D:\path\to\KingdomComeDeliverance2" sequence seq38 --path-hint vyjednavani_s_bergovovymi_muzi
   python scripts/inspect_game_data.py --game-dir "D:\path\to\KingdomComeDeliverance2" search-content objectiveVisual1 --path-hint trosecko/prepadeni
   ```
6. Build a chronological evidence table privately: event or choice, save path, state or sequence evidence, localization/script match, and confidence.
7. Choose the deliverable:
   - For a written recap, follow the output standard below.
   - For an HTML guide, encyclopedia, wiki, or compendium, follow the compendium workflow below.
8. Perform the spoiler-boundary check on the final prose and every generated page.

## Evidence requirements

- Treat the header''s current quest key and map as authoritative for the current checkpoint.
- Require user-facing objective logs, timestamped used sequences, or a matching localized/scripted transition before claiming an event occurred.
- Use installed localization and quest scripts as the primary decoder. Match the game build recorded in the save when version differences could matter.
- Use external guides only to establish human-readable chronology that local data cannot establish. Stop reading at the current checkpoint.
- Label inferences. Prefer "the save confirms," "strongly indicates," or "likely" according to the evidence quality.
- Never equate isolated `Active`, `Done`, `Completed`, `Streamed`, or `Unstreamed` values with a witnessed story event.
- Never expose characters, locations, twists, quest names, or outcomes found only in dormant/default/future world-state branches.

## Spoiler-boundary check

Before responding, verify all of the following:

- Every narrated event is supported by the save and occurs no later than the latest started objective.
- Earlier quest candidates have explicit objective/dialogue history and a verified place before the current quest.
- Mentioned characters were met, visibly present, or explicitly discussed; distinguish "mentioned but not met."
- The "not yet seen" boundary does not name a surprise or later outcome.
- Raw concept-state names that could reveal unseen material are omitted from the user-facing answer.

## Prose output standard

Lead with the exact checkpoint and overall progression. Then provide:

1. A short chronological "story so far."
2. Major characters grouped as met/present versus mentioned/not yet met.
3. Save-specific choices, successful or failed checks, and starting build decisions.
4. The current objective and immediate world state.
5. A concise confidence/limitations note.

State that the original save was not modified. Mention analysis artifacts only when useful or requested.

## HTML compendium workflow

When the user asks for an HTML guide, encyclopedia, wiki, compendium, or returning-player site:

1. Read [references/compendium-guide.md](references/compendium-guide.md) completely. It defines the content schema, editorial boundary, page architecture, UX standard, and final audit.
2. Convert the vetted evidence table into a UTF-8 JSON content file in the writable workspace. Include only claims already cleared by the spoiler-boundary check.
3. Generate the site with the bundled deterministic builder:

   ```powershell
   python scripts/build_compendium.py --content "C:\path\to\content.json" --output "C:\path\to\compendium"
   ```

   The default output is a compact five-page encyclopedia with shared local assets. Use `--logo` only when substituting another locally available logo. Use `--force` only for a known compendium-output directory created by this builder.
4. Inspect `index.html` first, verify all five pages and local links, and audit the rendered text again for future names, locations, quest titles, and outcomes.
5. If the user asks to open it, open the generated `index.html`. Preserve the JSON content file so the compendium can be regenerated or updated from a later save.
6. Deliver the path to `index.html`, summarize what was generated, and state that the original save was not modified.

## Failure handling

- If chunk validation or zlib decompression fails, the initial analysis must stop and report the exact offset; do not attempt repair.
- Do not equate an unfamiliar size marker with corruption. If the user explicitly authorizes compatibility investigation, follow the bounded, read-only format-extension procedure in `references/analysis-guide.md`, prove the next boundary, add a synthetic regression test, and validate the complete save before updating the installed parser.
- If the game installation is unavailable, still parse the save and report unresolved keys. Search the exact key narrowly or request the game directory rather than guessing.
- If evidence conflicts, choose the earlier safe boundary and explain the uncertainty.
- If compendium validation fails, fix the content or builder input; do not hand off a partially linked site.
