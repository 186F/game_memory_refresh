# KCD2 save-analysis guide

Use this guide as the evidentiary standard for Kingdom Come: Deliverance II save recaps. A save contains much more state than the player has actually witnessed. The goal is to recover the latest safe checkpoint and summarize only supported prior events.

## File and game-data layout

### `.whs` container

The observed PC format is:

1. Little-endian `uint32` marker `0xffffffff`.
2. Little-endian `uint32` byte length of an XML header.
3. UTF-8 XML header, normally including a trailing NUL.
4. Repeated chunks, each encoded as:
   - compressed size: little-endian `uint32`
   - uncompressed size: little-endian `uint32`
   - zlib-compressed bytes
5. An observed 64-byte opaque footer: roughly 20 nonzero bytes followed by zero padding.

Validate every declared size and every zlib result. Do not repair or rewrite the source save. The decompressed payload is a proprietary binary serialization containing recoverable strings and an XML-like `ConceptState` tree.

### Installed game data

Steam App ID is `1771300`. A common install contains:

- `Localization/English_xml.pak`, a ZIP archive. Useful entries include `text_ui_quest.xml`, `text_ui_dialog.xml`, and `text_ui_soul.xml`.
- `Data/Scripts.pak`, also a ZIP archive. Quest graphs are commonly under `Quests/Final/Barbora/`.

Localization rows normally store the key in the first `Cell` and English text in the second. Prefer data from the installed build that matches the save. On Windows, Steam install discovery can use the App 1771300 uninstall registry entry.

## What the save state means

`ConceptState` is a persistent world-state graph, not a player-facing journal. It can include dormant branches, defaults, future quest scaffolding, migration flags, streaming state, asset state, and technical cleanup. Internal character, location, quest, or sequence names may therefore reveal material the player has never seen.

Never treat an isolated value such as `Active`, `Done`, `Completed`, `Streamed`, or `Unstreamed` as proof that a story event was witnessed. Never narrate the order of raw strings in the payload; binary serialization order is not story chronology.

## Evidence hierarchy

### High confidence

- The header's current quest key and map identify the current checkpoint.
- Objective `Logs` with update timestamps show that a player-facing objective was reached or updated.
- Used `Sequences` with timestamps show that a scripted scene or interaction ran.
- A saved skill-check result mapped to its exact quest-script branch supports the selected argument and outcome.
- An earlier quest may be summarized when it has explicit objective/dialogue history and its place before the current quest is independently verified.

### Medium confidence

- State transitions inside the verified current quest, when their meaning is confirmed in the matching script.
- Saved stat mutations or start-build flags with an unambiguous localization/script mapping.
- Ambient sequences. Describe these as atmosphere or presence, not as a deliberate conversation unless the script says so.

### Low confidence; do not narrate by itself

- An isolated concept-state value.
- An internal name found only in strings.
- Entity or asset presence.
- Quest availability, streaming, cleanup, or compatibility markers.
- A branch that exists in a script but lacks saved evidence that it ran.

Use calibrated language: “the save confirms” for direct high-confidence evidence, “strongly indicates” for converging evidence, and “likely” for a labeled inference.

## Analysis procedure

1. Parse the header and record save version, build, location/map, play time, and current quest localization key.
2. Decompress all chunks and reconstruct the tokenized `<Roots>...</Roots>` concept-state document. Preserve raw binary only as an optional analysis artifact.
3. Resolve the header key through localization. For generated quest keys such as `qname_prepadeni_KsSs`, remove `qname_` and the final random four-character suffix to obtain the likely internal root `_prepadeni`.
4. Locate that quest root in `ConceptState`. Inspect its objective logs, used sequences, explicit state transitions, and related saved results.
5. Find the most recent player-facing objective update. This is the spoiler boundary unless another timestamped sequence clearly advances it.
6. Map sequence/state names into the matching XML in `Scripts.pak`. Use the concept path and current quest internal name as path hints.
7. When decoding dialogue, read only direct children of the matched sequence:
   - direct `UiPrompt` nodes;
   - direct `Elements/Response/Text` nodes.
   Do not attribute nested alternatives, later responses, or sibling branches to the player.
8. Search for earlier quest candidates only when they have explicit logs or used sequences. Verify their chronological position before including them.
9. Build a private table with: claimed event, concept path, saved state/sequence, timestamp, localization or script match, and confidence.
10. Draft a narrative from the table, then run the spoiler check in `SKILL.md`.

## Worked early-save interpretation pattern

This pattern records conclusions learned from an early save without assuming every save is identical:

- Header key `qname_prepadeni_KsSs` localizes to **Easy Riders** and points to internal root `_prepadeni`.
- Within that root, `_rideToCamp = Done`, `capounPlan = Started`, `InCamp = SmallTalk`, plus a matching objective log, establishes arrival at the camp and the immediate checkpoint.
- A used `dogBarking` sequence and an ambient cook/dog sequence establish background camp activity. They do not prove Henry deliberately spoke to a particular person.
- If dice, meal, training, or later scene sequences are absent, stop before them. Do not name a surprise character, attack, or outcome merely because later branches exist in the quest XML.
- A start-history flag such as `combathenry` mapping to Soldier/Warrior can support the selected background.
- Saved nodes such as `thrr`, `threaten`, `seq38`, and `seq56`, when mapped to the matching negotiation script, can support a military-service argument and successful check.
- Used sequences such as `seq114`, `seq2`, `seq5`, and `seq112`, after direct-child dialogue decoding, can support a responsible or cautious tone without quoting every line.
- A separate earlier prologue root may be summarized only when it has complete objective logs/sequences and verified immediate order. Other roots with technical `Done` values stay out of the recap.

These names are investigative examples, not universal narrative facts. Require the corresponding evidence in the current save.

## External-source use

Installed localization and scripts are the primary decoder. Use an external guide only when local data cannot establish a human-readable chronology. Search narrowly for the exact quest/objective and stop reading at the current checkpoint. Do not import later guide knowledge into the response.

## User-facing output

Lead with the exact checkpoint and broad progress. Follow with a compact chronology, major characters separated into met/present versus mentioned/not yet met, save-specific choices and checks, the current objective/world state, and a confidence note.

Do not expose raw future-facing concept names. A safe boundary sounds like “you have just reached camp and can explore it”; an unsafe boundary names the unseen incident that the quest data schedules next. State that the original save was not modified.
