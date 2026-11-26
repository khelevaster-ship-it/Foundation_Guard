# Evidence for the logic check, part 1 (AI-made, Claude, 11 Nov 2026)
Results: `evidence/results/RESULTS_logic_check.md`. Here:
- `PASSLINES.md`: the pass lines, written before the tool was built, with two dated amendments and the outcome.
  Public copy: three names of a private project's folder, files and switch are replaced by neutral words.
- `own_code/`: every run on FoundationGuard's own code (reports, JSON, start and end times), the control with tests
  that check nothing, the refusal, the list of the 22 step-gate tests, and the replays for pass line M2.
- `fixture/`: the small project and the outputs for pass lines M4 to M7, both draws.
- `harness/`: `replay.py` (M2: replays drawn verdicts without the tool's code), `ifblocks.py` (M10: reads the
  compile-time switches of the source itself), `m4567.py` (M4 to M7), `null_import.py` (the Python control).
Not here: the line-by-line reports on the game's hydrology core and the tests written for pass line M8. They quote
the game's code and are kept with the owner. Their counts are in the results file.
