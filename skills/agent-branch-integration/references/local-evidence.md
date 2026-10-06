# Local evidence

Executed from this skill directory:

```sh
python3 -B -m unittest discover -s tests -v
```

Observed result: exit code 0, `3 tests`, `OK`.

Descendant candidate reported without checkout mutation; divergent and unknown revisions refused.

Tests used only in-memory fixtures or disposable local Git repositories under the
caller-provided TMPDIR. Fixture commits are test setup, not commits in the public
copy repository. No credentials, remote, push or publication were used.

These results establish the tested helper behavior on the local Windows host, not
project acceptance, CI parity, security isolation, deployment or performance claims.
