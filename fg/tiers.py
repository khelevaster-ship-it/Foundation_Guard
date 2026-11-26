"""FoundationGuard: three kinds of guard file, by who really writes them (AI-made, Claude, 2026-11-13; outside review 6,
findings 2 and 6, Grok, and its fix plan).

  - records: only the kit's own scripts write them (what passed, the owner's yes and its one-time note, the frozen
    numbers, the break-glass log). Every honest writer goes through the record door (fg/steps.py recorded()).
  - switches: they turn the kit off (its settings, its code, git's hooks, the hook wiring in the AI tools' settings),
    or decide who GitHub asks and what runs there (.github/workflows, CODEOWNERS; Plan 2 PR 7, 17 Nov).
  - the owner's own: everything else (tests, check scripts, lists, APPROVED.md).

What changed between two helper steps is judged by its kind (fg/between.py): a record is put back, a switch is put
back unless it is as the remote branch has it, and the owner's own stays (held for the owner's yes at the upload when it
is more than new tests).
"""
import os

import paths as P

RECORD_NAMES = ("passed_commit", "gate_results.json", "fingerprint.json", "tiny_files.json", "owner_ok.json",
                "ownerok_asking", "ran_tests.json", "python_startup.json")
BASELINES = ("structure_baseline.json", "STRUCTURE_LOG.md", "docs_baseline.json", "assets_baseline.json",
             "rules_baseline.json", "BREAKGLASS.md")
SWITCHES = ["foundationguard.json", "fg/**", ".git/hooks/**", ".claude/settings.json", ".claude/settings.local.json",
            ".github/hooks/**", ".codex/**", ".cursor/hooks.json"]
GITHUB_SWITCHES = [".github/workflows/**", ".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]


def _sd(cfg):
    return (cfg.get("state_dir") or ".foundationguard").strip("/")


def is_record(rel, cfg):
    return rel in BASELINES or any(rel == _sd(cfg) + "/" + n for n in RECORD_NAMES)


def kind(rel, cfg):
    """'record', 'switch' or 'own' for a guard file (a path relative to the project)."""
    rel = rel.replace(os.sep, "/")
    if is_record(rel, cfg):
        return "record"
    if P.matches(rel, SWITCHES) or (P.matches(rel, GITHUB_SWITCHES) and os.environ.get("FG_BREAK", "") != "tier_workflow_switch"):
        return "switch"
    return "own"


def gate_record(rel, cfg):
    """A file the project's own gate writes on every run ("gate_records" in foundationguard.json; the game's PC, 13 Nov)."""
    if os.environ.get("FG_BREAK", "") == "gate_records":
        return False
    rel, recs = rel.replace(os.sep, "/"), [g for g in (cfg.get("gate_records") or []) if isinstance(g, str)]
    if rel in recs:
        return True
    if os.environ.get("FG_BREAK", "") == "gate_records_globs":
        return False
    # the game's PC, 23 Nov: the nightly writes Saved/Nightly.log and several files under Saved/FullTier/ for hours; a
    # pattern ("Saved/FullTier/**") names them all. The kit's own files, settings and records never count as one.
    import paths as P, config as C
    globs = [g for g in recs if any(c in g for c in "*?[")]
    if not globs or P.matches(rel, C.ALWAYS_GUARDED + ["fg/**", "foundationguard.json", ".claude/**", ".git/**"]):
        return False
    return P.matches(rel, globs)
