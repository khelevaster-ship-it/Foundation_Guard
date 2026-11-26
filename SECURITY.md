# Security

## What FoundationGuard protects against
Mistakes: an AI helper or a tired person force-pushing, pushing untested code, deleting history, adding unapproved
software, leaking a key, weakening a check, or letting an approved behaviour break without anyone noticing.

## What it does not protect against
It is a guard against mistakes, not a sandbox. It checks command text, files and diffs. A determined or malicious
program can get round a text check, and a person can skip a git hook with `--no-verify`. Anything on the same machine
can edit the kit. The real lock is server-side branch protection on GitHub; see `docs/GITHUB_PROTECTION.md`.
The kit also trusts that the owner reads the prompts and cards it writes.

## Reporting a bypass
A command that should be blocked but isn't, or a way to change a guard file without the owner's OK, is worth
reporting. Please report it privately: open a private security advisory on the GitHub repository. Do not post working
bypasses in a public issue first. Include the command or steps, what you expected, and what happened.
Known limits are listed in the README, and in full in docs/GUIDE.md.
