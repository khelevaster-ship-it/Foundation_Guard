# Contributing

Thanks for helping. Contributions made with AI tools are welcome. Please say so in the pull request, and name the tool.

## Run the tests
    python3 -m pytest -q tests

Python 3 and pytest. The kit itself uses only the standard library. On a computer without pytest (a game PC with
only the engine's own Python), `python tests/run_without_pytest.py` runs the same checks with plain Python, and lists
any it can't run there. For those, rely on the kit's CI for the same commit. A Python whose path holds a space
(C:\Program Files\...) is fine.

## The project's own rule
Every new check or fix ships with a row in `APPROVED.md`: the behaviour, who asked for it, the check's name, and a way
to break the feature on purpose (`env:FG_BREAK=name` or `patch:path`). The kit's code turns the feature off when the
break is set. Then prove it:

    python3 fg/prove.py --all

The check must pass normally and fail when the feature is broken. Put the failing output in the pull request. A change
with a missing or stale check will not be merged. Patch-style breaks need remaking if the code they patch moves.

## Structure rule
The kit holds itself to its own code-shape limits (file, class and function size, tangle, copy-paste, loops). Those
numbers may only shrink. Split code rather than raising a limit, and do not chop code into tiny files to dodge a limit.

## Repository layout (the owner's standing rule, 11 Nov 2026, for every tool added to this repo)
A stranger should understand the repo from its front page. So:
- `README.md` is a short front page: what it is and who it's for, a quick start, what it stops, a small proof table
  (one line and a link per claim), what it is not, limits and licence. Long detail goes in `docs/`.
- `evidence/` holds every result: `evidence/results/` for the results write-ups, one folder per test for its pass
  lines, harness and raw runs, and `evidence/EVIDENCE.md` as the index (claim, measured result, file). Say at the top
  that the results are AI-made and judged by their author.
- `docs/` holds the guides (`GUIDE.md`, `HABITS.md`, `BEGINNER_TEST.md`, `GITHUB_PROTECTION.md`) and the pass-lines rules.
- The root keeps only what GitHub or the kit expects by name: `AGENT_SETUP.md`, `APPROVED.md`, `CHANGELOG.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `REVIEW_PROMPT.md`, `DOC_TEST.md`, `DEPENDENCIES_AND_LICENCES.md`,
  the kit's settings and its code folders.
- A new result goes in `evidence/results/` with a row in `evidence/EVIDENCE.md`; a claim on the front page links to it.

## Other
Keep the docs true: if you change a switch, file or behaviour, update the README or docs/GUIDE.md, or the module docstring, in the same
change. Plain words, short sentences. Do not add outside dependencies.
