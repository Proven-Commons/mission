/-
  Finding F1 of the 2026-10-24 bar audit: the headline statements do
  not imply that extraction stays inside the destination.

  `gate_sound` and `extractAll_safe` say each emitted relative
  component is not `..`, not empty, and not `.`. They do not say a
  component is free of `/`. So the statements also hold for a gate that
  keeps `a/../../etc/passwd` as one component, and the CLI joins
  components with `/` (`Main.lean`, `runManifest`).

  The tar code is safe in practice: its components come from
  `splitOn "/"`. The point is that no theorem says so.

  Run inside a checkout of Proven-Commons/tar at 7517a86:

      cp WeakStatement.lean <tar>/ && cd <tar>
      lake build && lake env lean WeakStatement.lean
-/

import TarPilot

open TarPilot

/-- The conclusion of `extractAll_safe`, copied from `Archive.lean`. -/
def PublishedSafe (dest path : List String) : Prop :=
  ∃ rel, path = dest ++ rel ∧ ".." ∉ rel ∧ "" ∉ rel ∧ "." ∉ rel ∧ rel ≠ []

/-- 1. A path that climbs out of `out` satisfies the published conclusion. -/
theorem escaping_path_is_published_safe :
    PublishedSafe ["out"] ["out", "../../etc/passwd"] :=
  ⟨["../../etc/passwd"], rfl, by decide, by decide, by decide, by simp⟩

/-- Joined the way `runManifest` joins it, that path is `out/../../etc/passwd`. -/
theorem escaping_path_joined :
    String.intercalate "/" ["out", "../../etc/passwd"] = "out/../../etc/passwd" := by
  decide

/-- 2. A broken gate that never splits the name on `/`. -/
def badGate (name : String) : Option (List String) :=
  if name.startsWith "/" then none
  else match cleanComponents [name] with
    | some (r :: rs) => some (r :: rs)
    | _ => none

/-- It proves the exact statement of `gate_sound`. -/
theorem badGate_sound : ∀ (name : String) (rel : List String),
    badGate name = some rel →
    ".." ∉ rel ∧ "" ∉ rel ∧ "." ∉ rel ∧ rel ≠ [] := by
  intro name rel h
  unfold badGate at h
  split at h
  · exact absurd h (by simp)
  · split at h
    · rename_i r rs hc
      injection h with h'
      subst h'
      obtain ⟨h1, h2, h3⟩ := cleanComponents_sound _ _ hc
      exact ⟨h1, h2, h3, by simp⟩
    · exact absurd h (by simp)

-- What it lets through: expect `some ["a/../../etc/passwd"]`.
#eval badGate "a/../../etc/passwd"

-- Expect only the standard axioms.
#print axioms escaping_path_is_published_safe
#print axioms badGate_sound
