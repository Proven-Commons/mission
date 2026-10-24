# clamp: a template for a Proven Commons library

This repo is the layout every Proven Commons library follows, shown on a function small enough to read in a minute: clamp a number into a range. Copy it to start a new library, then replace the code, the specification, and this page. The rules it follows are in [playbook/verified-bar.md](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md).

Status: in progress. The specification has not been approved by a reviewer, so this is not verified.

## What is proved

| Claim | Theorem |
|-------|---------|
| When `lo ≤ hi`, `clamp lo hi x` is never below `lo` or above `hi`. | `Spec.clamp_in_range` |
| A value already between `lo` and `hi` comes back unchanged. | `Spec.clamp_of_mem` |

The statements are in `Spec.lean`, the proofs in `Proofs.lean`. The command-line tool in `Main.lean` calls the proved `Clamp.clamp` directly.

## What is not proved

- Parsing the input lines and printing the results in `Main.lean`. The differential tests cover them.
- How fast it runs.

## What you must trust

- The Lean kernel and the five external kernels shipped with Lean, which all check the proofs.
- The Lean compiler and runtime, which turn the proved definitions into the program that runs.
- The hardware it runs on.
- Python, as the oracle in the differential tests.

## Re-check it

Needs Linux, [elan](https://github.com/leanprover/elan), and bubblewrap (`apt install bubblewrap`).

```
lake build
lake comparator --paranoid
python3 tests/run_tests.py
```

`lake comparator --paranoid` builds the project in a sandbox, checks that each theorem in `Proofs.lean` proves exactly the statement in `Spec.lean`, checks that it uses only the axioms `propext`, `Classical.choice`, and `Quot.sound`, and replays it through every kernel shipped with Lean. The test script compares the tool with the oracle on a million inputs and rewrites `tests/TEST-RESULTS.md`.

## Layout

- `Clamp.lean`: the code under proof.
- `Spec.lean`: the statements, with `sorry` for proofs. This is the file a reviewer approves.
- `Proofs.lean`: the proofs, under the same names.
- `Main.lean`: the command-line tool used by the tests.
- `lakefile.toml`: the build. It names the libraries and the executable, and sets nothing else.
- `comparator.json`: which theorems `lake comparator` checks, and which axioms it allows.
- `bar.toml`: the project's record for the bar check: authors, approvals, and where things are.
- `SPEC.md`: the specification in plain words.
- `tests/run_tests.py`: differential tests against the oracle.
