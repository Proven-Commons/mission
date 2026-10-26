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

It prints one row per bar item, with PASS, FAIL, OPEN, or SKIP. It exits 1 if any item failed, or if `bar.toml` says `verified` and any item did not pass. `--no-lean` skips the proof check, and `--offline` skips asking GitHub to confirm the spec approval. A skipped item is never a pass.

## Start a library

1. Copy `template/` into a new repo named for the software it verifies.
2. Replace `Clamp.lean`, `Spec.lean`, `Proofs.lean`, `Main.lean`, `SPEC.md`, the tests, and the page. Update `lakefile.toml` (library and executable names, `defaultTargets`), the executable path in `tests/run_tests.py`, `comparator.json`, and `bar.toml` (including `[spec] code`) to match.
3. Keep `[project] status = "in-progress"` until every item passes.
4. In `.github/workflows/bar.yml`, pin the workflow and `bar-ref` to the same tag or commit of this repo.
5. Have the default branch require the `bar / bar` check, which the "verified bar" workflow reports.

## Record an approval

GitHub does not let people approve their own pull requests, so the reviewer approves one that someone else opens:

1. Anyone but the reviewer opens a pull request that adds the approval to `bar.toml`. The hash comes from:

   ```
   python3 <mission>/bar/check.py <repo> --spec-hash
   ```

   It prints the hash of the spec files, the public page, and the list of code under proof, and lists what it covers. The entry is:

   ```
   [[spec.approval]]
   reviewer = "their-github-handle"
   date = "2026-11-02"
   sha256 = "<the hash>"
   record = "https://github.com/Proven-Commons/<repo>/pull/<n>"
   ```

   Until the review lands, item 1 reads OPEN.
2. The reviewer reviews the spec, checks the hash, and approves that pull request on GitHub. The review starts a new run of the check, which confirms it.
3. Merge it without pushing anything more to it. A push after the approval leaves the approved text behind, and a branch rule that dismisses stale approvals would dismiss it.

## Run the self-tests

```
python3 -m unittest discover -s bar/tests -v
BAR_LEAN=1 python3 -m unittest discover -s bar/tests -k LeanTest -v
```

The second line builds the template and runs `lake comparator` on planted faults: a weakened statement, a `sorry`, and an `implemented_by` that the kernels cannot see but the source rule catches. Run `lake build` in `template/` first.
