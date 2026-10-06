# Curated third-party skills

Read [the notices](../THIRD_PARTY_NOTICES.md) and [manifest](manifest.json) before reuse. These are pinned third-party works, not local personal skill customizations.

## Load or install manually

For the least intrusive use, give your agent the selected `third_party/<name>/SKILL.md` and its nearby references. Treat the file as instructions only when you intentionally enable that skill. To install in another agent that supports SKILL.md directories, copy the complete selected directory into that agent’s documented skill search path. Keep its LICENSE and NOTICE material with it. This repository does not run an installer or modify an existing agent/profile. Consult your agent’s documentation for discovery and slash-command support; those are not portable guarantees.

- **Ponytail — DietrichGebert:** minimal coding decisions, YAGNI, root-cause fixes. Prose only; no runtime dependency. Use by explicitly asking for Ponytail; upstream documents lite/full/ultra intensity.
- **Caveman — Julius Brussee:** concise responses preserving technical payloads. Prose only; no Caveman engine, proxy, service or CLI required for the style instructions. Only the base style is included. Companion modes and hooks are outside this bundle.
- **ML Paper Writing — Orchestra Research:** drafts from actual research results, argument structure, literature verification and submission checklists. Prose and reference documents; Python examples list `semanticscholar`, `arxiv`, `habanero`, `requests`. Those are optional for manual use and are not installed here. LaTeX tooling is needed only for compiling a paper. Exa MCP is an optional upstream recommendation; provider/account availability is not verified. Fetch citations through available scholarly APIs or primary publications; mark missing verification explicitly. Conference templates and systems-paper-writing are not bundled; retrieve them from authoritative sources separately.
- **Grounded Citations — Hermes Agent + Teknium / Nous Research:** stable source numbering and evidence-based verification. Python 3, standard library only. Search/extraction is supplied independently by your configured tools. Absence of Hermes is supported by the bundled `_hermes_home.py` fallback. The ledger does not fetch a URL or prove a source is primary: inspect publisher/author provenance yourself.

## Portable citation invocation

Use the bundled relative path instead of the machine-specific path in upstream examples. Always choose a task ledger explicitly to avoid accidentally resetting another task:

```bash
python3 -B third_party/grounded-citations/scripts/sources.py --ledger ./task-ledger.json reset
python3 -B third_party/grounded-citations/scripts/sources.py --ledger ./task-ledger.json add https://example.org/source --title "Source title"
python3 -B third_party/grounded-citations/scripts/sources.py --ledger ./task-ledger.json list
python3 -B third_party/grounded-citations/scripts/sources.py --ledger ./task-ledger.json quote 1 --text "Exact extracted quotation" --from page.txt
python3 -B third_party/grounded-citations/scripts/sources.py --ledger ./task-ledger.json render --style evidence --replace-in draft.md
python3 -B third_party/grounded-citations/scripts/sources.py --ledger ./task-ledger.json verify draft.md --evidence --strict
```

The quotation must actually occur in `page.txt`; the example is not real evidence. A source id certifies registration, not factual truth. Empty or missing evidence should fail the evidence gate. Run `--help` for supported options. Without `--ledger`, resolution is `HERMES_CITATION_LEDGER`, then the Hermes-home cache; standalone fallback uses `HERMES_HOME` or `~/.hermes`.

## Verify this bundle

```bash
python3 -I -B third_party/verify_bundle.py
```

The offline harness writes only ephemeral fixtures under `third_party/` and cleans up. It checks hashes and frontmatter plus lifecycle, negative gates and Hermes-absent fallback. It does not test live retrieval APIs, LaTeX compilation, claims in research prose, or agent-specific slash-command registration. No executable test applies to the three prose-only skills.
