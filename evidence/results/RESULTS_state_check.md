# The logic check, part 2: "is every piece of state kept?" Results
AI-made (Claude), 11 Nov 2026, v0.8.6. The pass lines were written before any code existed. The full results name a
game's files, so they are kept with the owner; the numbers below are taken from them.

**Judge:** whether a field list to read through (25 fields on the real game, 8 of them the faults an audit had found)
is a fair price, and whether "it matches names" is a limit you are happy to publish.
**Placeholder:** none; every number below is measured. Judging by hand where two lists differed (5 types) is the
author's own and has not been checked by anyone else.

## The samples
- A plain C++ simulation core from a real game, which builds here (15 types).
- The same game's own Unreal headers, 81 files. These were split by a fixed seed into an open half used while building
  and a held-back half, run once at the end.
- The game's two saved-state types, which an earlier audit had read by hand and found 8 unsaved fields in.
- Small C++ and Python fixtures.

## The pass lines
| Line | Asked | Measured |
|---|---|---|
| P1 fields, the compiler as judge | every type equal | 15 of 15 equal with clang's parser |
| P2 the game's headers, held back | no field missed, at least 98% of types equal | 89 of 89 equal, none missed |
| P3 planted omissions | at least 95% reported | 157 of 157. With the harder planting, which takes out only the writing statement, 145 of 150. |
| P4 the real fault | 8 of 8 | 8 of 8, with 17 other fields to read through |
| P5 a running program as judge | every field, both columns | 15 of 15 fields of the edit layer, for both the fingerprint and the save |
| P6 it can guard an upload | all | 12 of 12 exit codes. Each report is the same on a second run. |
| P7 the kit's own rules | all | F152 to F160, each proven by breaking it. All 152 tests pass and the shape check passes. |
| P8 finding types unasked | 4 of 4 | 4 of 4, with 13 other candidates |
| P9 no false "not kept" | 0 wrong | 0 wrong |

## Faults found while building, and fixed (open half and real types only)
- Fields after engine macros (`UPROPERTY(...)`, `GENERATED_BODY()`) were missed (F158).
- A field with brackets in its type or array size was read as a function (F159).
- `operator==` was counted as a field.
- Name matching was too loose. A chained reset (`A = B = 0.5f`), a field that is only zeroed, and a field only
  assigned in a save function all counted as kept (F153, F154).

The judge itself also had faults, and these were corrected and listed:
- Clang's field lister lost track of the current file, so most of a header's types were dropped.
- 5 held-back types under a test switch had to be judged again with that switch on.

## Limits, as measured
- **It matches names.** In the harder planting, it missed these fields:
  - a field still read to make an old save's default;
  - a field rebuilt on load with `.Add(...)`;
  - three fields still named in the loop that counts what to write.
- **It cannot tell scratch values from state that steers the game.** A reader must go through what it lists.
- **Python** was tested on fixtures only.
- **Not seen:** fields held by a base type, and fields made by a macro.
