/-
  The specification as Lean statements: the challenge file.

  A reviewer who did not write this file approves it, and `bar.toml`
  records the SHA-256 it had then. The proofs live in `Proofs.lean`;
  `lake comparator` checks that each one proves exactly the statement
  written here. The `sorry` below is expected in this file only.
-/

import Clamp

open Clamp

/-- Safety: the result is never outside the range. -/
theorem Spec.clamp_in_range (lo hi x : Nat) (h : lo ≤ hi) :
    lo ≤ clamp lo hi x ∧ clamp lo hi x ≤ hi := sorry

/-- Usefulness: a value already in range comes back unchanged.
    A function that always returns `lo` passes `clamp_in_range`
    but fails this one. -/
theorem Spec.clamp_of_mem (lo hi x : Nat) (h₁ : lo ≤ x) (h₂ : x ≤ hi) :
    clamp lo hi x = x := sorry
