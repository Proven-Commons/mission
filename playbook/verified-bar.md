# The verified bar

Bar version 2, 2026-10-24. It replaces the six-item bar the founding brief started with. The last sections say what changed, why, and what the bar does not cover.

A project may use the word verified in public only when every item below holds. A machine checks most of them. The rest are a person's judgment, recorded so that a machine can tell whether that judgment still applies to what is in the repo.

## The items

1. **The specification is public, approved by a reviewer apart from the author, and pinned.** The specification is `SPEC.md` in plain words and a Lean file of theorem statements with `sorry` where the proofs go, called the challenge file. A reviewer on the org's list of spec reviewers, who wrote neither, approves them. The approval also covers `comparator.json`, the programs people run, the test generator, the list of code under proof, and the whole project page, since a claim anywhere on the page is a public claim. The approval is the reviewer's approving review of the GitHub pull request that records it in `bar.toml`, with the SHA-256 of what was approved. Any later change to any of it voids the approval until a reviewer approves the new text.

2. **Each public claim names the theorem behind it, and the theorem says what the claim says.** What is proved is a table of claims in plain words, each with its theorem. The reviewer reads each statement against its claim and tries to write a wrong program that still meets the statement. If one exists, the statement is too weak. A safety statement also holds for a program that does nothing, so the specification pairs each one with a statement that such a program fails, or the page says that usefulness rests on tests alone.

3. **The proofs prove the approved statements, and one command re-checks them.** `comparator.json` names every theorem in the challenge file. `lake comparator --paranoid` builds the challenge and the proofs in a sandbox and checks that each named theorem proves exactly the statement in the challenge file, uses no axiom but `propext`, `Classical.choice`, and `Quot.sound`, and is accepted by Lean's kernel and by every other kernel shipped with Lean. It does not build the program people run; item 4 covers that. Each statement depends only on the spec files, on the code under proof named in `bar.toml`, and on code from outside the project. A definition or instance anywhere else in the project could change what a statement means without changing its text, and the approval would not notice. `lean-toolchain` pins an exact Lean release.

4. **The code that runs is the code that was proved.** Kernels check the logical definitions, not the compiled program, and some Lean features let the two differ, skip the kernel, or change what a statement means. Project code does not use `implemented_by`, `extern`, `unsafe`, native evaluation (`native_decide`, `decide +native`), `debug.skipKernelTC`, or `axiom`, and has no `sorry` or `admit` outside the challenge file. It does no metaprogramming: no `import Lean`, and no `macro`, `syntax`, `elab`, `notation`, or `run_cmd`. The build is a `lakefile.toml` that sets no compiler or linker arguments and no plugins. Each exception is listed in `bar.toml` with its reason and named under What you must trust. The programs people run, whether a command-line tool or the library's entry points, call the proved functions, not copies of them.

5. **Differential tests ran against the original, and the record is in the repo.** The inputs are random, from a recorded seed, and mutated from those samples where the input has a structure to mutate. The committed `tests/TEST-RESULTS.md` records the oracle and its version, the seed, the number of inputs, and the failures, and a fresh run gives the same seed, count, and failures. There are no failures. A case where the original is wrong is left out of the comparison by the test script, with a link to its bug report, and listed under What is not proved.

6. **The public page lists what is outside the proof.** It has a `Status:` line that matches `bar.toml`, and the sections What is proved, What is not proved, What you must trust, and Re-check it. What you must trust names at least the Lean kernel, the compiler, the runtime, the hardware, every dependency in `lake-manifest.json`, and every exception from item 4. Re-check it gives `lake comparator --paranoid` and the test command.

7. **The check runs in CI and blocks releases.** Every push, pull request, and review runs the verified-bar workflow from this repo. The default branch requires its check, and releases are tagged only from the default branch.

## How each item is checked

`bar/check.py` in this repo checks a project, and `.github/workflows/verified-bar.yml` runs it in CI. It gives each item one status:

- PASS: checked and met.
- FAIL: checked and not met.
- OPEN: not met yet, which a project marked `in-progress` in `bar.toml` may be. An unfinished proof, a missing approval, or a missing record is OPEN. A forbidden axiom or feature, a failing test, or a reviewer who wrote the spec is FAIL, even while in progress.
- SKIP: not checked in this run, for example offline.

A run exits 1 when an item fails, or when `bar.toml` says `verified` and any item is not PASS. Only a run where every item passes may be called verified.

| Item | What the machine checks | What only a person can judge |
|------|-------------------------|------------------------------|
| 1 | The recorded hash equals the hash of what the approval covers now. The reviewer is on `bar/reviewers.toml` in this repo, is not a listed spec author, and is not the GitHub author of any commit to the spec files. GitHub shows the reviewer's approving review of the pull request that added this approval to `bar.toml`, at a commit where the covered text had this same hash. | Whether the specification is right. |
| 2 | Every theorem in `comparator.json` is named under What is proved. | Whether each statement says what its claim says, whether a wrong program can meet it, and whether a program that does nothing can. |
| 3 | `lake comparator --paranoid` passes. Only the three standard axioms are permitted. The challenge file is one of the spec files, and `comparator.json` names every theorem in it. A walk over each statement, in a sandbox, finds no project definition or instance outside the spec files and the code under proof, and finds some code under proof. The toolchain is pinned. | Whether the list of code under proof is right. |
| 4 | No forbidden feature or metaprogramming appears outside comments and strings, and `lakefile.toml` uses only allowed keys, except for listed exceptions. It lists the instance declarations outside the challenge file. | Whether the programs people run call the proved functions, and whether an instance changes what a statement means. |
| 5 | The committed record names the oracle, the seed, and the input count, with zero failures, and CI reruns the tests and gets the same numbers. | Whether the inputs reach the cases each claim depends on. |
| 6 | The status line matches `bar.toml`. The four sections exist, the trust section names what it must, and Re-check it gives both commands. | Whether the text is true and complete. |
| 7 | A workflow at the top of the repo calls the verified-bar workflow, and the default branch requires the `bar / bar` check. | That releases are tagged only from the default branch. |

The person checks happen once, at approval, and the hash pins everything that person judged. That is why any change to the page, the entry points, or the tests voids the approval: a claim cannot grow after review, wherever it is written. Keep numbers that change often, such as test counts, in `tests/TEST-RESULTS.md` rather than on the page.

## What a library repo contains

Copy [bar/template](../bar/template) to start. It passes every item except the approval and the branch rule, which people supply.

- `lean-toolchain` and `lake-manifest.json`, so `lake comparator` builds what was checked.
- `lakefile.toml`: the libraries and the executable, and nothing else.
- The code under proof, for example `Clamp.lean`.
- The challenge file, `Spec.lean`: the statements, with `sorry`, and any definition they need besides the code under proof.
- `Proofs.lean`: the proofs, under the same names.
- `comparator.json`: the challenge and solution modules, every theorem in the challenge file, and the three permitted axioms.
- `SPEC.md`: the specification in plain words, including a table from each property to its theorem.
- `bar.toml`: the project's status, its page, its spec authors and files, its entry points, the code under proof, each approval, its tests, and any exception to item 4.
- `Main.lean`: the program people run, which calls the proved functions.
- `tests/`: the differential tests and `TEST-RESULTS.md`.
- `README.md`: the project page, with its status line and four sections.
- `.github/workflows/bar.yml`: calls the verified-bar workflow, pinned to one version of this repo.

## The reviewer's checklist

1. Read `SPEC.md` and the challenge file. For each claim on the page, find its theorem, and check that every word of the claim is backed by the statement.
2. Try to break each statement. Write a program that is wrong but still meets it, in Lean if you can. The [tar audit](../reviews/tar/evidence/WeakStatement.lean) shows the method. If you can write one, the statement is too weak.
3. Check that a program that does nothing does not meet every statement.
4. Check the list of code under proof in `bar.toml`: it should name the functions the claims are about, and nothing that only gives a statement its meaning. Read each definition the statements use, and each instance the checker lists. An instance in the code can change what a symbol such as `≤` means in the challenge file, and `lake comparator` cannot see it, because both sides import the same code.
5. Check that the programs people run call the proved functions.
6. Read the test generator. Check that its inputs reach the cases each claim depends on.
7. Read the whole page. Look for claims outside What is proved, for what is missing from What is not proved and What you must trust, and for anything false. Run probes against the program where you can.
8. When it holds up, ask the author to open a pull request that adds your approval to `bar.toml`, with the hash from `python3 check.py --spec-hash <repo>` in this repo's `bar/` folder. Check the hash yourself, and approve that pull request on GitHub. Nothing should be pushed to it after you approve.

## Why version 2

Version 1 had six items. The [audit of the tar pilot](../reviews/tar/2026-10-24-bar-audit.md) on 2026-10-24 found three of them met while the pilot's public claim was not proved:

- The headline theorem stated less than its claim, and every machine check passed. Now the approval covers the claims, item 2 asks the reviewer to try to break each statement, and `lake comparator` holds the proofs to the approved statements.
- `lake build` succeeded with a `sorry`, and the project's homemade axiom check let `axiom cheat : False` through. Now item 3 uses Lean's own tool, with a list of allowed axioms and six kernels.
- The command-line tool re-implemented the proved loop instead of calling it. Now item 4 asks for the programs people run to call the proved functions, and the approval covers them.
- Two statements on the page about what was not proved were false. Now the reviewer approves the whole page, and item 5 asks for random and mutated inputs.
- No one command on the page re-checked the proof: `lake build` accepted a `sorry`, and the test script accepted a new axiom. Now `lake comparator --paranoid` does it alone.

More gaps were found while writing this version, each now closed and planted in the self-tests:

- In a copy of the tar pilot, `@[implemented_by]` pointed the path gate at a function that checks nothing. `lake comparator` still reported "Your solution is okay!" and `#print axioms` showed only the standard three, while the compiled program extracted `../evil.txt` to `out/../evil.txt` ([evidence](../reviews/tar/evidence/implemented_by.py)). No kernel can see this, so item 4 forbids the feature.
- A metaprogram could do the same without writing `implemented_by`, by calling Lean's own API from `run_cmd`. So item 4 also forbids metaprogramming and build settings that change the program.
- An instance or a definition in the code could change what an approved statement means, with no change to its text. So item 3 walks each statement's dependencies.
- A claim could be added to the page outside the reviewed sections, a theorem could be dropped from `comparator.json`, and an approval of an unrelated pull request could count. So the approval now covers all of these, and must be on the pull request that records it.

Lean 4.35 ships the tools this bar rests on: `lake comparator` and five kernels besides Lean's own (`leanchecker-paranoid`, `lean4lean`, `nanoda`, `con-leche`, `con-ron`). The bar uses them instead of homemade proof checks.

## What the bar does not cover

- The soundness of Lean's logic, and a bug that every kernel shares.
- The compiler and runtime. With item 4 met, the program comes from the proved definitions, but a compiler bug could still make it differ.
- Whether the specification is the right one. That stays a person's judgment, which is why the reviewer must not be the author.
- Speed.
- The checker itself, and this repo. Every library runs the checker from here, so this repo's main branch needs the same protection as a release, and each library pins the version it runs.
