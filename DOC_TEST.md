# Fresh-session doc test (AI-made, Claude, 2026-11-09)

Proves the docs are enough to carry on the work. Run weekly and after each merge.

1. The owner opens a brand-new AI helper session (no memory of this project) and pastes the prompt below.
2. The helper answers from the docs only. It must not read code.
3. A second helper (or the owner, for the plain questions) checks each answer against the code and the owner's memory.
   A wrong or "the docs don't say" answer means a doc gap: fix the doc, not the answer.

Prompt to paste:
---
You are new to this project. Read ONLY ARCHITECTURE.md, HANDOFF.md and REJECTED.md (and files they link). Do not open code.
Answer each in one or two sentences, and say "the docs don't say" when they don't:
1. What is this project, in one sentence?
2. What are its main parts, and which folder holds each?
3. Which things must never be changed or broken?
4. How is a change checked and uploaded?
5. Which plugins or libraries does it use, and why?
6. Name three feature switches and what each turns off.
7. What is being worked on right now, and what is next?
8. Name two ideas that were tried and dropped, and why.
9. Where would a new piece of code for the most recent feature go?
10. What would you need to ask the owner before starting work?
---
Score: answers right / 10. Pass: 8 or more, and no wrong answer about question 3.
