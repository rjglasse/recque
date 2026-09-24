# RecQue vision

*Agreed with Ric 2026-09-24. Agents plan against this file; only Ric changes it.*

## In one sentence

RecQue teaches through its learners' mistakes: a wrong answer is treated as a diagnosis, the
learner steps down to a simpler question aimed at that exact misconception, and then climbs
back up to the question they missed.

## What it is

RecQue is a learning tool for students, built to be used; Ric uses it himself. It is not a research
instrument. The design rests on one idea about learning, and the tool succeeds when
that idea works for the person using it:

1. **Wrong answers are diagnostic.** Each distractor encodes a specific, plausible
   misconception, so the answer a learner picks says *which* misconception they hold, not
   just that they are wrong.
2. **Descending beats explaining.** A simpler question that targets that misconception, answered
   by the learner, repairs understanding better than being told the right answer.
3. **Climbing back consolidates.** Returning up the stack to the original question (or a
   variation of it) is where the repair shows.

Every change should make this loop work better for someone learning with recque. Proving the
idea in general is not the goal.

## Who it is for

Students: for example, a first-year programming student revising a concept on their own,
who names a topic and wants to find out what they don't understand. Ric's own use stands in
for theirs, but when the two pull apart, the student wins. Examples, topics and evaluation
personas should be student-shaped: novice misconceptions, not an expert's gaps. Teachers
setting topics for a class are not the audience (yet).

## Principles

1. **Question quality over features.** A mediocre question breaks the loop: a distractor that
   targets no real misconception, two defensible answers, or a giveaway length. Work that
   improves question quality beats new screens.
2. **The stack is the product.** Depth, descent and climbing back should be visible and feel
   meaningful (the skyline is the start of this). Nothing should flatten the recursion into
   a plain quiz.
3. **Every question is checked.** The first prototype had a step that verified each question
   (`legacy/recque.py:verify_question`). Generated questions should be checked before a
   learner sees them.
4. **Calm and fast.** Minimal UI; prefetch and the question cache keep waits short. Latency
   and cost per session are product properties, not afterthoughts.
5. **Two equal front ends, one core.** The terminal UI (`recque_tui/ui`) and the web app
   (`recque_web/`) are both first-class, because many students never open a terminal.
   Loop logic lives in the core and application services, never in a front end, and a
   feature is done when both front ends have it (or an issue says why one waits).
6. **Small on purpose.** Single user, single process, about 5k lines. Structure only where it
   serves the loop; no full tactical DDD, no framework (CLAUDE.md already says this).

## Non-goals

- Accounts, multi-user servers, hosting as a general service. The one exception is a
  time-boxed hosted deployment for a student study (direction 6), which Ric approves via
  `bd human`.
- Gamification: points, streaks, badges.
- LMS/Canvas integration. Recque stays standalone; students use it on their own.
- Growing analytics or the knowledge graph for their own sake; they stay only where they
  serve the claim.
- Changes to `legacy/`.

## What "better" means

Tests and lint show a change didn't break anything. They don't show recque got better at
teaching. The final judge is using it, and Ric's own sessions are the first signal.
Agents can't use it the way a learner does, so they judge direction with an
**evaluation harness** they can run:

- **Simulated learners:** a small set of scripted personas, each holding named
  misconceptions in a topic (e.g. "thinks `=` compares in Python"). A model plays each
  persona through a real session.
- **Measures per session:**
  - *validity*: a separate check agrees there is exactly one correct answer;
  - *distractor fit*: each distractor maps to a named misconception;
  - *descent aim*: the simpler question targets the misconception the persona actually chose;
  - *repair*: the persona gets the original question (or its variation) right on the climb back;
  - depth reached, latency, cost.
- A fixed topic and persona set, so scores are comparable run to run. Results are kept in
  the repo as short reports.

Until this harness exists, building it is the top priority, because every later decision
depends on it.

**Budget: at most $1 of live-model spend per evaluation run.** That means a handful of
personas on one topic with a cheap model. The harness estimates cost before a run, stops
when it reaches the cap, and records the actual cost in the report. Development and tests
use mock or recorded sessions and cost nothing. Needing more than $1 is a `bd human`
question for Ric.

## Where it might go next (for agents to refine, not a plan)

1. Evaluation harness (above).
2. Question checking in the live engine, with the harness showing the effect.
3. Misconception-aware descent: carry the chosen distractor's misconception explicitly into
   the simpler question, and make "why that was wrong" visible on the climb back.
4. Finish the architecture issues (recque-9d1, nm1, 5v9, tx0) only as far as 1–3 need them.
   recque-nm1 (application services) matters more now, since both front ends must share
   one path through the loop.
Beyond those, agents may plan toward:

5. **Topic packs:** curated, reusable topics and skill maps for common student subjects (intro
   programming first), so a student doesn't start from a blank prompt. Packs come with
   their misconceptions, which the harness can reuse as personas.
6. **A study with real students,** e.g. in a KTH course, to learn from actual sessions. Agents
   can prepare for it (session logging, export, consent screens), but running it involves
   ethics, consent and course decisions, which go to Ric via `bd human`. A study may use a
   time-boxed hosted web instance with model access Ric provides; that is the only hosting.
7. **Distribution:** make recque easy for students to run themselves: `uvx`/pip install, a
   smooth first run, and clear setup for their own API key.

Anything outside 1–7 is filed as an issue labelled `idea` and waits for Ric.

## How agents work here

recque is Ric's experiment in a project where **agents plan the direction**. This differs from
his other projects on purpose.

- **Agents own the backlog.** They create, split, prioritise, defer and close beads issues
  against this vision, and record their reasoning in issue notes. A planning run reads this
  file, the backlog, recent commits and the latest evaluation reports, then updates the plan.
  Work runs take the top ready issue.
- **Agents push to `main`** (a deliberate exception to Ric's usual rule that nothing merges
  without him), under these gates:
  - `uv run pytest -q` and `uv run ruff check .` pass;
  - `git pull --rebase` first, never force-push, never rewrite history;
  - `bd dolt push` alongside `git push`, so the backlog on GitHub stays current;
  - a change to prompts or question flow comes with an evaluation run once the harness exists.
- **Only Ric edits VISION.md.** An agent that thinks the vision is wrong files an issue labelled
  `vision` explaining why, and carries on under the current text.
- **Decisions an agent shouldn't make** go to Ric through `bd human`: anything this file reserves
  for Ric, spending beyond the budget, licence or public-facing changes (README claims,
  releases).
- The repo is public, so plans, issues and evaluation reports are public too.
