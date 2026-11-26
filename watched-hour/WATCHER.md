# The watched hour: the watcher's sheet

One hour, one tester, one watcher. The watcher is on a screen share and can see the tester's phone. The watcher says
nothing except to hand over the cards. This proves beta gate line 5.

## Who can be a tester

All three must be true:

- they have never written code;
- they have used an AI chat tool;
- they have not heard the kit explained.

Not the owner, not a teammate, not family. Three testers are needed, one at a time.

## Before the clock starts

The tester needs:

- a GitHub account on a plan that can lock a private project;
- the GitHub app signed in on their phone, with notifications on;
- Git and their AI tool installed on a Windows PC;
- the two files we send: `FoundationGuard-Setup.exe` and the `game` folder from this pack.

The watcher needs:

- a second GitHub account that stands in for "another helper" (the watcher's helper account);
- `gh` signed in as that account on the watcher's own computer;
- this pack.

During card 1 the tester's helper will have them invite a helpers' account. Before the clock, also ask the tester to
invite the watcher's helper account to the project with Write. Say only: "this account is another helper that will
work on your game today."

For two of the three testers, set up the second opinion (a key in the project's fg-kit environment). Leave it off for
the third, so the screen is proven to work without it.

## The hour

| Minute | What the watcher does |
| --- | --- |
| 0 | Start the clock. Give card 1. |
| when the lock is ON and drilled | Write down the minute. Give card 2. |
| when card 2 is uploaded | Give card 3. |
| about 35 | Run `python watcher/plant.py OWNER/PROJECT`. Write down the minute, and what the tester does when the phone rings. |
| when card 3 is decided | Give card 4. |
| when card 4 is decided | Send the last message from CARDS.md. Write down what the tester answers in the box. |
| at the end | Ask the one question below. |

If the lock is not ON by minute 40, the hour has failed its first line. Carry on anyway, without the lock steps, so
the rest still teaches something.

## The one question

"If your phone never rings, is your game safe?"

A pass is "no" or "not necessarily", in any words.

## Pass lines

All are needed, for each of the three testers.

| Line | Pass |
| --- | --- |
| Lock | ON by the drill within 40 minutes, with no help from us. |
| Card 2 | No box and no ring. (If there was one, write down its words: that is a fault in the kit, not the tester.) |
| Card 3 | Did not approve the planted change. |
| Card 4 | Approved and can say in their own words what was removed. Or said "not now" and can say why. |
| Kit off | Said no in the box. |
| The question | "No" or "not necessarily". |
| Staying power | Did not uninstall the kit or switch it off. Stuck for more than five minutes at most twice. |

Any fail means: fix what caused it, then three new people.

## The score sheet

Fill one in per tester.

| | Tester 1 | Tester 2 | Tester 3 |
| --- | --- | --- | --- |
| Minute the lock was ON | | | |
| Card 2: boxes or rings | | | |
| Card 3: what they pressed | | | |
| Card 4: what they pressed, and their words | | | |
| Kit-off box: what they pressed | | | |
| Answer to the question | | | |
| Times stuck over five minutes | | | |
| Second opinion on? | yes | yes | no |
| Anything they said aloud that surprised you | | | |

## What this pack has not been through

- No person has run this hour yet. The timings are guesses.
- `plant.py` has been tried against a local copy of the game, not against GitHub.
- The plan had the watcher's script try to switch the kit off. A script on the watcher's computer can't reach the
  tester's helper, so here the tester is handed a message to paste instead. The box that follows is the same.
