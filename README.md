# Proven Commons

[Visit the Proven Commons website](https://proven-commons.github.io/mission/)

Proven Commons rewrites widely used software libraries in Lean and proves that the new code follows its written specification. It is a programme of Foundation-0, a non-profit organisation. It also trains future verifiers on live work: trainees learn by shipping real verified modules, with a mentor checking their work.

A finished project publishes the library, the specification, a proof a computer can check, and a test report that compares the new code against the original on millions of inputs.

## The verified bar

A project may use the word verified in public only when all of these hold:

- The specification is public and was approved by a reviewer apart from the author.
- The build has no `sorry` or `admit`.
- `#print axioms` on each main theorem shows only the standard Lean axioms.
- Differential tests against the original ran, and the count, seed, and result are in the repo.
- The public page lists what is outside the proof: runtime, compiler, hardware, and any unverified code.
- A stranger can clone the repo, run one command, and re-check the proof.

## First projects

Pilot (complete): the tar extractor lives in its own repo, [tar](https://github.com/Proven-Commons/tar). It has a proved rule that no file in an archive can be written outside the destination folder. Its project page states what is proved, what is not proved, and the recorded test results.

Wave 1: a policy engine in the style of AWS Cedar, a reader for the SQLite file format, and a parser for the Redis protocol with a small key-value store.

Candidate list: [CANDIDATES.md](CANDIDATES.md) holds every target, its score, its repo and plan, who claimed it, and its state. It is updated as targets ship and new candidates are proposed.

Each project sends reusable lemmas to CSLib and Mathlib, the shared libraries for computer science and mathematics in Lean. The shared library grows. The next project starts cheaper.

## Learn here

- Level 0, Reader: Lean basics and a small codec proof. Two weeks, open to all.
- Level 1, Apprentice: one lemma or parser function inside a live project. Eight weeks.
- Level 2, Verifier: own a module from specification to proof to public page.
- Level 3, Spec Lead and Mentor: write and review specifications, run a squad, teach Level 1.

Graduation at each level is merged work that a computer checked. That record is the proof of work an employer can check in minutes.

## Read more

See FOUNDING-BRIEF.md for the full plan: how a project moves through the factory, how the academy works, how the org is funded, and the 90-day plan.

## Website

The public website is a static, buildless GitHub Pages site. Pages publishes the root of `main`; `.nojekyll` serves the files directly. Changes to `index.html` or `assets/` publish automatically after they reach `main`. No package installation, build system, secrets, or third-party scripts are required.

To preview locally, run `python3 -m http.server 8000` from the repository root and open `http://localhost:8000`. The site's relative asset URLs also work under GitHub Pages' `/mission/` project path. The custom 404 page links back to that production path.

Keep programme facts in step with this README and the founding brief. Treat roadmap projects, academy structure, and year-one measures as plans or targets. Check the tar project's own README and recorded results before updating pilot claims, and preserve the distinction between proved path confinement and unproved filesystem integration. The site uses Google Fonts with system fallbacks; navigation and expandable factory steps work without JavaScript.
