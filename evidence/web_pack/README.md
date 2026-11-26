# Web pack sample games (11 Nov 2026)

AI-made: two small games written to try the web pack end to end. Results: [../results/RESULTS_web_pack.md](../results/RESULTS_web_pack.md).

- `tide_pool/`: a canvas game in one page, tested with Node's own test runner (nothing to install).
  `tide_pool_helper_change.patch` is the helper's change the kit stopped (risky maths and a script from a CDN).
- `star_herder/`: a Phaser-style project with Vitest and a Playwright test in a real browser.
  `breaks/no_frames.patch` breaks the drawing, to prove the browser check.

To rerun one: copy its folder somewhere, `git init` and commit it, run `npm ci` (star_herder only; it needs Python 3 for
its little web server), then `python path/to/fg/setup.py --solo`.
