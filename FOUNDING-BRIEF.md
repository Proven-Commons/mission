# Founding Brief: Proven Commons, a verified software factory and academy
Proven Commons is a programme of Foundation-0, a non-profit organisation. Home folder in the shared vault: `proven-commons`. Public repo: https://github.com/Foundation-0/proven-commons

This org rewrites widely used software libraries in Lean, a programming language that can check a proof that code follows its specification. It publishes the verified code as open source. It trains people by having them ship real verified modules, not by having them finish lectures.

Plain result it sells: a library, a written specification, a proof a computer can check, and a test report that compares the new code against the original on millions of inputs.

## Why this org, and why it is not a copy of an existing one

Lean FRO builds Lean itself. It works "to make formal verification more accessible across mathematics research, software and hardware verification, and AI-assisted theorem proving".

It also works to improve Lean's "scalability, usability, documentation, and proof automation". It does not ship verified replacements for the libraries the world runs on.

CSLib builds the shared library for computer science in Lean. It "aims to be for computer science what Lean's Mathlib is for mathematics" and to "facilitate the manual and AI-aided engineering of large-scale formally verified systems".

It is infrastructure. It needs production projects to use it, test it, and feed lemmas back into it. This org is one of those production projects, run as a permanent programme.

The Secure Program Synthesis Fellowship (Apart Research and Atlas Computing, June to September 2026) trains researchers. It offers "part-time research opportunities on mentor-led projects at the intersection of formal methods, AI systems, and security", in small teams, on problems in specification and validation.

It ended with the cohort. This org keeps the team, the code, and the maintenance duty after the cohort ends.

Gap this org fills: a permanent factory that picks critical libraries, verifies them to one public standard, gives the result to the upstream project, maintains it as the upstream code changes, and turns each project into training for the next group of verifiers.

## Mission

Verify the small set of libraries that most software depends on, in the open, to a standard anyone can re-check. Train enough people that the work no longer depends on a small set of experts.

## Non-goals

- Whole applications, whole operating systems, or a full database or TLS stack in one project. Projects take a slice with a clear specification.
- A new proof language or a new theorem prover. The org uses Lean 4, Mathlib, and CSLib, and sends fixes upstream.
- Certificates for sale. No project gets the verified label because a sponsor paid. A separate reviewer checks each specification and each proof.
- Closed results for open libraries. Work on public code stays public.

## How a project moves through the factory

Each project follows the same seven steps. The playbook is public. Each step has a named owner and a check.

1. Pick the target. Score it (see Target scoring). Freeze the original tests, the written specification or RFC, and sample files.
2. Write the specification in Lean. State what inputs are valid, what errors are allowed, and what must always hold. A reviewer who did not write the specification must approve it.
3. Build a proof-friendly version in Lean. Pure functions. Total functions that return an error instead of crashing. No pointer tricks carried over from C.
4. State the main theorems and the lemmas under them. Prove them. A failed proof is treated as a bug report against the code, the specification, or a missing lemma.
5. Attack the result. Check for `sorry`. Print the axioms the proof depends on. Run differential tests against the original library on random and mutated inputs. Record the input count and the failures found.
6. Ship it. Offer the code to the upstream project in the form that project can use: a Lean replacement library, or a Lean model plus a production implementation kept in step by differential tests, as AWS does with Cedar. Publish a page that states what was proved, what was not proved, and what a reader must still trust (the Lean kernel, compiler, runtime, and any foreign function code).
7. Maintain it. The proof runs in continuous integration. A change that breaks a proof blocks a release until the proof is fixed or the specification change is approved and recorded.

### The verified bar

A project may use the word verified in public only when all of these hold:

- The specification is public and was approved by a reviewer apart from the author.
- The build has no `sorry` or `admit`.
- `#print axioms` on each main theorem shows only the standard Lean axioms.
- Differential tests against the original ran, and the count, seed, and result are in the repo.
- The public page lists what is outside the proof: runtime, compiler, hardware, and any unverified parser or foreign function code.
- A stranger can clone the repo, run one command, and re-check the proof.

## Target scoring

Score each candidate 0 to 3 on each point. Take the highest total that fits the current team size. Publish the score sheet with the project.

- Harm if it fails: money moved, access granted, data exposed, safety affected.
- Reach: how much other software depends on it.
- Specification size: a short public specification scores high. A large or disputed one scores low.
- Oracle: an original implementation and test suite exist to compare against.
- Slice: a useful part can be cut out and proved on its own.
- Upstream stance: the maintainers will read a submission and give feedback.

## First wave

Pilot, months 1 to 3. One project only. Tar extractor with a proved rule that no file in an archive can be written outside the destination folder. Small specification. Clear harm story. Trainees can finish a lemma in week 2.

Wave 1, months 4 to 9. Three projects in parallel, one squad each:

- Policy engine in the style of AWS Cedar: prove that a satisfied forbid gives a deny, that no satisfied permit gives a deny, and that policy order does not change the decision.
- SQLite file reader: parse the 100-byte header, the page header, and records. Prove the parser returns an error instead of reading outside the file, and that a record it reads stays inside its page.
- Redis protocol parser and small key-value store: prove that reading what the printer wrote gives the same command back, and that a get after a set returns the set value and a get after a delete returns nothing.

Each wave sends reusable lemmas to CSLib and Mathlib. The shared library grows. The next project starts cheaper. That growth is the main long-term asset of the org.

## The academy

People learn here by shipping. Lectures support the work. They do not replace it.

Ladder:

- Level 0, Reader (2 weeks, open to all). Lean basics, reading a proof, the codec pack: base64, hex, CRC-32, each with a round-trip proof. Exit test: one small proof, no `sorry`, checked by a mentor.
- Level 1, Apprentice (8 weeks, paid or sponsored, groups of 6 to 8). Works inside a live factory project. Owns one lemma or one parser function and its tests. Exit test: code merged into a public project.
- Level 2, Verifier (6 months). Owns a module: specification, code, proofs, differential tests, and the public page. Exit test: a module that passes the verified bar with a separate reviewer.
- Level 3, Spec Lead and Mentor. Writes and reviews specifications, runs a squad, teaches Level 1. This is the senior role the job market cannot supply. The academy is the only planned source of these people.

Funnel: public hack weekend (3 days, one small specification problem), then Level 0, then a paid Level 1 cohort, then Level 2 posts in the factory or placement with a sponsor who needs a verifier. Mentors: one senior verifier per 4 apprentices. No larger ratio.

Each graduate leaves with public proof of work: merged code, a proof a computer checked, and a page that states what they proved. That record is what an employer can check in minutes.

## Team shape at start

- Director (1). Picks targets with the spec lead, raises money, holds the verified bar.
- Head of Verification (1). Owns specification review and the bar. Must not be the author of a project they approve.
- Senior Verifiers (2). Each runs one squad and mentors 4 apprentices.
- Platform Engineer (1). Build and proof checking in CI, the differential test and fuzz rig, the agent harness that lets AI models propose code and proofs for a human to review, and the public registry site.
- Academy Lead (part-time at start). Runs Level 0 and Level 1, mentor roster, and graduate records.
- Operations (part-time at start). Money, contracts, hiring, sponsor reports.

Squad shape: one spec lead, one verifier, one or two apprentices, plus AI agents whose output a human reviews before it enters the repo. Agents propose. The kernel checks. A human owns the specification and the merge.

## Money

Three sources, in this order at the start:

1. Grants and donations for public work on public libraries. This pays for the pilot and the first cohort.
2. Sponsored verification. A company pays to move a library it depends on up the queue. The score sheet, the specification, the code, and the proof stay public. Sponsorship buys priority. It does not buy the label.
3. Paid training and private work. Team training for companies, and verification of private code under contract. This work is closed by its nature. It must stay a minority of total effort, or the public factory will starve. Cap it in the annual plan and report the split.

Costs to plan for: senior verifier pay (market rate is high because supply is low), compute for proof checking and fuzz runs, mentor time, and upstream conference and travel costs. Trainee stipends come before new senior hires: the pipeline is the product.

## Measures, year 1 targets (targets, not promises)

- 1 pilot and 3 wave-1 projects pass the verified bar.
- 40 people finish Level 0. 12 finish Level 1. 4 reach Level 2.
- 10 reusable lemmas or modules accepted into CSLib or Mathlib.
- At least 2 bugs found in original libraries during specification writing, reported to upstream with a fix or a test.
- Every public claim of verified links to a repo a stranger can re-check.
- Time and cost per project recorded and published, so the next org can copy the method with real numbers.

## Risks and the plan for each

- Specification is wrong. Separate spec reviewer, adversarial review of the public page, differential tests against the original, and a standing rule that finding a spec error is a success to report, not a failure to hide.
- Upstream says no. Talk to maintainers at step 1, before code. If they decline, publish as a separate library and keep the differential tests running against new upstream releases.
- Lean code is too slow. Benchmark at step 6. If a replacement is too slow, ship the Cedar pattern instead: Lean model as the specification, production code in the original language, differential tests to keep them in step.
- Trainees leave after training. Level 2 is a paid post inside the factory, and sponsor placements pay a fee that funds the next cohort.
- AI proof tools get much better mid-project. That cuts proof cost and leaves specification and review as the human work. The academy already trains those two skills as the senior skills.
- Money runs short. The pilot must be small enough to finish on grant money alone. No wave starts without funding for its full run.

## Form: settled

Proven Commons sits under Foundation-0, a non-profit organisation. Decision made 2026-10-23. No new legal entity for the pilot.

Two other forms were set aside for now. A programme inside a company is faster to start, but a company home can blur the open promise and many grant makers need a non-profit.

A hybrid, with a separate company selling training and private verification, stays open as a later step. It needs two entities and a hard line between paid work and the verified label. Revisit it only after the first sponsored project and the first paid training cohort both exist.

## 90-day plan

Days 1 to 14: appoint the director and the head of verification, publish this brief for comment, open talks with Lean FRO and CSLib maintainers so the work feeds their libraries instead of forking them.

Days 15 to 30: hire or contract the two senior verifiers and the platform engineer. Pick the pilot from the score sheet and get written feedback from the tar format maintainers or the relevant upstream. Build the CI rig: proof check, `sorry` check, axiom print, differential test runner.

Days 31 to 75: run the pilot and Level 0 at the same time. Apprentice applications open on day 31, picked by a worked problem, not by a CV. The pilot squad posts a public progress note each week: what was specified, what was proved, what failed.

Days 76 to 90: pilot passes the verified bar or gets a public report that states where it stopped and why. Publish playbook version 1 with real time and cost numbers. Open Level 1 applications. Sign the first sponsor or grant for wave 1, or state plainly that wave 1 waits for funding.

## Decisions needed now

1. Pilot: tar extractor as set out above, or swap in the policy engine if a sponsor tied to access control appears first.
2. Director and head of verification: name the two people, or run a search for the head of verification first.
