# Why your agent forgets everything, and what to do about it

Every session starts the same way. You explain that the project uses pnpm and
not npm, that the Supabase client has a browser version and a server version and
mixing them leaks a key, that the deploy script needs the release commit written
to a file first. The agent does good work. The session ends.

Next week you explain it again.

This is the single largest hidden cost of working with AI agents, and it is
almost never discussed, because each individual re-explanation feels too small
to complain about. Two minutes. Then two minutes. Then two minutes, forever.

## Why it happens

An agent's context window is short-term memory, and that is not a metaphor. It
is the only memory the model has. Everything it learned during a session, every
correction you made, every piece of project knowledge it worked out, exists as
text in that window and ceases to exist when the window closes.

The model itself learned nothing. Weights did not change. The next session
starts from the same blank state as the last one, with the same confident
willingness to run `npm install` in a pnpm workspace.

## The naive fix, and where it breaks

The obvious answer is a project instructions file: a markdown document the agent
reads at the start of every session, containing the things you keep repeating.
This is genuinely useful and you should have one.

It breaks at scale, in two ways.

**It is loaded whole, every time.** A thousand facts about six projects means
every session pays the token cost of all six projects to work on one. You end up
pruning it to keep it cheap, which means deleting things you will need later.

**Retrieval is by reading, not by relevance.** The fact you need is the one that
matches the problem in front of you, and a flat file has no way to surface it.
The agent has to notice, on its own, that line 340 of your instructions file is
the one that applies to the error it just hit. Often it does not notice.

What you want is not a bigger file. It is a store you can query with the problem
you currently have, and get back the three facts that bear on it.

## The mechanism

Facts go in as text. Queries come in as natural language. Ranking is semantic,
so a query and a stored fact can match without sharing a single word.

```bash
python cortex.py add "Scheduled jobs written as .sh fail silently on Windows: \
the scheduler spawns with a narrow PATH and cannot find bash" --category gotcha

python cortex.py search "my cron job does nothing and reports no error" -n 5
```

That query returns that fact, scored 0.616 against 0.294 for the next candidate,
with zero words in common between query and fact. "Cron" and "scheduled jobs",
"does nothing" and "fail silently" are the same idea in different vocabulary,
which is precisely the case a keyword search cannot handle and the case that
matters, because when you hit a problem you describe it in the words of the
symptom, not in the words you used when you wrote the note.

Three design decisions matter more than the rest.

### Memory travels as text, never as a binary

The source of truth is a `facts.jsonl` file. The SQLite database and the vectors
are derived, and regenerated from that file on demand.

This is what makes syncing between machines safe. Putting a live SQLite database
in git corrupts it: the write-ahead-log sidecars are separate files, they are
not in the commit, and a merge produces a database whose state does not match
its log. A jsonl file with `merge=union` in `.gitattributes` merges cleanly, and
a `UNIQUE(content)` constraint absorbs the duplicates that union merging
produces.

Verified: delete the database, rebuild from the jsonl, and the file is
byte-identical while search scores are unchanged.

### Embeddings lead, keyword search is a tiebreak

I measured this over a 40-query set, and the result changed the design:

| Ranking | Exact token | Paraphrase | recall@5 |
|---|---|---|---|
| Keyword only (SQLite FTS5, bm25) | 100% | 0% | 57% |
| Embeddings only | 100% | 43% | **100%** |
| Naive rank fusion of both | 100% | 14% | worse than either |

The third row is the one worth sitting with. Combining two signals made the
system worse than either signal alone. The reason is that FTS5 is not merely
weak on paraphrase, it is *confidently wrong*: it returns a high-ranked
irrelevant result, and a rank-based fusion has no way to discount that
confidence, so the wrong answer is promoted by the merge.

Keyword search now enters only above a 0.85 score floor, as a tiebreak for exact
identifiers like `createServiceRoleClient`, at weight 0.15. That is the only
thing it is reliably good at.

### Facts are superseded, never edited

When a stored fact turns out to be wrong, the temptation is to edit it. Do not.
An edited fact cannot be audited, you lose the record that you once believed
something else, and if the store syncs between machines the old version returns
through the next merge. `supersede` keeps the old row, marks it superseded, and
points it at the replacement.

## A failure worth reporting

The store records which machine each fact came from, and my first version used
that as a ranking multiplier: facts from the current machine scored 0.55 higher.

It was wrong, and badly. For one test query the correct fact fell 54 positions.

The cause was conceptual, not numerical. The device field records *where a path
exists*, not where the knowledge matters. "The scheduler cannot find bash on
Windows" is true on every Windows machine, not just the one where I learned it.
Only absolute paths are genuinely machine-specific. Device is now a weak
tiebreak worth −0.02, and never a filter.

## What this does not solve

**It does not decide what is worth remembering.** That is still a judgement
call, and a store full of trivia is worse than no store, because it dilutes
every query. The test I use: would re-learning this cost me more than a minute?

**It does not make old facts true.** A fact stored in March about an API that
changed in June is retrieved with full confidence. Some staleness handling is on
me and some is unsolved.

**It is not a replacement for an instructions file.** Standing conventions that
apply to every session still belong somewhere loaded by default. The store is
for the long tail: the specific, the hard-won, the thing you would otherwise
re-derive.

---

The anchor is [`cortex.py`](../cortex.py) in this repo: one file, Python
standard library plus SQLite, embeddings optional. Without `fastembed` installed
it degrades to keyword search and tells you which mode it is in, rather than
crashing on a missing import.
