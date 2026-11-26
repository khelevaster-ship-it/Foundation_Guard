# Pass lines for the two new rule checks (written 9 Nov 2026 ~05:00 UTC, before any build or run; AI-made, Claude)

From an outside review the owner passed on (9 Nov 04:54): (2) unsafe/non-deterministic maths creeping into simulation code;
(3) agents adding plugins, engine modules or outside libraries without the owner's OK.

Test sets are written by a fresh agent that never sees the code, only a plain description of what must be caught.
Each set is frozen with sha256 before scoring. Scores before any fix are the reported ones; later fixes are post hoc.

| Check | Line | Pass |
|---|---|---|
| Maths rule | Planted new unsafe calls found (in the named simulation folders) | 85% or more |
| Maths rule | Decoys wrongly flagged (comments, strings, other folders, allowed wrappers, look-alike names, unchanged old code) | 10% or fewer |
| Allow-list | Planted new plugins / engine modules / outside libraries found | 85% or more |
| Allow-list | Decoys wrongly flagged (comments, disabled plugins, reordering, own modules, removals) | 10% or fewer |
| Both | Each check proven by break-to-prove (fails with its switch on) | all |
