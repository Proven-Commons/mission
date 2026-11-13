# Empirical & Solver-Backed Verification Hazards (Companion Note to Verified Bar v2)

When differential test harnesses, model checkers, or branch-and-bound lower-bound provers support a Verified Bar specification (`playbook/verified-bar.md` Item 5 & Item 6), four empirical failure modes uncovered across `223.9M`-edge discrete state-space verification ([ahrazzle/soko#42](https://github.com/ahrazzle/soko/pull/42)) and rational identifiability proofs ([Foundation-0/project-asma#97](https://github.com/Foundation-0/project-asma/pull/97)) must be explicitly ruled out:

1. **64-Bit Hash Memoization Collisions (`181.0M` Observed Probe Collisions):**
   - Across `141,107,637` canonical states on a `15x7` state lattice, 64-bit hash transposition keys produced `181,027,454` probe collisions. Unverified 64-bit hash memoization can silently alias distinct states and fabricate unsound `UNSAT` / lower-bound claims.
   - **Rule:** Store full collision-free bit-packed canonical keys (modulo proven symmetry automorphisms) whenever claiming `VERIFIED` exhaustiveness.

2. **Sticky-Gate Relaxation Mirages vs. Turn-End Coupled Re-Evaluation:**
   - Modeling state-dependent gates as monotone/sticky once opened admitted a false `34`-step solution that failed at step `30` under true turn-end gate re-evaluation (`>= 38` certified floor).
   - **Rule:** Replay every candidate trace on an independent concrete reference oracle (`oracle` differential check) and audit every quotient heuristic table via an `O(|E|)` Bellman edge-inequality pass (`h(u) <= h(v) + cost`, `0` violations; [ahrazzle/soko#48](https://github.com/ahrazzle/soko/pull/48)).

3. **Static Unit-Flow Token Borrowing Without Causal Parent Conservation:**
   - Independent unit-capacity max-flow relaxations can pass (`9/9` or `11/11` flow) by borrowing tokens across incompatible trajectories or secondary loss branches when parent conservation fails.
   - **Rule:** Pair flow bounds with explicit parent-rung conservation and an independent `O(|E|)` `(S, T)` cut-capacity replay (`cut_capacity == reported_flow`; [Moissanite-Labs/weft#182](https://github.com/Moissanite-Labs/weft/pull/182)).

4. **Pinned-Nuisance Mirages Under Floating Adversarial Re-Fit:**
   - Separation bounds proved against a fixed baseline parameter (`r_S = 16`) can collapse across an entire measurement continuum (`p in [1/20, 1]`) when the adversary re-fits a single free parameter (`r_S = 19`, `570p^2 - 169p + 17 > 0`, `Delta = -10199 < 0`).
   - **Rule:** Certify identifiability bounds either over the full unconstrained nuisance domain `(0, inf)` or via nuisance-invariant dual channels (exact `fractions.Fraction` Farkas witnesses).
