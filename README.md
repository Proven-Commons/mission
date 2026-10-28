# Proven Commons

[Visit the Proven Commons website](https://proven-commons.github.io/mission/)

Proven Commons rewrites widely used software libraries in Lean and proves that the new code follows its written specification. It is a programme of Foundation-0, a non-profit organisation. It also trains future verifiers on live work: trainees learn by shipping real verified modules, with a mentor checking their work.

A finished project publishes the library, the specification, a proof a computer can check, and a test report that compares the new code against the original on millions of inputs.

## The verified bar

A project may use the word verified in public only when all of these hold. The [playbook page](playbook/verified-bar.md) says how each one is checked, and [bar/](bar/) holds the checker, the CI workflow, and a template for a new library.

1. The specification is public, approved by an independent current repository maintainer, and pinned. The approval records a hash of the specification, the whole project page, the programs people run, and the tests, and any later change voids it.
2. Each public claim names the theorem behind it, and the reviewer has checked that the theorem says what the claim says.
3. One command, `lake comparator --paranoid`, re-checks that the proofs prove exactly the approved statements, with only the standard Lean axioms, under every kernel shipped with Lean. Nothing outside the approved text and the code under proof can change what a statement means.
4. The code that runs is the code that was proved. The programs people run call the proved functions, and project code uses no `implemented_by`, `extern`, `unsafe`, native evaluation, metaprogramming, or `axiom`, and no `sorry` or `admit` outside the statements, except for exceptions the page lists.
5. Differential tests against the original ran on random and mutated inputs, and the oracle, seed, input count, and result are committed in the repo.
6. The public page lists what is outside the proof: the kernel, compiler, runtime, hardware, dependencies, and any unverified code.
7. The check runs in CI on every change, the default branch requires it, and releases are tagged only from the default branch.

## First projects

Pilot (built, not yet verified): the tar extractor lives in its own repo, [tar](https://github.com/Proven-Commons/tar). Its goal is a proved rule that no file in an archive can be written outside the destination folder. Its proofs check, but the [bar audit of 2026-10-24](reviews/tar/2026-10-24-bar-audit.md) found that the main theorem states less than that rule, that two statements under "What is not proved" on its project page are false, and that three of the six items of the first version of the bar are not yet fully met. The audit lists the fixes.

Wave 1: a policy engine in the style of AWS Cedar, a reader for the SQLite file format, and a parser for the Redis protocol with a small key-value store.

Wave 1, Redis (proofs done, specification review pending): a Lean parser and printer for the Redis protocol with a small key-value store lives in its own repo, [redis](https://github.com/Proven-Commons/redis). It proves that parsing what the printer wrote gives the same value back, that the parser accepts nothing else, and that a get after a set or delete behaves as specified. Its differential tests against hiredis and redis-server are recorded in that repo. It is not yet verified: a reviewer who did not write its specification must approve it first.

Candidate list: [CANDIDATES.md](CANDIDATES.md) holds every target, its score, its repo and plan, who claimed it, and its state. It is updated as targets ship and new candidates are proposed.

Each project sends reusable lemmas to CSLib and Mathlib, the shared libraries for computer science and mathematics in Lean. The shared library grows. The next project starts cheaper.

## Learn here

- Level 0, Reader: Lean basics and a small codec proof. Two weeks, open to all.
- Level 1, Apprentice: one lemma or parser function inside a live project. Eight weeks.
- Level 2, Verifier: own a module from specification to proof to public page.
- Level 3, Spec Lead and Mentor: write and review specifications, run a squad, teach Level 1.

Graduation at each level is merged work that a computer checked. That record is the proof of work an employer can check in minutes.

## Read more

See FOUNDING-BRIEF.md for the full plan: how a project moves through the factory, how the academy works, how the org is funded, and the 90-day plan. See [reviews/](reviews/) for review records: what an attack on a project found, with commands to reproduce it.

## Website

The public website is a static, buildless GitHub Pages site. Pages publishes the root of `main`; `.nojekyll` serves the files directly. Changes to `index.html` or `assets/` publish automatically after they reach `main`. No package installation, build system, secrets, or third-party scripts are required.

To preview locally, run `python3 -m http.server 8000` from the repository root and open `http://localhost:8000`. The site's relative asset URLs also work under GitHub Pages' `/mission/` project path. The custom 404 page links back to that production path.

Keep programme facts in step with this README and the founding brief. Treat roadmap projects, academy structure, and year-one measures as plans or targets. Check the tar project's own README and recorded results before updating pilot claims, and preserve the distinction between proved path confinement and unproved filesystem integration. The site uses Google Fonts with system fallbacks; navigation and expandable factory steps work without JavaScript.
