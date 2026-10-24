# bar: the verified bar check

Tools that check a library repo against the [verified bar](../playbook/verified-bar.md).

- `check.py`: the checker. Python 3.11 or later, standard library only.
- `template/`: a small library laid out the way the bar expects. Copy it to start a new one.
- `tests/`: self-tests for the checker, run on the template.
- `../.github/workflows/verified-bar.yml`: the workflow a library repo calls to run the check in CI.

## Check a repo

From a clone of the library, with elan and bubblewrap installed:

```
lake build
python3 <mission>/bar/check.py . --run-tests
```

It prints one row per bar item, with PASS, FAIL, OPEN, or SKIP, and exits 1 if any item failed. `--no-lean` skips the proof check, and `--offline` skips asking GitHub to confirm the spec approval. A skipped item is never a pass.

## Start a library

1. Copy `template/` into a new repo named for the software it verifies.
2. Replace `Clamp.lean`, `Spec.lean`, `Proofs.lean`, `Main.lean`, `SPEC.md`, the tests, and the page. Update `comparator.json` and `bar.toml` to match.
3. Keep `[project] status = "in-progress"` until every item passes.
4. Have the default branch require the `verified bar` check.

## Record an approval

The reviewer does this, in a pull request the reviewer then approves on GitHub:

```
python3 <mission>/bar/check.py <repo> --spec-hash
```

It prints the hash of the spec files and the three page sections it covers. Add it to `bar.toml`:

```
[[spec.approval]]
reviewer = "their-github-handle"
date = "2026-11-02"
sha256 = "<the hash>"
record = "https://github.com/Proven-Commons/<repo>/pull/<n>"
```

## Run the self-tests

```
python3 -m unittest discover -s bar/tests -v
BAR_LEAN=1 python3 -m unittest discover -s bar/tests -k LeanTest -v
```

The second line builds the template and runs `lake comparator` on planted faults: a weakened statement, a `sorry`, and an `implemented_by` that the kernels cannot see but the source rule catches. Run `lake build` in `template/` first.
