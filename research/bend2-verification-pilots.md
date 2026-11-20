# Bend 2 and formal verification: a bounded integration assessment

Date: 2026-11-03. Status: research and proposed pilots, not an adopted runtime or a verified implementation.

## Recommendation

**Prototype Bend 2 on one small, pure component; retain Lean and the existing verified bar.** Spread explicit, reviewed invariants through product boundaries, rather than require one language everywhere. There is evidence of active development, but no evidence here that the technology industry has reached a consensus that Bend should replace established stacks.

Proven Commons already supplies the right foundation: reviewed specifications, exact-statement proof checking, executable linkage, differential tests, and honest proof boundaries. A new language must earn its place against that process.

## What Bend means now

The canonical project is [bendlang/bend](https://github.com/bendlang/bend). The inspected main revision is [ea66e0044fc1632c28e35b7b0f0d2263d77e3449](https://github.com/bendlang/bend/tree/ea66e0044fc1632c28e35b7b0f0d2263d77e3449); the latest release endpoint returned [v2.0.39](https://github.com/bendlang/bend/releases/tag/v2.0.39), published 2026-10-23. Main and that release are different evidence: do not assume every inspected main feature ships in that binary.

[Bend 2's README](https://github.com/bendlang/bend/blob/ea66e0044fc1632c28e35b7b0f0d2263d77e3449/README.md) explicitly says Bend 1 programs and HVM do not carry over. Older HVM/GPU-only assessments therefore miss the current dependent types and proof workflow.

The [guide](https://github.com/bendlang/bend/blob/ea66e0044fc1632c28e35b7b0f0d2263d77e3449/guide/GUIDE.md) separates reviewed laws from implementation and proof definitions. Ordinary checking is not a proved checker. The additional `--verdict` path rechecks translated terms with a kernel whose [Lean source](https://github.com/bendlang/bend/blob/ea66e0044fc1632c28e35b7b0f0d2263d77e3449/bend2/bendtt.lean) contains soundness theorems, including `book_check : Claim.sound`. This assessment inspected source, not a reproduced kernel build. The guide explicitly says translation is unproved and recommends inspecting the emitted terms.

Neither a checked law nor a sound kernel proves that the law captures the intended requirement. Neither proves the parser, translation, compiler, foreign boundary, runtime, filesystem or deployed service correct. The README warns that backend behavior can differ from the semantics under proof. Its absolute promotional claims must be read with those limitations.

## Fit and constraints

- Good candidate: deterministic pure transformations with a small input domain, explicit failures, no effects and useful algebraic laws.
- Current costs: explicit annotations; no tactics/proof search; small base library; slow linked-list strings; no built-in TLS/HTTP/JSON/regex in the inspected README; no separate compilation or incremental builds.
- Numeric constraints: Nat, U32 and F32, not U64/I64/F64. F32 is axiomatic and is unsuitable for this first proof pilot.
- Execution choices include C, Metal, CUDA and JavaScript. The JavaScript target is single-core. Balanced recursion matters for parallelism; headline speedups are not evidence for an application workload.
- The compiler is described as young, largely AI-written and not fully audited. Reject `@unsafe`, foreign dependencies and unchecked recursion from the proof slice. Do not mistake a green ordinary checker for the stronger verdict path.
- [License](https://github.com/bendlang/bend/blob/ea66e0044fc1632c28e35b7b0f0d2263d77e3449/LICENSE): Apache-2.0 at the inspected revision. Before distributing a runtime or generated artifact, inspect bundled dependency and generated-code terms, preserve applicable license/notice material, and record the exact toolchain. This is not blanket legal clearance.

## Preserve the work already done

[The verified bar](../playbook/verified-bar.md) requires independent, hash-bound specification approval; named claims; comparator checking under multiple kernels; actual entry points calling proved definitions; reproducible differential tests; trust-boundary disclosure; and release checks. Bend's verdict is not a replacement for that bar, which is currently Lean-specific.

Concrete reusable baselines already exist:

- [codec at 860b895](https://github.com/Proven-Commons/codec/tree/860b895c1a6449506d99f4b8b6c9dd8a9c5117e6): hex/base64/CRC/percent/PEM and check digits, with specifications, proofs, test records and explicit exclusions.
- [json at 4ff8eb6](https://github.com/Proven-Commons/json/tree/4ff8eb6483e21ec87da03a80abdb0af45ba9b7f2): proved printer/parser and normalized decimal round trips. A round trip alone is not full parser conformance.
- [rfc at 7ca89c9](https://github.com/Proven-Commons/rfc/tree/7ca89c914c9d9dcba41fd5db4ec52ce87de0ca41): timestamp grammar, calendar and ordering properties, with clock/table and integration boundaries.

Each inspected README explicitly says independent specification review remains pending. These are substantial existing proofs, not completed verified releases. Do not relabel them or rewrite their specifications to accommodate a new backend. Closing those review gaps may have higher immediate value than adding another language.

## Prioritized pilots

### 1. Compare one codec, without replacing it

Use the existing hex codec as the reference specification and implement a separate experimental Bend slice. Preserve exact casing, invalid-input and byte-range behavior. Prove both decode-after-encode and the accepted-language direction; a constant rejector must fail useful-behavior obligations.

Require a pinned Bend revision, ordinary check plus verdict, reviewed emitted terms and dependency closure, no unsafe/foreign assumptions, shared deterministic vectors and mutated invalid cases, and differential comparison to the existing Lean executable and a conventional oracle. Run supported JS/native backends over the same corpus; report mismatches rather than discard them.

Record proof/check time, implementation and proof size, reviewer time, peak memory, end-to-end throughput including process/serialization overhead, and license/build requirements. Initial planning estimate: 2–5 engineer-days plus independent review, not a commitment. Stop if the small slice needs trust exceptions, diverges semantically, or cannot justify maintenance cost. Do not install a production dependency from this proposal.

### 2. Specify an Exo decision boundary in shadow mode

The current [Exo gate](https://github.com/Moissanite-Labs/exo/blob/4fb581675aedd965464884e472131f2dce388e17/src/exo/gate.py) separates action classification and policy decision. First formalize the small decision relation: policy overrides cannot lower the operator floor, and approval is bound to exact action content and target. Prove the decision algebra in Lean first; use Bend only as an optional comparison implementation.

Keep shell parsing, action classification completeness, policy-file loading and enforcement outside the first proof. Shadow comparisons should use synthetic fixtures and never authorize an action. Passing the algebra's proof does not establish a secure whole gate. Scope estimate: 3–7 engineer-days after a reviewer fixes the requirements; stop at a reviewed model and discrepancy report, not a live security change.

### 3. Model recovery, rather than reimplement the ledger

The [append-authority contract](https://github.com/Moissanite-Labs/exo/blob/4fb581675aedd965464884e472131f2dce388e17/docs/LEDGER-AUTHORITY.md) already defines operation identity, expected-head conflicts, durable commits and ambiguous replies. Model transitions and prove that identical retries preserve one committed result and changed payloads cannot reuse an operation ID.

Pair the model with existing crash/replay tests. State that signatures, SQLite durability, OS isolation and external side effects remain outside this model. Do not move keys, storage or live append authority into a new runtime. Scope estimate: 1–2 weeks after pilot 1 and specification review demonstrate useful value.

## Adoption gate

A successful experiment earns an optional component, not an ecosystem migration. Before any production proposal, require a concrete consumer, an independently reviewed specification, exact source/toolchain provenance, explicit assumptions, reproducible checks, measured benefit including integration overhead, a maintained fallback and owner, and a rollback plan. Keep proofs close to the code actually executed; do not claim a separately proved model verifies an unchanged Python or TypeScript implementation.

No software was installed, no benchmark was run, and no production/security setting changed for this assessment. Sources are primary repository documents and source inspected on the date above. Existing project claims are reported as documented, not independently reverified here.
