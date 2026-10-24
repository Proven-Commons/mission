/-
  Path safety for tar entry names.

  A tar entry name is untrusted input. Before an entry may be extracted,
  its name goes through `gate`, which produces a list of path components
  that is proved to contain no `..`, no empty component, and no `.`,
  and to be non-empty. Extraction joins those components under a
  destination, so every extracted path stays under the destination by
  construction (see `Archive.extractAll_safe`).
-/

namespace TarPilot

/-- Split a tar entry name into path components. -/
def components (name : String) : List String :=
  name.splitOn "/"

/-- Drop empty and `.` components. Fail if any component is `..`. -/
def cleanComponents : List String → Option (List String)
  | [] => some []
  | c :: cs =>
    if c = ".." then none
    else (cleanComponents cs).map (fun rest =>
      if c = "" ∨ c = "." then rest else c :: rest)

theorem cleanComponents_sound : ∀ (cs : List String) (out : List String),
    cleanComponents cs = some out →
    ".." ∉ out ∧ "" ∉ out ∧ "." ∉ out := by
  intro cs
  induction cs with
  | nil =>
    intro out h
    simp [cleanComponents] at h
    subst h
    simp
  | cons c cs ih =>
    intro out h
    rw [cleanComponents] at h
    by_cases hpar : c = ".."
    · rw [if_pos hpar] at h
      exact absurd h (by simp)
    · rw [if_neg hpar] at h
      cases hrec : cleanComponents cs with
      | none =>
        rw [hrec] at h
        simp at h
      | some rest =>
        rw [hrec] at h
        obtain ⟨h1, h2, h3⟩ := ih rest hrec
        by_cases hskip : c = "" ∨ c = "."
        · rw [Option.map_some] at h
          rw [if_pos hskip] at h
          injection h with h'
          subst h'
          exact ⟨h1, h2, h3⟩
        · rw [Option.map_some] at h
          rw [if_neg hskip] at h
          injection h with h'
          subst h'
          have hn1 : c ≠ "" := fun hc => hskip (Or.inl hc)
          have hn2 : c ≠ "." := fun hc => hskip (Or.inr hc)
          refine ⟨?_, ?_, ?_⟩
          · simp only [List.mem_cons, not_or]
            exact ⟨fun hh => hpar hh.symm, h1⟩
          · simp only [List.mem_cons, not_or]
            exact ⟨fun hh => hn1 hh.symm, h2⟩
          · simp only [List.mem_cons, not_or]
            exact ⟨fun hh => hn2 hh.symm, h3⟩

/-- The gate every entry name must pass before extraction.
    Absolute names are rejected. `..` is rejected. Empty and `.`
    components are dropped. A name with nothing left is rejected. -/
def gate (name : String) : Option (List String) :=
  if name.startsWith "/" then none
  else match cleanComponents (components name) with
    | some (r :: rs) => some (r :: rs)
    | _ => none

theorem gate_sound : ∀ (name : String) (rel : List String),
    gate name = some rel →
    ".." ∉ rel ∧ "" ∉ rel ∧ "." ∉ rel ∧ rel ≠ [] := by
  intro name rel h
  unfold gate at h
  by_cases habs : name.startsWith "/" = true
  · rw [if_pos habs] at h
    exact absurd h (by simp)
  · rw [if_neg habs] at h
    cases hclean : cleanComponents (components name) with
    | none =>
      rw [hclean] at h
      exact absurd h (by simp)
    | some out =>
      rw [hclean] at h
      obtain ⟨h1, h2, h3⟩ := cleanComponents_sound _ _ hclean
      cases out with
      | nil =>
        exact absurd h (by simp)
      | cons r rs =>
        injection h with h'
        subst h'
        exact ⟨h1, h2, h3, by simp⟩

end TarPilot
