# Licence ledger: results (AI-made, Claude, 9 Nov 2026)
Fresh cases written by a separate agent that never saw the code (fresh_set/, 6 projects: Unreal, Unity, Godot, web 2D, music-heavy,
fonts/video; sha256 of the file list 7a709ccc...9bee). Scores before any fix are the reported ones.

| Line | Needed | Before fixes | After fixes (post hoc) |
|---|---|---|---|
| 1. New asset files without a row caught / false alarms | 95% / 5% | 21/21 / 0 of 46 decoys PASS | same |
| 2. Licence problems caught / false alarms | 90% / 5% | 23/25 (92%) / 0 PASS | same (the 2 are kept as design choices, below) |
| Warnings (row covers nothing, share-alike) | - | 9/9 | same |
| 3. Credits list right | every CC BY author+link, every AI tool | FAIL: "made with Sam" when the tool was only in Notes; rows the gate fails still printed (blank author, "-" link) | fixed (F050) |
| 4. Beginner test (pixel_quest sample: trees, icons, sounds, music, font; helper read only README/AGENT_SETUP) | owner reads no code or licence text | PASS: 6 rows filled from plain answers, the non-commercial track caught and the owner told to replace it, credits written; 9 doc gaps | gaps fixed post hoc (selling question and setting, columns explained, no-internet note, credits drop Notes, --help, date twice) |
| 5. Real-project trial (report only) | - | ran on a real Unreal project's asset folders; no files were recorded yet, so all started as "to fill in" | |
| 6. No harm | all | 51 tests pass, 50/50 proven; earlier fresh sets unchanged | |

The two licence "misses" are disagreements on spelling, not slips: the case writer wanted "public domain" and a bare "CC-BY" with
no version to fail as unrecognised; the checker accepts "public domain" as CC0 and versionless CC BY as CC BY. Stricter is
arguably safer (public-domain claims vary by country; CC BY versions differ slightly), so it is noted for the owner to choose.
