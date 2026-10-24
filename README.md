# Proven Commons

Proven Commons rewrites widely used software libraries in Lean and proves that the new code follows its written specification. It is a programme of Foundation-0, a non-profit organisation. It also trains future verifiers on live work: trainees learn by shipping real verified modules, with a mentor checking their work.

A finished project publishes the library, the specification, a proof a computer can check, and a test report that compares the new code against the original on millions of inputs.

## The verified bar

A project may use the word verified in public only when all of these hold. The [playbook page](playbook/verified-bar.md) says how each one is checked, and [bar/](bar/) holds the checker, the CI workflow, and a template for a new library.

1. The specification is public, approved by a reviewer apart from the author, and pinned. The approval records a hash of the statements and of the page's claims and limits, and any later change voids it.
2. Each public claim names the theorem behind it, and the reviewer has checked that the theorem says what the claim says.
3. One command, `lake comparator --paranoid`, re-checks that the proofs prove exactly the approved statements, with only the standard Lean axioms, under every kernel shipped with Lean.
4. The code that runs is the code that was proved. Project code uses no `implemented_by`, `extern`, `unsafe`, native evaluation, or `axiom`, and no `sorry` or `admit` outside the statements, except for exceptions the page lists.
5. Differential tests against the original ran on random and mutated inputs, and the oracle, seed, input count, and result are in the repo.
6. The public page lists what is outside the proof: the kernel, compiler, runtime, hardware, and any unverified code.
7. The check runs in CI on every change, and releases come only from commits where it passed.

## First projects

Pilot (built, not yet verified): the tar extractor lives in its own repo, [tar](https://github.com/Proven-Commons/tar). Its goal is a proved rule that no file in an archive can be written outside the destination folder. Its proofs check, but the [bar audit of 2026-10-24](reviews/tar/2026-10-24-bar-audit.md) found that the main theorem states less than that rule, that two statements on its project page are false, and that four of the six items of the first version of the bar are not yet fully met. The audit lists the fixes.

Wave 1: a policy engine in the style of AWS Cedar, a reader for the SQLite file format, and a parser for the Redis protocol with a small key-value store.

Each project sends reusable lemmas to CSLib and Mathlib, the shared libraries for computer science and mathematics in Lean. The shared library grows. The next project starts cheaper.

## Learn here

- Level 0, Reader: Lean basics and a small codec proof. Two weeks, open to all.
- Level 1, Apprentice: one lemma or parser function inside a live project. Eight weeks.
- Level 2, Verifier: own a module from specification to proof to public page.
- Level 3, Spec Lead and Mentor: write and review specifications, run a squad, teach Level 1.

Graduation at each level is merged work that a computer checked. That record is the proof of work an employer can check in minutes.

## Read more

See FOUNDING-BRIEF.md for the full plan: how a project moves through the factory, how the academy works, how the org is funded, and the 90-day plan. See [reviews/](reviews/) for review records: what an attack on a project found, with commands to reproduce it.
