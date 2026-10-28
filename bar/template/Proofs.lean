/-
  Proofs of the statements in `Spec.lean`, under the same names.
-/

import Clamp

open Clamp

theorem Spec.clamp_in_range (lo hi x : Nat) (h : lo ≤ hi) :
    lo ≤ clamp lo hi x ∧ clamp lo hi x ≤ hi := by
  unfold clamp
  omega

theorem Spec.clamp_of_mem (lo hi x : Nat) (h₁ : lo ≤ x) (h₂ : x ≤ hi) :
    clamp lo hi x = x := by
  unfold clamp
  omega
