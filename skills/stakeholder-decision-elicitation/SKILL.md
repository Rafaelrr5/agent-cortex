---
name: stakeholder-decision-elicitation
description: "Get decisions from a non-technical owner via chat message."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [Stakeholders, Product, Requirements, Ghostwriting, Communication]
    related_skills: []
---

# Stakeholder Decision Elicitation

Outbound counterpart to `meeting-action-items` (which turns notes *into* tickets).
This skill covers the other direction: you hold open design questions and need a
**non-technical decision-maker** — a PO, professor, client, coordinator — to
answer them so work can start.

## When to use

- "Prepare a message for <person> so they decide how X works."
- You wrote a design/concept doc and need it approved or corrected.
- A spec has open items and the owner of those items is not an engineer.
- Any time the answer changes what you build and you are guessing instead.

## The four rules

### 1. Split the questions by who owns them

Sort every open question into two piles before writing a word:

| Pile | Goes to | Examples |
|---|---|---|
| **Product** | the stakeholder | what it does, who uses it, cadence, scoring, what is out of scope |
| **Technical** | you and the user | stack, data sources, schema, auth, batch idempotency |

Technical questions **never** appear in the stakeholder message — not even in a
tidy appendix. Deliver them separately to the user in the same reply. A PO asked
to weigh in on Postgres RLS will either stall or rubber-stamp; both are worse
than you deciding.

### 2. Assume zero context and explain from scratch

Even when the stakeholder started the project, they have not read your docs and
do not hold your model of it. Open with the concept in plain language: one
paragraph on what it is, one concrete worked example that shows a real moment of
use, and what the end user walks away with. Only then ask.

Strip jargon at the source — not "the engine applies a multiplier to the demand
curve" but "the jogo aplica o efeito". If a term must appear (DRE, MEI), it must
be one the stakeholder already uses in their own domain.

### 3. Present your decisions as reversible guesses, never as settled

This is the rule that gets violated most.

You will usually arrive with a decisions doc where items are marked *closed*.
That status is **internal**. Externally, every one of those is a proposal the
stakeholder may overturn, and the message must say so explicitly:

> "pra não te entregar uma folha em branco, eu chutei uma resposta pra quase
> tudo. Mas é chute MEU. Se você discordar de qualquer uma é só falar que eu
> mudo — agora é de graça, nada foi construído ainda. Depois de pronto fica caro."

Two failure modes this avoids:

- A blank-slate questionnaire ("what should scoring be?") is work you offloaded
  onto someone with less context than you. Always propose.
- A settled-sounding recap ("scoring is final company value") reads as *fait
  accompli*; a polite stakeholder will not fight it and you will build the wrong
  thing with their signature on it.

Propose a default **and** name the tradeoff you took, so disagreeing is cheap.

Corollary: re-open items your own doc closed. If `decisoes.md` says grading was
cut, the message still asks about grading — the stakeholder never voted on it.

### 4. Ghostwrite in the user's voice

The user sends this from their own account. It must read as them typing, not as
an assistant drafting. Concretely:

- First person throughout; their register, informality, and language variant.
- Contractions, hedges, the occasional emoji if that matches them — plus their
  characteristic tics if visible in the transcript.
- No consultant scaffolding: no "Parte 1 — Contexto", no "conforme alinhado", no
  bolded label on every sentence, no executive summary.
- Sign off the way they would.

Check by reading it back: would the recipient notice anything unusual about how
this person writes today? If yes, rewrite.

## Question design

- **Number every question** and keep the numbering flat across the whole message
  so the reply can be "1 – terça, 4 – (b), 7 – todos no mesmo".
- **Say which ones block.** "As 4 primeiras travam tudo, as outras 12 eu consigo
  tocar em paralelo" lets a busy person answer partially and still unblock you.
- **Give options as labelled alternatives** `(a)/(b)/(c)` with the cost of each
  stated honestly, including the cost to *you*. Do not hide that (b) is more
  work for you; a stakeholder who learns that later feels manipulated.
- **Close with a catch-all**: "tem alguma coisa que você imaginava e que eu não
  falei em nenhum momento?" This is the highest-yield question in the set — it
  is where a pivot surfaces before you build.
- Ask about risk you deliberately accepted, in their terms: not "no scheduler,
  manual close only" but "se ninguém fechar a rodada naquela semana, a turma
  fica parada esperando".

## Match the channel

Ask which channel before formatting; the same text fails differently on each.
See `references/chat-channel-formatting.md` for WhatsApp, Telegram, Slack, and
email specifics. The one that bites hardest: **hard-wrapped lines look broken on
a phone** — write each paragraph as a single unwrapped line and let the client
reflow.

For a long message, split into parts, announce the split up front ("vou mandar
em 4 partes pra não virar um textão"), and send them back-to-back. Without the
announcement the recipient replies to part 1 before seeing the questions.

## Reading the reply — the part everyone skips

Answers arrive unstructured, often as voice notes (see `audio-transcription`).
Before mapping replies onto your numbered questions, check whether they map at
all.

**A stakeholder who answers none of your questions has not failed to reply —
they have told you the questions were wrong.** Treat an off-form response as the
highest-value signal in the exchange, not as noise to be re-asked.

When the reply diverges, produce a comparison table (`what I designed` vs `what
they asked for`) across: who uses it, what it is, who builds it, your role, and
where the value sits. Divergence on **who builds it** or **your role** is a
different project, not a revision.

Then hunt for the motive that was mentioned once and in passing. Stakeholders
bury the actual driver inside logistics: *"a gente tem que conseguir pessoas que
queiram e não está tão simples"* revealed that the whole request was a
**substitute for a missing input**, which means it is a means and evaporates if
that input arrives. Naming that changes what is worth building.

Also extract from the reply, explicitly:
- **New constraints** they mentioned casually (schedules, venues, other people).
- **Cost delta** versus what you had scoped — recurring teaching is not a
  weekend of coding, and say so plainly.
- **Anything of yours that went unmentioned.** It is neither approved nor
  rejected; surface it as orphaned and ask directly rather than assuming.
- **Risk they cannot evaluate** (legal, tax, institutional exposure). Raise it
  as a question — "quem valida o conteúdo antes de publicar?" — not as an
  objection to their idea.

## When the answers land — re-scoping

A reply that answers your questions **properly** is not the easy case. Updating
the docs is mechanical; the real work is spotting the structural consequence the
stakeholder could not see, because they reasoned in their domain and the damage
lands in yours.

Worked example: *"as decisões devem mudar ao longo da jornada"* reads as a scope
tweak. It actually threatens the single-engine architecture — a round about
*validating a hypothesis with customers* and a round about *setting price and
production* are not the same mathematics, so eight rounds risked becoming eight
mini-games with nothing shared and no second module.

So, on every answered item, ask: **does this multiply the number of engines,
rulesets, or screens?** If yes, find a staging boundary before agreeing (see
`references/scoping-under-po-answers.md` for the patterns that resolve it).

Also re-derive consequences the answer created but did not mention. "Teams" plus
"some competition" quietly converted round closing from per-entity to a
**whole-cohort simultaneous calculation** — one team that fails to submit now
blocks everyone. That was not in their reply, it is not something they can be
expected to foresee, and it invalidates a feature spec. Surface it as the most
urgent open question, not as a footnote.

When you push back on the process itself, push back on **sequencing, not
substance**: agree with the principle, name the one property their sequence
cannot validate, and propose running that piece in parallel rather than deleting
a step. "Game balance cannot be validated in a document" wins where "your plan
is too slow" does not.

## Co-authored specs: mark authorship, then strip it

When a document is written jointly with the stakeholder, tag every section by
who owns it — decided-by-them, proposed-by-you, open, and critically
**draft-standing-in-for-their-territory**.

That last tag is the one that matters. Where you wrote a first pass on ground
that is theirs — learning objectives, assessment weights — say so in the
document, or a polite stakeholder **approves it by omission** and the project
proceeds on objectives that are not actually theirs.

Two more rules that keep such a document honest:

- **Label every number in a proposed model as a starting guess.** A doc that
  prints `ε = 1,8` without that caveat turns it into law by accident.
- **Leave blocked sections visibly empty.** A questionnaire plus a reasoned
  recommendation beats a section filled with plausible invention.

**On export, convert the marks to prose — do not delete them.** Rafael asked for
"um PDF com tudo, sem essa marcação de [CRIS] etc.": the information must
survive, the notation must not. `[RASCUNHO-CRIS]` becomes a sentence at the head
of the section ("esta seção pertence à concepção pedagógica; o que segue é um
ponto de partida feito para ser reescrito"), `[EM ABERTO]` becomes "em aberto:
…" inline plus a consolidated pendency table, `[RAFAEL]` becomes "recomendação
técnica: …", and the stakeholder's own tag disappears entirely — in a document
signed by both, marking their half is noise.

External export also means: drop first names for roles ("a professora", "a
concepção pedagógica"), and drop insider jargon — *sandbox* → "calibração por
simulação", *share* → "participação de mercado". Then grep the extracted text to
prove no marks survived; do not eyeball it.

## Don't answer for them

When the reply forces choices that are genuinely the user's (accept the new
scope? defend the old design? which slot fits their calendar?), stop and ask the
user. Do not draft a reply that silently commits them to teaching a course.

## Verification

- [ ] Zero technical questions in the stakeholder message; they went to the user.
- [ ] Concept explained from scratch, with a concrete worked example.
- [ ] Every proposed decision framed as a reversible guess, with its tradeoff.
- [ ] Items your own doc marked "closed" are re-opened for their vote.
- [ ] Questions numbered flat; blocking ones flagged.
- [ ] A catch-all "what did I miss" question is present.
- [ ] Formatted for the actual channel; no hard-wrapped paragraphs.
- [ ] Reads as the user wrote it.

## References

- `references/chat-channel-formatting.md` — per-channel formatting and splitting.
- `references/scoping-under-po-answers.md` — design patterns for absorbing a PO's
  answers without multiplying engines: staging boundaries, variance-not-mean
  incentives, derived consequences, and calibrating in parallel.
