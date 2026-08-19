# Test Guide — Emergency ("I have a fever") Flow

This guide checks what happens when a patient reports a symptom over WhatsApp. Each
test is a short list of exact actions. Do them top to bottom. After each step there's
a "you'll know it worked when…" so you're never left guessing.

Every bug you catch here is one that never reaches a real patient — so if anything
looks off, note it and report it. A false alarm costs us nothing; a missed problem
costs a lot.

---

## Before you start (do this once)

**Where you're testing:** the **`care360` testing environment** — the WhatsApp webapp,
the AWS Console, and DBeaver.

**Get your patient id.** Open DBeaver and run this — replace `<YOUR_MOBILE>` with the
number your test WhatsApp account uses (digits only, e.g. `919812345678`):

```sql
SELECT id, name, mobile_number
FROM patients
WHERE mobile_number = '<YOUR_MOBILE>';
```

Write down the `id` that comes back. Everywhere below says `<YOUR_PATIENT_ID>`, paste
that number in.

**Two checkpoints in every test.** Each test checks two things:
1. **Was the message understood?** — you'll see this in the lambda's logs (CloudWatch).
2. **Did the system act on it?** — you'll see this as a row in the database (DBeaver).

A test passes only when **both** are true. If the log looks right but the database row
is missing, that's still a finding worth reporting — it tells us exactly where the
break is.

---

## Test 1 — "I have fever" (English) creates an emergency ticket

**Step 1.** Open the Care360 WhatsApp webapp and log in as your test patient. In the
chat, type exactly:

```
i have fever
```

and send it.

**Step 2.** Open AWS Console → CloudWatch → Logs → log group
**`/aws/lambda/care360-nlu-handler`**. Open the newest log stream (top of the list).
Look for a line that shows the intent was set to **`SYMPTOM_HIGH`** and severity
**`EMERGENCY`**.

✅ *If you see that line, the message was understood as an emergency.*

**Step 3.** Open DBeaver and run this — replace `<YOUR_PATIENT_ID>`:

```sql
SELECT status, escalation_level, escalation_level_code, assigned_to, severity
FROM escalations
WHERE patient_id = <YOUR_PATIENT_ID>
ORDER BY created_at DESC
LIMIT 1;
```

**Step 4.** Check the row that comes back has:
- `status` = **OPEN**
- `escalation_level` = **3**
- `escalation_level_code` = **L3_DOCTOR**
- `assigned_to` contains both **doctor** and **counsellor**
- `severity` = **RED**

✅ **You'll know it worked when** that one row exists with those exact values, created
just now. If no row comes back, or the values differ, note it down and report it.

---

## Test 2 — the same message in Hindi

This test only means something if the patient's language is set to Hindi first — the
system replies in whatever language the patient has saved, so we set that before sending
the message.

**Step 0 — set the patient's language to Hindi.** In the Care360 webapp, logged in as
your test patient, open the **Settings** page. You can reach it by tapping the
**Settings / profile** option in the app menu, or by adding `/settings` to the end of the
web address in the browser bar and pressing Enter.

On the Settings page, find the row with a **🌐 globe icon** labelled **Language** (it
shows your current language next to it). Tap that row. A dialog titled **Language** opens
with the heading **Select Language** and a list of choices. Tap **हिंदी** (Hindi). Wait a
moment for it to save — the Language row should now show **हिंदी**.

✅ *You'll know Step 0 worked when the Language row reads हिंदी.* To double-check it saved
to the patient's record, run this in DBeaver and confirm `preferred_language` is now a
Hindi value (for example `hi` or `HINDI`), not English:

```sql
SELECT id, preferred_language
FROM patients
WHERE id = <YOUR_PATIENT_ID>;
```

**Step 1.** Back in the WhatsApp chat, type exactly:

```
मुझे बुखार है
```

and send it.

**Step 2.** Same log group as Test 1 (**`/aws/lambda/care360-nlu-handler`**), newest
stream. Again look for intent **`SYMPTOM_HIGH`** and severity **`EMERGENCY`**.

✅ *The Hindi message should be treated exactly like the English one.*

**Step 3.** Run the **same query** as Test 1, Step 3.

**Step 4.** Confirm a **fresh** row exists with the same values as Test 1
(`status = OPEN`, `escalation_level = 3`, `escalation_level_code = L3_DOCTOR`,
`severity = RED`) and a `created_at` from just now.

✅ **You'll know it worked when** that new emergency row exists. As a bonus, the reply
you get back on WhatsApp should also be in Hindi.

---

## Test 3 — a **voice note** saying "fever" (please report either way)

This tests whether a fever said *out loud* escalates the same as a typed one.

**Step 1.** In the webapp chat, record and send a **voice note** where you clearly say,
in Hindi:

> mujhe bukhar hai

Send it as **audio** (the microphone), not as typed text.

**Step 2.** Open CloudWatch → log group **`/aws/lambda/care360-voice-note-handler`** →
newest stream. Confirm it shows your voice note was received and turned into text (you'll
see text close to what you said).

✅ *This confirms the voice note was heard and understood.*

**Step 3.** Now run this query (same table as Test 1, with the time it was created):

```sql
SELECT status, escalation_level_code, severity, created_at
FROM escalations
WHERE patient_id = <YOUR_PATIENT_ID>
ORDER BY created_at DESC
LIMIT 1;
```

**Step 4.** Check whether a **new** emergency row appeared — `severity = RED`,
`escalation_level_code = L3_DOCTOR`, with a `created_at` from just now — i.e. the **same
outcome** as typing "I have fever" in Test 1.

✅ **You'll know it worked when** a fresh emergency ticket exists, exactly like Test 1.

⚠️ **This one is important to report whichever way it goes.** If you got a caring reply on
WhatsApp but **no new ticket** appeared in the database, write that down clearly. A fever
reported by voice should escalate exactly like a typed one — if it doesn't, that's a real
gap and catching it here matters.

---

## Test 4 — a mild symptom should **not** raise an emergency

**Step 1.** In the webapp, type exactly:

```
thoda pain hai
```

and send it.

**Step 2.** Log group **`/aws/lambda/care360-nlu-handler`**, newest stream. Look at the
intent line — it should say **`SYMPTOM`** (plain), **not** `SYMPTOM_HIGH`.

✅ *This means the system understood it as a mild symptom, not an emergency.*

**Step 3.** Run this query and note the `created_at` of the newest row:

```sql
SELECT severity, escalation_level_code, created_at
FROM escalations
WHERE patient_id = <YOUR_PATIENT_ID>
ORDER BY created_at DESC
LIMIT 1;
```

**Step 4.** Confirm **no new emergency row was created for this message** — i.e. the
newest row is from an *earlier* test (check `created_at`), not from just now. A mild
"pain" message should get a supportive reply **without** opening a doctor-level ticket.

✅ **You'll know it worked when** no fresh `RED` / `L3_DOCTOR` row appears for this
message. If a new emergency ticket did open from "thoda pain hai", note it and report it.

---

## Quick variants (optional spot-check)

Each message below should behave **exactly like Test 1** — intent `SYMPTOM_HIGH` in the
logs, and a fresh `OPEN` / `L3_DOCTOR` / `RED` ticket in the `escalations` table. Send
one, then re-run the Test 1 query and confirm a new emergency row appears:

```
tez bukhar hai
saans nahi aa rahi
khoon aa raha hai
बुखार है
```

✅ **You'll know it worked when** each of these opens a fresh emergency ticket just like
Test 1. If any one of them does **not**, note which message it was — that's a finding.

---

*In short: type (or speak) the message → check the log line → run the query → match the
row. If the log and the row agree with what's written here, the test passed. If they
don't, you've found something worth telling us about.*
