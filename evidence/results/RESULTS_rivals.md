# Comparisons with other tools (11 Nov re-check, AI-made)

Earlier comparisons used pattern-for-pattern ports of other tools, not the tools themselves. For release each was
either run for real or checked by reading.

| Tool | How it was checked now | Result |
|---|---|---|
| lizard 1.17.13 (code shape) | Installed and run for real on the same 180 seeded code-shape cases (seed 20261108) | lizard caught 42 of 120 tangled or over-long cases (22 of 100 without the long-function kind); FoundationGuard 120 of 120. Both flagged the same 4 of 60 clean cases (long functions in "clean" cases made before the tangled-code check existed). Identical to the 8 Nov port's numbers. |
| git-guardrails-claude-code (MIT), cc-safe-setup 30.0.7 (MIT) (command guards) | Downloaded and read line by line against the port; not run (running downloaded hook code was not allowed in the test machine) | Every command pattern in both matches the port exactly. The only extra rule is a file-write rule for `.env`, which does not apply to commands. The earlier 25/40 and 14/40 scores therefore stand, marked "port, checked by reading". |
| Other code-quality and architecture tools named in early drafts | Could not be run here (one needs a server, one works only on Java) | Removed from every comparison and document. No score is claimed. |

Evidence: evidence/rivals/ (benchmark script and per-case results).

## Market scan, 11 Nov (web search, not tested)
Similar tools found, none run or scored here: karanb192/claude-code-hooks (a hook catalogue, including a rule that
blocks edits to test files), googlarz/vibe-safe (a session guardian for non-technical contributors, early stage),
Swarm Orchestrator (flags relaxed tests and stripped asserts in pull-request diffs), a "vibe-coding-guardian" skill,
and commercial pull-request quality gates. Guides widely recommend the same layers this kit uses: a hook outside the
model's choices, protected config files, and a required check on the server. None found combines owner-approved
behaviours with break-to-prove and plain-words cards for a non-programmer owner; that is a claim from one scan only.
