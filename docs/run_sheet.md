# Demonstration run sheet

Issue #54, epic #39.

The order the demonstration is run in, with what to say at each surface and what to do when something is not there.
It exists so the demonstration does not depend on anybody remembering the order, and so it can be executed by somebody who did not build the dataset.

The dataset, its phases and its expectations are in [demonstration_dataset_plan.md](demonstration_dataset_plan.md).
The mechanisms are in [replay.md](replay.md) and [corpus_format.md](corpus_format.md).
Vocabulary is in [CONTEXT.md](../CONTEXT.md).

---

## Before the room

Everything here is done before an evaluating officer is present, and none of it is run live in front of one.

| Step | Command | Expected | Time |
|------|---------|----------|------|
| 1 | `make up` then `make health` | every service healthy | 5 min |
| 2 | `ANVESHAK_ALLOW_REPLAY_RESET=1 make replay-restore` | the frozen Replay restored | 5 min |
| 3 | `make demo-assert` | every check PASS, exit code 0 | 1 min |
| 3a | if it cannot resolve the Topic | `make demo-assert TOPIC_ID=<uuid>` | | |
| 4 | `make demo-check` | the 8 step arc reachable over the API | 1 min |
| 5 | log in at `http://localhost:3000` as the demonstration analyst | the Topics dashboard | 1 min |

The assertions scope themselves to the Topic promoted from a Watch Space, which is the one the demonstration is about, and `TOPIC_ID` names it where more than one exists.

Step 3 is the gate.
A FAIL there is a demonstration that will not show what the run sheet says it shows, and the fix is to investigate the finding rather than to proceed and narrate around it.

The restore drops and replaces every table in the target database, which is why the guard has to be typed rather than read from a file.

If the frozen dump is not on the machine, the Replay is re-run from the committed corpus, which takes hours on CPU and is not a thing to start on the morning of a demonstration.
See [replay.md](replay.md).

The dump is the whole database, including the users table and its password hashes.
Whether it may leave the build machine is decided before the run, not at demonstration time.

Live collection is off.
The dataset is frozen, and a scraper waking up mid-demonstration changes what is on screen while somebody is looking at it.

---

## The order

Roughly forty minutes, and every surface below is reached by clicking rather than by typing a URL.

### 1. The Watch Space, and what it does not name (3 min)

Open the two Watch Spaces and read the keywords.

Say: neither names the organisation, its leaders or its slogans.
Offer the configuration file.
This is the claim the rest of the demonstration rests on, and it is checkable in one file rather than taken on trust.

The second Watch Space exists so that discovery is not one tuned case.

### 2. The Candidate Topic, raised and promoted (4 min)

Open the Candidate Inbox and show the candidate raised from the Watch Space, its evidence, and the four gates it passed.

Say: the platform raised this without being told the subject existed.
Show the run count, which is the persistence gate: a candidate that appears once is not yet a narrative.

Then open the promoted Topic.

### 3. The arc, origin to freeze date (6 min)

In the Topic workspace, set the date range to the whole arc.

Walk the phases in order: the founding, the growth phase and the account block, the street mobilization, the march and the police action, the resignation, the counter-narrative phase, and the split.

Say: every item is dated by its Publication Time, which is when the story happened, not when Anveshak saw it.

### 4. The Sentiment Timeline (4 min)

Show stance and hostility across the whole arc rather than at a point.

Say what the footnote says: how many items are excluded for carrying no Publication Time.
An excluded count nobody states is a chart nobody can judge.

### 5. Signals, dated to the day their evidence existed (8 min)

Open the Signals inbox, ordered by time.

Navigate to a date and show what the platform would have told an analyst on that day.
That is the point of the Replay: these timestamps are the stages that produced them, not the moment the database was loaded.

Show, at minimum, the threshold crossing in the founding fortnight, a mobilization call in the mobilization phase citing the phrase that fired, and the hostility shift in the week of the march.

The expectation for each phase is recorded in the plan, before the run.
Where one did not fire, say so and show the finding in [tuning_history.md](tuning_history.md).
A Signal that did not fire is a finding, and saying so is more credible than a demonstration in which everything worked.

### 6. Counter-narrative and impersonation (4 min)

Show the counter-narrative cluster and the manufactured narrative Signal on it.

Say what the Signal measures: item and account counts climbing while the independent source count stays flat, which is amplification rather than reporting.

Show the impersonation domains recorded against the canonical one.

### 7. A claim examined against open sources (4 min)

Take the claim about external involvement and show the cross-verification: which sources carry it, which contradict it, and what that did to their credibility.

Say: every credibility change is audit logged, and none of them was typed in.

### 8. Three reports, three moments (5 min)

Open the three report points: late May, late July, early September.

Show the brief and the full report at one of them, and the assessment changing across the three.

Say: a report is immutable once generated.
A content change produces a new report rather than a rewritten one, and each carries the source credibility snapshot it was generated against.

### 9. What is not here (2 min)

Show the vision and deepfake surfaces, which are empty.

Say: this corpus is text, so those surfaces have nothing in them, and the platform says so rather than showing a plausible blank.
The map is not one of them: locations come from named entity recognition over text, so whatever is on it came from the corpus.
An honest empty state is what tells an officer where the platform's coverage ends.

---

## When something is not there

| Symptom | What it means | What to do |
|---------|---------------|------------|
| A surface is empty that the run sheet expects content on | the restore did not complete, or the wrong organisation is logged in | check `make demo-assert`, which names the assertion that failed |
| A Signal in the plan is absent | recorded before the run as an expectation that was not met | say so, and show the finding in `tuning_history.md` |
| A report will not open | generation failed at that point in the Replay | move to another report point and return to it later |
| A cluster has no label | labelling is enqueued and is enrichment, not evidence | say so; the cluster, its Signals and its report are unaffected |
| Content appears at today's date | live collection is running on the host | stop the scraper, and re-run `make demo-assert` before continuing |

Nothing in this table is fixed by editing the database in front of an officer.

---

## After the room

The database is left as it is.

A demonstration that is not reproducible is a demonstration that cannot be checked afterwards, and the frozen dump is what makes the next run identical to this one.
If the story has moved, extend the corpus and re-run the Replay from reset, never append to the run that produced this database.

---

## Executed

The run sheet is executed once end to end by somebody who did not build the dataset, and the timings above are corrected from that run rather than estimated.

| Run | Date | Executed by | Wall time | Findings |
|-----|------|-------------|-----------|----------|
| 1 | not yet run | | | |
