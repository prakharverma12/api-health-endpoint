---
name: test-guide
description: Write or reformat a manual QA test guide in Care360's "type/do a thing → check the log → run a query → match the row" style — a step-by-step document a non-technical tester can execute with zero ambiguity. Use when asked to write test cases, a test document, a test guide, or QA steps for a feature/ticket, or to turn a developer's rough test notes/checklist into this format.
---

# Test guide writer

Produces manual test documents in one consistent house style, whether starting from a
ticket/feature description or from a developer's existing rough notes. A full worked
example lives at `references/example-emergency-ticket.md` — read it if you want to see
every rule below in context before writing.

## Who you're writing for (read this first)

Every guide is written for one specific person: our tester. A full profile lives at
`F:\Internship\codebase\aws-lambda\plans\about-the-tester.md` — read it before writing if
you haven't. The short version, which shapes every rule below:

- He is **smart and careful, but new to the system, and not a developer.** He doesn't read
  code, doesn't know the table schemas, and shouldn't have to. If a step needs explaining,
  explain it plainly — don't assume prior knowledge.
- **He trusts exactly what he sees.** That's his value: he catches things we've stopped
  noticing. So every step must tell him precisely what to look at and what a pass looks like.
- **Write with respect and encouragement.** Never talk down. Do **not** use "just",
  "obviously", "simply", or "this is easy" — they make a confusing step feel like his fault
  when it's really our instructions falling short. A confused tester is a documentation bug,
  not a tester error.
- **Hand him everything, so he never has to guess or invent:** copy-paste SQL, copy-paste
  test-event JSON, the exact URL to open, exact button/menu labels, exact function/log-group
  names. The only thing he fills in is his own test id, and you always tell him where to get it.
- **Make "done right" unmistakable** with a clear finish line on every test.
- **Assume good faith and say findings are welcome.** A false alarm from him is far cheaper
  than a real bug slipping through — say so, so he reports freely.

His toolkit (lean on these; don't send him anywhere he can't reach): the **Care360 WhatsApp
webapp** (act as a patient) and the **web portal** (open exact URLs you give him); the **AWS
Console** — run a lambda on its **Test** tab, fake any date/time via the `injected_now` test-event
field, read **CloudWatch** logs, read **DynamoDB**; and **RDS via DBeaver** for result-checking
queries you write out in full.

## Step 1 — figure out the mode

- **From scratch**: the user describes a feature, flow, or ticket and wants test cases
  invented for it.
- **Reformat**: the user already has draft steps, a checklist, or notes and wants them
  restructured into this style — don't invent new test cases they didn't ask for, don't
  drop cases they did write, just impose the structure and fill in the checkpoints.

If it's unclear from the request which mode applies, ask.

## Step 2 — gather what you need before writing (don't guess)

Never invent environment names, log group names, table/column names, or expected values
— a wrong technical detail makes the whole document untrustworthy. If any of the
following aren't already given, ask the user (a developer) for them:

- **Environment(s) and tools** the tester will use (e.g. a specific webapp/testing
  environment, AWS Console, DBeaver, an admin panel).
- **How the tester identifies their own test data** — usually a one-time lookup query
  (e.g. find your own patient/user id by phone number/email) that gets reused via a
  placeholder for the rest of the doc.
- **Where "the message/action was understood" shows up** — log group name(s), what
  field/line to look for, and what value it should show.
- **Where "the system acted on it" shows up** — table name(s), the exact query, and the
  exact expected field values (not "check it looks right" — literal values).
- **The exact literal inputs to test** — messages, taps, form values — precise enough to
  put in a code block with zero interpretation left to the tester.
- **What should NOT happen** for at least one negative-path case, if the feature has one
  (most do) — see Step 4.
- **Any known-flaky or uncertain areas** the developer wants flagged as "report either
  way" regardless of pass/fail.

If the user gave you a ticket description with gaps in any of these, ask targeted
questions rather than filling gaps with assumptions.

## Step 3 — document skeleton

```
# Test Guide — <Flow name> Flow

<1 short paragraph: what this checks, in plain language, and that each test is a
list of exact actions to do top to bottom.>

<1 short paragraph motivating care: why catching bugs here matters, and that a false
alarm costs nothing but a missed one costs a lot.>

---

## Before you start (do this once)

**Where you're testing:** name the exact environment(s)/tools.

**Get your <test data id>.** Give the exact one-time lookup query, using a
`<PLACEHOLDER>` for whatever varies per tester (e.g. their own phone number), and
say explicitly that the result gets substituted everywhere below via another
placeholder, e.g. `<YOUR_PATIENT_ID>`.

**<N> checkpoints in every test.** State the verification philosophy ONCE, e.g.:
1. Was the input understood? — where that shows up (logs).
2. Did the system act on it? — where that shows up (DB row / UI state / etc).

Say a test only passes when ALL checkpoints are true, and that a partial match
(log right, DB wrong, or vice versa) is still a finding worth reporting.

---

## Test 1 — <specific behavior under test>

**Step 1.** Exact action, in a fenced code block if it's literal text/input.

**Step 2.** Exactly where to look to confirm it was understood (named log
group/source), and the exact value/line to find.

✅ *Soft checkmark — one italic sentence confirming what that step means.*

**Step 3.** Exact query/check to confirm the system acted, with placeholders.

**Step 4.** Exact expected values as a bullet list of `field` = **value**, not prose.

✅ **You'll know it worked when** <the single, unambiguous pass condition,
spelled out>. If it differs, note it down and report it.

---

## Test 2, 3, ... — one per behavior

Repeat the Test 1 skeleton. If a test needs its own precondition setup first, give
it as **Step 0** with the same exactness (menu labels, icon descriptions, dialog
titles) as any other step — don't assume the tester already knows the UI.

Include at least one **negative-path test**: a case where the expected outcome is
that nothing (extra) happens. Tell the tester explicitly what "no new record"
looks like to check (e.g. compare `created_at` against the last known test row)
instead of just saying "make sure it doesn't trigger."

Mark any test the developer flagged as uncertain/important-either-way with
⚠️ and say explicitly to report the result regardless of pass or fail, and why
it matters if it fails.

---

## Quick variants (optional, only if there are near-duplicate cases)

List extra literal inputs that should each produce the exact same outcome as an
earlier test, without re-deriving the whole step sequence — just point back at
which test's pass criteria applies.

---

*Closing one-liner recapping the whole method, e.g.: do the thing → check the log
→ run the query → match the row.*
```

## Step 4 — house rules (apply throughout)

- **Respectful, encouraging, second person.** Never talk down; never use "just", "obviously",
  "simply", or "this is easy". If a step is confusing, that's the doc's fault, not the tester's —
  add detail without apologising for it. Open or close the guide by making clear his testing
  matters (every bug caught is one that never reaches a real patient) and that reporting a false
  alarm is always welcome.
- **Start with how to get there.** The first action of the flow names the exact environment and,
  for web tests, gives the **exact URL to open** in a code block — he shouldn't have to find the
  page himself.
- **Every literal input, query, or exact value goes in a fenced code block or bold/code
  span** — never "type something like fever," always the exact string.
- **Every test ends with an unambiguous pass condition**, phrased as
  `✅ **You'll know it worked when** …`. Softer intermediate confirmations use
  `✅ *italic*` instead of the bold "You'll know it worked when" phrasing — reserve that
  exact bold phrase for the final, whole-test verdict.
- **Placeholders** (`<LIKE_THIS>`) are introduced once with an explicit "replace X with
  Y" instruction, then reused silently everywhere after.
- **Second person, plain language, no unexplained jargon.** Assume the tester may not
  read code and won't go spelunking in the codebase to figure out what to send.
- **Always name the exact source of truth** — the specific log group, table, or screen —
  never "check the logs" or "check the database" unqualified.
- **Include at least one negative-path test** if the feature has any "and this should
  NOT happen" behavior — untested absence-of-behavior is a common gap.
- **Flag known-uncertain cases with ⚠️** and say to report the outcome either way, with
  the reason it matters.
- **Separate tests with `---`.**
- **If reformatting existing notes**, preserve every case the developer already wrote;
  only add the checkpoint/pass-condition structure, placeholders, and exact-value
  callouts — don't silently drop or merge their cases.
- **If the developer's draft already contains findings/results** (e.g. a note that a
  step failed), keep that as a `**Remarks**` line directly under the step it belongs to,
  rather than moving it to a separate summary — findings stay attached to the step that
  produced them.

## Step 5 — output

Write the result as a single markdown file. Confirm the target filename/location with
the user if it isn't obvious (e.g. `test-<flow-name>.md` next to their other test docs).
