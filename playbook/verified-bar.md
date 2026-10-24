# The verified bar

Version 2, 2026-10-24. It replaces the six-item bar the founding brief started with. The last section says what changed and why.

A project may use the word verified in public only when every item below holds. A machine checks most of them. The rest are a person's judgment, recorded so that a machine can tell whether the judgment still applies to the text in the repo.

## The items

1. **The specification is public, approved by a reviewer apart from the author, and pinned.** The specification is two files: `SPEC.md` in plain words, and a Lean file of theorem statements with `sorry` where the proofs go, called the challenge file. A reviewer who wrote neither approves them, together with three sections of the project page: What is proved, What is not proved, and What you must trust. The approval is the reviewer's approving review on the GitHub pull request that records it in `bar.toml`, with the SHA-256 of the approved text. Any later change to that text voids the approval until a reviewer approves the new text.

2. **Each public claim names the theorem behind it, and the theorem says what the claim says.** What is proved is a table of claims in plain words, each with its theorem. The reviewer reads each statement against its claim and tries to write a wrong program that still meets the statement. If one exists, the statement is too weak. A safety statement also holds for a program that does nothing, so the specification pairs each one with a statement that such a program fails, or the page says that usefulness rests on tests alone.

3. **The proofs prove the approved statements, and one command re-checks them.** `lake comparator --paranoid` builds the project in a sandbox. It checks that each theorem named in `comparator.json` proves exactly the statement in the challenge file, uses no axiom but `propext`, `Classical.choice`, and `Quot.sound`, and is accepted by Lean's kernel and by every other kernel shipped with Lean. A `sorry` anywhere a theorem depends on fails it. `lean-toolchain` pins an exact Lean release.

4. **The code that runs is the code that was proved.** Kernels check the logical definitions, not the compiled program, and some Lean features let the two differ or skip the kernel. Project code does not use `implemented_by`, `extern`, `unsafe`, native evaluation (`native_decide`, `decide +native`), `debug.skipKernelTC`, or `axiom`, and has no `sorry` or `admit` outside the challenge file. Each exception is listed in `bar.toml` with its reason and named under What you must trust. The program people run, whether a command-line tool or the library's entry points, calls the proved functions, not copies of them.

5. **Differential tests ran against the original, and the record is in the repo.** The inputs are random and mutated, from a recorded seed. `tests/TEST-RESULTS.md` records the oracle and its version, the seed, the number of inputs, and the failures. There are no failures, or each one is filed as a bug report against the code, the specification, or the original. One command reruns the tests.

6. **The public page lists what is outside the proof.** It has the sections What is proved, What is not proved, What you must trust, and Re-check it. What you must trust names at least the Lean kernel, the compiler, the runtime, the hardware, and every exception from item 4. Re-check it gives `lake comparator --paranoid` and the test command.

7. **The check runs in CI and blocks releases.** Every push and pull request runs the verified-bar workflow from this repo. The default branch requires it to pass, and releases are cut only from a commit where it passed.

## How each item is checked

`bar/check.py` in this repo checks a project, and `.github/workflows/verified-bar.yml` runs it in CI. It gives each item one status: PASS, FAIL, OPEN (not met yet, which a project marked `in-progress` may be), or SKIP (not checked in that run). Only a run where every item passes may be called verified.

| Item | What the machine checks | What only a person can judge |
|------|-------------------------|------------------------------|
| 1 | The recorded hash equals the hash of the current text. The reviewer is not a listed spec author and did not commit to the spec files. GitHub shows the reviewer's approving review on the recorded pull request, made at a commit where the text has that same hash, so the reviewer approved exactly this text. | Whether the specification is right. |
| 2 | Every theorem in `comparator.json` is named under What is proved. | Whether each statement says what its claim says, whether a wrong program can meet it, and whether a program that does nothing can. |
| 3 | `lake comparator --paranoid` passes. Only the three standard axioms are permitted. The challenge file is one of the approved spec files. The toolchain is pinned. | Nothing. |
| 4 | No forbidden feature appears outside comments and strings, except listed exceptions. | Whether the program people run calls the proved functions. |
| 5 | The record names the oracle, the seed, and the input count, with zero failures. CI reruns the tests first. | Whether the inputs reach the cases that matter. |
| 6 | The four sections exist, the trust section names what it must, and Re-check it gives both commands. | Whether the text is true and complete. |
| 7 | A workflow runs the check. | The branch rule is a repo setting, set by an org admin. |

The person checks happen once, at approval, and the hash pins the text that person judged. That is why a change to a claim or a limit on the page voids the approval: a claim can no longer grow after review.

## What a library repo contains

Copy [bar/template](../bar/template) to start. It passes every item except the approval.

- `lean-toolchain` and `lake-manifest.json`, so `lake comparator` builds what was checked.
- The code under proof, for example `Clamp.lean`.
- The challenge file, `Spec.lean`: the statements, with `sorry`.
- `Proofs.lean`: the proofs, under the same names.
- `comparator.json`: the challenge and solution modules, the theorem names, and the three permitted axioms.
- `SPEC.md`: the specification in plain words, including a table from each property to its theorem.
- `bar.toml`: the project's status, its page, its spec authors and files, each approval, its test record and command, and any exception to item 4.
- `tests/`: the differential tests and `TEST-RESULTS.md`.
- `README.md`: the project page, with the four sections.
- `.github/workflows/bar.yml`: calls the verified-bar workflow.

## The reviewer's checklist

1. Read `SPEC.md` and the challenge file. For each claim on the page, find its theorem, and check that every word of the claim is backed by the statement.
2. Try to break each statement. Write a program that is wrong but still meets it, in Lean if you can. The [tar audit](../reviews/tar/evidence/WeakStatement.lean) shows the method. If you can write one, the statement is too weak.
3. Check that a program that does nothing does not meet every statement.
4. Read each definition the statements use, and any notation or macro the checker reports.
5. Check that the program people run calls the proved functions.
6. Read What is not proved and What you must trust. Look for what is missing and for what is false. Run probes against the program where you can.
7. When it holds up, run `python3 check.py --spec-hash <repo>` from this repo's `bar/` folder, add the approval to `bar.toml` in the pull request, and approve that pull request on GitHub.

## Why version 2

Version 1 had six items. The [audit of the tar pilot](../reviews/tar/2026-10-24-bar-audit.md) on 2026-10-24 showed a project meeting most of its letter while its public claim was not proved:

- The headline theorem stated less than its claim, and every machine check passed. Now item 1 covers the claims on the page, item 2 asks the reviewer to try to break each statement, and `lake comparator` holds the proofs to the approved statements.
- `lake build` succeeded with a `sorry`, and the project's homemade axiom check let `axiom cheat : False` through. Now item 3 uses Lean's own tool, with a list of allowed axioms and six kernels.
- The command-line tool re-implemented the proved loop instead of calling it. Now item 4 asks for the program people run to call the proved functions.
- Two statements on the page about what was not proved were false. Now the reviewer approves those sections, and item 5 asks for random and mutated inputs.
- Re-checking took three commands. Now it takes one.

One more gap was found while writing this version. In a copy of the tar pilot, `@[implemented_by]` pointed the path gate at a function that checks nothing. `lake comparator --paranoid` still reported "Your solution is okay!" and `#print axioms` showed only the standard three. Meanwhile the compiled program extracted `../evil.txt` to `out/../evil.txt`. No kernel can see this, so item 4 forbids the feature in project code. The template's tests repeat the experiment on every CI run.

Lean 4.35 ships the tools this bar uses: `lake comparator`, `lake check`, and five kernels besides Lean's own (`leanchecker-paranoid`, `lean4lean`, `nanoda`, `con-leche`, `con-ron`). The bar uses them instead of homemade scripts.

## What the bar does not cover

- The soundness of Lean's logic, and a bug that every kernel shares.
- The compiler and runtime. With item 4 met, the program comes from the proved definitions, but a compiler bug could still make it differ.
- Whether the specification is the right one. That stays a person's judgment, which is why the reviewer must not be the author.
- Speed.
