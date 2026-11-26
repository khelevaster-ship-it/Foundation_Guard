# Web pack: results (11 Nov 2026)

**AI-made and judged by its author.** Claude wrote the web pack, its tests, both sample games and this report. No
human and no second AI has checked them. The sample games are small and were written for this test, so they show the
pack works end to end; they do not show it holds up on a real web project.

The owner asked for it on 11 Nov: "create a version for web apps", meaning the same kit, working with them. Approved
rows F185 to F193 each have a check proven by breaking its feature on purpose (`python fg/prove.py --all`).

## What was run
Linux, Python 3.12, Node.js 22.23, Vitest 5.1.0, Playwright 1.63.0 with its Chromium. Both games are in
[../web_pack/](../web_pack/) without their installed packages.

### Tide Pool: a canvas game in one page, tested with Node's own test runner
`index.html` holds the game loop in a `<script type="module">`; its rules are in `sim/world.js`; two tests in
`test/world.test.js` import `node:test`.

| Step | Result |
|---|---|
| `python fg/setup.py --solo` | "this is a web (JavaScript or TypeScript) project"; `sim/**` under the browser maths rule; tests found (Node's test runner), all pass; `node_modules/` added to `.gitignore`. |
| Approve "the tide rises" with an off-switch (`env:TIDE_NO_TIDE=1`) | Proven: the test passes, and fails with the tide switched off. |
| A helper's change ([tide_pool_helper_change.patch](../web_pack/tide_pool_helper_change.patch)): a wave made with `Math.sin`, `Math.random` and `**`, and Phaser loaded from a CDN | Not uploaded. The rules check: "sim/world.js has 3 (was 0)" and "new dependency web:phaser"; the owner's card for it gives version 3.80.1 and the address. The game's own test "same_world_every_time" also failed (the random wave). |

### Star Herder: a Phaser-style project with Vitest and a real browser test
`package.json` lists Phaser, Vitest and Playwright; `src/sim/herd.js` uses a seeded generator; Vitest tests sit beside
it; `tests/game.spec.js` opens the page in Chromium and waits for the game to draw frames.

| Step | Result |
|---|---|
| `python fg/setup.py --solo` | "made with Phaser"; `src/sim/**` under the maths rule; tests found (Vitest + Playwright). The first run FAILED: Vitest also picked up the Playwright file. The gate showed it, and the sample was fixed with a `vitest.config.js` (a project setting, not a kit fault). |
| The joined report | Each test known by its own title (Vitest's "herd > stars_drift_right" becomes "stars_drift_right"); one check run alone passes for a Vitest test and for a Playwright test, and a name that matches no test fails. |
| Approve "the game draws frames in a real browser" with a patch break ([breaks/no_frames.patch](../web_pack/star_herder/breaks/no_frames.patch)) | Proven in Chromium: the test passes, and fails with the patch applied; the patch is taken off again. |

### The guard
Ten publish and deploy commands (`npm publish`, `npx vercel --prod`, `vercel`, `npm run deploy`, `npx gh-pages -d dist`,
`butler push`, `netlify deploy --prod`, `firebase deploy`, `npx wrangler pages deploy`, `npx surge`) were blocked with
the reason and what to do instead. `npm run dev`, `vercel dev`, `npm test`, `npm run build` and `npx playwright test`
were not.

## A fault found on the way
A JavaScript regex holding a quote, such as `s.replace(/"/g, ...)`, made the code reader think a text had started, so
every function after it vanished from the size and tangle checks, and maths in them from the maths rule. Code inside a
template's `${...}` was not read at all. Both are fixed and guarded (F188).

## Not done yet
- No real web project, and no web run on Windows or macOS.
- No fresh-case round: the planted cases in `tests/test_kit.py` were written by the same author as the code. The
  engine packs had one (`RESULTS_engine_packs.md`); the web pack should get one too.
- The known limits are in [docs/GUIDE.md](../../docs/GUIDE.md#all-known-limits).
