# Third-party skill notices

These locally prepared copies are third-party works, not authored by Rafael. Publication remains subject to the repository owner’s review. Upstream files are byte-for-byte copies of the revisions below; repository-level documentation and the verification harness are separate additions. The repository’s own license does not replace these licenses.

| Bundle | Original author / maintainer | Upstream repository | Pinned commit | License |
|---|---|---|---|---|
| `ponytail` | DietrichGebert | https://github.com/DietrichGebert/ponytail | `552acd5efd0aeae2583a12efe39373d2f076f25e` | MIT |
| `caveman` | Julius Brussee (JuliusBrussee) | https://github.com/JuliusBrussee/caveman | `6571943370f7c9d4de1946481177ee7b306cd8e8` | Apache-2.0 |
| `ml-paper-writing` | Orchestra Research | https://github.com/orchestra-research/AI-Research-SKILLs | `773a52944ba4747a18bd4ae9ade53fff041adcbc` | MIT |
| `grounded-citations` | Hermes Agent + Teknium (Nous Research maintainer) | https://github.com/NousResearch/hermes-agent | `79af3f6cea8067284a7ea5725078578b3f790adb` | MIT |

## Permission and retained notices

- Ponytail: upstream MIT grant and Copyright (c) 2026 DietrichGebert retained in `third_party/ponytail/LICENSE`.
- Caveman: pinned `LICENSING.md` explicitly places the skill and all repository code under Apache-2.0 starting at 3.0.0. Root `LICENSE`, complete `NOTICE`, historical `LICENSE-MIT`, and `LICENSING.md` are retained under `third_party/caveman/`. Local Hermes metadata claiming MIT is not the authority for this revision. The historical MIT notice is retained because upstream requires it for earlier contributions. The full NOTICE references runtime/font dependencies not bundled here; no runtime, proxy, fonts, binaries, or engine were copied.
- ML Paper Writing: Orchestra Research’s upstream skill header is retained. Repository MIT permission and Copyright (c) 2025 Claude AI Research Skills Contributors are preserved in `third_party/ml-paper-writing/LICENSE`.
- Grounded Citations: upstream author header `Hermes Agent + Teknium` is unchanged; public maintainer is Nous Research. MIT permission and Copyright (c) 2025 Nous Research are retained in `third_party/grounded-citations/LICENSE`. It supports evidence attached to primary sources; it does not itself establish that a URL is authoritative.

Each upstream file’s exact raw URL, original path and SHA256 is in `third_party/manifest.json`. LICENSE and NOTICE files are hashed too. No author fields were rewritten. No license is inferred from a local header alone.

## Curated subset and unresolved integration limits

- Ponytail is the main skill only; audit/debt/gain/review companions are not bundled.
- Caveman is the prose skill and its local upstream README only. `/caveman ultra`, `/caveman wenyan`, hook mode/status integration and companion skills are not installed. Do not imply they work from this bundle alone.
- ML Paper Writing includes the original SKILL and five research reference documents. Templates are intentionally not copied: conference-owned template files carry separate notices/permissions and need their own review. Its unchanged `templates/` and `templates/README.md` links therefore do not resolve locally; use the pinned upstream directory or the conference’s current official style files. Its `../systems-paper-writing/` links are upstream companion recommendations, not a bundled skill. This is guidance for drafting and citations, not a complete camera-ready template distribution.
- Grounded Citations includes both reference documents and its two stdlib Python scripts, with no retrieval provider bundled. Optional Reddit, RSS, video, X and Hermes skill-install commands in upstream prose are upstream integration suggestions, not verified capabilities of this repository.
- Upstream documents contain numerical effectiveness/error-rate statements. They are preserved as upstream text, not independently reproduced or endorsed benchmark claims.

## Scope and checks

All vendored files are obtained from public raw GitHub URLs at the pinned commits. Only the four skill subsets and their governing notices were copied. Live skill directories were inspected read-only and were not used as redistribution sources. No global installation, profile modification, staging, commit, or push is performed.

Run `python3 -I -B third_party/verify_bundle.py` from the repository root. It verifies every upstream SHA256 and the four name/description frontmatter structures, then exercises the grounded-citations lifecycle in an isolated temporary directory under `third_party/`, which is deleted afterward. Tested: reset, add, deduplicate, list, reject missing/false evidence, attach quote, render/replace idempotence, strict evidence verification, reject unknown ids, reset, Hermes-absent standalone fallback, and environment ledger override. Run completed with exit code 0. Prose-only bundles have no executable lifecycle; no executable test applies. Relative links were inspected; local research reference links exist, except the explicitly omitted templates/companion above. External reading links are retained, not a promise of continuous availability.
