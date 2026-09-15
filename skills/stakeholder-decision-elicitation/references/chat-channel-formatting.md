# Chat channel formatting

Ask which channel **before** formatting. The same text degrades differently on
each one, and the failure is invisible from a desktop chat window.

## The universal mistake: hard-wrapped lines

Manually wrapping paragraphs at ~95 chars looks tidy in a terminal or an editor
and looks **broken on a phone**, because the client reflows to a narrower column
and your breaks land mid-sentence with ragged short lines.

Rule: inside a paragraph, write **one unbroken line**. Use blank lines only
between paragraphs. Let the client wrap.

Exception: deliberately separate lines for `(a)/(b)/(c)` alternatives — those
must not run together as prose or nobody reads past the first one.

## WhatsApp

| | |
|---|---|
| Bold | `*single asterisk*` — **not** `**double**`, which renders literally |
| Italic | `_underscore_` |
| Strike | `~tilde~` |
| Mono | `` ```block``` `` |
| Headings | none — use a bold line as a pseudo-heading |
| Tables | none — do not send markdown tables, they arrive as pipe soup |
| Links | auto-linked; no `[text](url)` syntax |

Long messages get collapsed behind a "Read more" fold, and a wall of text on a
phone gets skimmed or postponed. Split into parts of roughly 10–20 short
paragraphs.

**Announce the split in the first message** ("vou mandar em 4 partes pra não
virar um textão só") and send the parts back-to-back without waiting. Otherwise
the recipient replies to part 1 before they have seen the questions in part 3.

Sensible split for a decision-elicitation message:
1. context and the concept
2. the blocking questions
3. the bulk questions
4. remaining questions and sign-off

Voice notes are a common reply format — expect `.ogg` files and transcribe them
locally (`audio-transcription` skill).

## Telegram

Supports the same `*bold*` / `_italic_` in its legacy Markdown mode, plus real
`[text](url)` links and `` `code` ``. Much higher message length limit (~4096
chars), so fewer splits are needed. Still no tables.

## Slack

`*bold*`, `_italic_`, `~strike~`, `` `code` ``, ```` ``` ```` blocks, and `>`
blockquotes. Bulleted lists work. No tables, no headings in plain messages.
Threads exist — put a long body in a thread reply under a short summary rather
than splitting into sequential top-level messages.

## Email

Full markdown-ish structure is fine: headings, tables, long paragraphs, nested
lists. This is the only channel where the "Parte 1 / Parte 2" scaffolding is
appropriate, and even there a numbered question list beats prose.

## Quick checklist before sending

- [ ] Channel confirmed with the user.
- [ ] No hard wraps inside paragraphs.
- [ ] Bold syntax matches the channel (`*one*` for WhatsApp/Slack).
- [ ] No markdown tables outside email.
- [ ] Options `(a)/(b)/(c)` each on their own line.
- [ ] Split announced up front if multi-part.
- [ ] Numbering runs flat across all parts, so replies can cite numbers.
