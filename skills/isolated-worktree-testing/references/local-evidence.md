# Local evidence

Executed from this skill directory:

```sh
python3 -B -m unittest discover -s tests -v
```

Observed result: exit code 0, `4 tests`, `OK`.

Staged plus unstaged tracked changes reproduced; source HEAD/status preserved; existing target, untracked file and submodule refused before creation; fixture worktree removed without force.

Tests used only in-memory fixtures or disposable local Git repositories under the
caller-provided TMPDIR. Fixture commits are test setup, not commits in the public
copy repository. No credentials, remote, push or publication were used.

These results establish the tested helper behavior on the local Windows host, not
project acceptance, CI parity, security isolation, deployment or performance claims.
