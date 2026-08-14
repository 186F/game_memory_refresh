# Game Memory Refresh

Game Memory Refresh is a collection of Codex skills for reconstructing a player''s progress from game save files. Each skill aims to answer one practical question: **what have I already seen, and where was I when I stopped?**

The collection is organized so support for additional games can be added without coupling their parsers, evidence rules, or presentation assets.

## Included skills

### Kingdom Come: Deliverance II

[`skills/summarize-kcd2-save`](skills/summarize-kcd2-save) analyzes Kingdom Come: Deliverance II `.whs` saves and produces spoiler-safe output limited to the player''s evidenced checkpoint.

It includes:

- Read-only `.whs` parsing and chunk validation
- Quest, dialogue, character, choice, and build-state evidence extraction
- Localization and `Scripts.pak` inspection helpers
- Written "game so far" recaps
- Compact five-page HTML encyclopedia generation
- A strict boundary against unseen characters, places, twists, and outcomes

## Repository layout

```text
game_memory_refresh/
├── README.md
└── skills/
    └── summarize-kcd2-save/
        ├── SKILL.md
        ├── agents/
        ├── assets/
        ├── references/
        └── scripts/
```

Every supported game should live in its own directory beneath `skills/` and remain independently installable.

## Installing a skill

Copy the desired skill directory into your personal Codex skills directory. For example, on Windows:

```powershell
Copy-Item -Recurse ".\skills\summarize-kcd2-save" "$env:USERPROFILE\.codex\skills\summarize-kcd2-save"
```

Restart or refresh Codex skill discovery after installation. Invoke the included skill as `$summarize-kcd2-save`.

## Adding another game

New game integrations should follow the same operating principles:

1. Create one self-contained directory under `skills/`.
2. Keep the original save read-only and exclude personal saves from version control.
3. Document the game''s save format, evidence hierarchy, and spoiler boundary.
4. Bundle deterministic inspection scripts and reusable presentation assets when useful.
5. Distinguish confirmed events from inference and dormant future state.
6. Validate the skill and test its output before publishing changes.

Game-specific parsing logic should stay inside that game''s skill rather than becoming a shared assumption.

## Disclaimer

This is fan-made tooling and is not affiliated with or endorsed by Warhorse Studios or Deep Silver. Game names, logos, and related marks belong to their respective owners.
