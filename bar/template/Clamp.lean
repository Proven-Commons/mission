/-
  The code under proof: clamp a number into a closed range.

  Kept deliberately small. It is here to show the layout every
  Proven Commons library uses, not to be useful on its own.
-/

namespace Clamp

/-- Clamp `x` into `[lo, hi]`. When `lo > hi` the result is `lo`. -/
def clamp (lo hi x : Nat) : Nat :=
  max lo (min hi x)

end Clamp
