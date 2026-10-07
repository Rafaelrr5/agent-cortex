---
name: first-run-onboarding
description: "Use on a non-technical user's first Hermes session. Safe defaults, then a short interview."
version: 1.1.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [onboarding, first-run, non-technical, memory, user-profile, safety]
    related_skills: [recall-and-claim-verification, measurement-validity]
---

# First-Run Onboarding

The person in front of you has just installed Hermes and is **not technical**. Often this
happens in a workshop, with someone presenting. In about ten minutes, leave the agent:

1. asking permission before anything risky;
2. carrying the two honesty skills from this repo;
3. knowing who the person is, what they do and how they want to be answered.

An agent that starts from zero makes a first impression of forgetting everything. The point
of this skill is that the **second** conversation already opens with the agent knowing them.

## Conversation rules (whole session)

- **First message: ask which language to use**, in one short line written in the likely
  languages side by side (e.g. "Português, English, Español?"). Skip the question only if the
  invocation already named a language. Use that language for everything after, including
  the saved facts.
- Short sentences, second person, warm. No jargon: if a technical word is unavoidable,
  explain in one sentence what it means **for them**.
- **One question at a time.** Wait for the answer.
- Before running any command, say in one sentence what it changes for the person
  ("this makes me ask before deleting or installing anything").
- **Never ask for or store** passwords, API keys, bot tokens, ID numbers, home address,
  phone number, health data or data about other people. If offered, thank them, say it is
  not needed, and do not save it.
- Never say something is done without having seen the command's real output. If a step
  fails, say what failed in plain words and continue with the next step.

## Step 1 - Agree on the plan

After the language answer, in at most four lines: two quick settings, two new skills, six questions about them, and at
the end the list of what was saved, for them to check. Ask if you can start.

## Step 2 - Safety and language

One at a time, explaining first:

```bash
hermes config set approvals.mode manual
hermes config set display.language <their language code, e.g. pt>
```

- The first makes the agent **stop and ask** before risky commands (deleting files,
  installing programs, changing the system).
- The second puts Hermes' fixed system messages, like the permission prompt, in their
  language. Skip it if they are fine with English.

Confirm with `hermes config get approvals.mode`: it must answer `manual`.

## Step 3 - Two honesty skills

```bash
hermes skills install Rafaelrr5/agent-cortex/skills/recall-and-claim-verification --yes
hermes skills install Rafaelrr5/agent-cortex/skills/measurement-validity --yes
```

Explain without jargon:

- **Check before claiming**: when they ask for something "you already did", or a program
  says "done", the agent checks for real. If it finds nothing, it says so instead of
  producing a plausible answer.
- **Check a number before deciding**: before a number drives a decision (price, grade,
  deadline), the agent checks where it came from.

Then run `hermes skills list` and, **only for skills actually in the list**, mention a few
that ship ready and help non-technical work: weekly review (`weekly-review-planning`),
tasks and deadlines from a document (`document-to-action-items`), action items from a meeting
(`meeting-action-items`), less robotic writing (`humanizer`). Describe them by effect.

If an install fails:

| What shows up | What to do |
|---|---|
| GitHub rate limit | Common on shared classroom wifi. Go on to step 4 and retry at the end |
| Blocked by the security scan | Do not force it. Tell them to ask the presenter |
| Already installed | Fine, move on |
| No internet | Go on to step 4; skills can be installed later |

## Step 4 - Interview

Six questions, **one at a time**, in this order. Accept "I'd rather not say" without
pushing. If an answer is vague, ask at most one follow-up.

1. What is your name, and what do you like to be called?
2. What do you do today? Study, work, both? In what?
3. Where in your routine do you lose the most time on repeated work?
4. Is there one boring, repetitive task you would like to hand off? (In a workshop, they may
   have written it down at the start: ask for it.)
5. How do you prefer my answers: short or explained? More formal or more relaxed?
6. Is there anything I must **never** do without asking you first?

## Step 5 - Save and confirm

Save with the memory tool, in the user profile (`target: user`), **one fact per entry**,
declarative, third person, in the user's language. Format examples:

- "Name is Ana Souza; prefers to be called Ana."
- "Second-year high-school student who wants to organize her studies."
- "Loses the most time putting together the weekly class summary."
- "Repetitive task to hand off: remembering school assignment deadlines."
- "Prefers short answers and informal language."
- "Never send a message or email on her behalf without confirming first."

Then show **everything saved** as a plain list and ask: "Is this right? Want to fix or remove
anything?". Apply corrections (replace or remove the entry) and show the final list.

## Step 6 - Close

- Explain: "From the next conversation on, I start out knowing this. To open a new
  conversation, type /new." Memory is loaded at the start of each conversation; in this one
  it is already in what we talked about.
- Suggest **one** concrete first task tied to answers 3 and 4, and ask if they want to try it
  now.
- End with three lines: what was configured, which skills were added, what you know about
  them.

## Verification (before saying you are done)

- [ ] `hermes config get approvals.mode` answered `manual`.
- [ ] `hermes skills list` shows both new skills, or you said which ones failed.
- [ ] Every interview fact was saved and the person saw the final list.
- [ ] No password, document number, address or phone number was saved.

## Pitfalls

- **Asking all six questions at once.** Non-technical users answer the first and skip the
  rest; the profile comes out with one fact.
- **Saving a paragraph instead of facts.** One entry per fact is what lets the person later
  say "remove the one about my job" and have it work.
- **Telling them the agent "now knows them" in this session's prompt.** The memory snapshot
  is taken at session start; the honest line is that it applies from the next `/new`.
- **Installing everything that looks useful.** Each extra skill is one more thing to explain.
  Two skills, named by effect, are remembered; ten are not.
