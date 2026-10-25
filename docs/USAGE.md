# psych2vslice — Psych Engine → V-Slice converter (stage 1)

Requires Python 3.8+, no dependencies.

```
python3 -m psych2vslice <psych-mod-folder> <output-folder> [--artist NAME]
python3 -m psych2vslice <mod>/data/my-song <output-folder> --song [--artist NAME]
```

Input: `data/<slug>/<slug>.json` (normal), `<slug>-hard.json` etc.
Output: `<out>/data/songs/<slug>/<slug>-metadata.json` (version 2.2.4) and `<slug>-chart.json` (version 2.0.0),
plus `conversion_report.md` / `.json`.

## What is converted
- Notes: time, lane (Psych `mustHitSection` side swap → V-Slice 0-3 player / 4-7 opponent), hold length, note type → `k`.
- BPM changes → `timeChanges`; per-difficulty `scrollSpeed`; difficulties from file names.
- Section camera → `FocusCamera` events; `Camera Follow Pos` → `FocusCamera` (`char: -1`).
- Characters/stage → `playData` (IDs copied as-is).

## Not converted (listed in the report)
- Lua/HScript files (`.lua`, `.hx`, `.hscript`): marked **manual**, never rewritten.
- Other Psych events (dropped), custom note types (kind kept, needs script), altAnim, gfSection, arrow/splash skins.
- Audio files, characters, stages, week/Freeplay data: not yet handled.
- Artist is absent in Psych; defaults to `Unknown`.
- Unverified in the real game: no V-Slice build was run; fields were checked against the Funkin source only.

## Tests
`python3 -m unittest discover -s tests -v`
