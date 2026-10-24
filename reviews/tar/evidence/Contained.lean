/-
  A proposed fix for finding F1 of the 2026-10-24 bar audit: a
  statement that does imply containment, proved in core Lean.

  Two changes against Proven-Commons/tar at 7517a86:

  - The cleaner also rejects a component that holds `/` or NUL. The
    current code can never produce one (components come from
    `splitOn "/"`, and header names stop at the first NUL), so this
    changes no output. It makes the property easy to prove instead of
    resting on an unproved fact about `String.splitOn`.
  - The theorem says every emitted relative component is a plain name,
    and, as a corollary, that resolving the joined path the POSIX way
    (`..` pops, `.` and empty stay) gives the resolved destination
    followed by the relative path. Nothing can climb out.

  Run inside a checkout of Proven-Commons/tar at 7517a86:

      cp Contained.lean <tar>/ && cd <tar>
      lake build && lake env lean Contained.lean
-/

import TarPilot

open TarPilot

namespace Contained

/-- A component that names one entry inside its directory. -/
def PlainName (c : String) : Prop :=
  c ≠ "" ∧ c ≠ "." ∧ c ≠ ".." ∧ c.contains '/' = false ∧
    c.contains (Char.ofNat 0) = false

/-- Lexical path resolution, POSIX style: `..` drops the last
    component, empty and `.` components stay where they are. -/
def resolve : List String → List String → List String
  | acc, [] => acc
  | acc, c :: cs =>
    if c = ".." then resolve acc.dropLast cs
    else if c = "" ∨ c = "." then resolve acc cs
    else resolve (acc ++ [c]) cs

theorem resolve_append : ∀ (xs ys acc : List String),
    resolve acc (xs ++ ys) = resolve (resolve acc xs) ys := by
  intro xs
  induction xs with
  | nil => intro ys acc; simp [resolve]
  | cons c cs ih =>
    intro ys acc
    simp only [List.cons_append, resolve]
    split
    · exact ih ys _
    · split
      · exact ih ys _
      · exact ih ys _

theorem resolve_plain : ∀ (rel acc : List String), (∀ c ∈ rel, PlainName c) →
    resolve acc rel = acc ++ rel := by
  intro rel
  induction rel with
  | nil => intro acc _; simp [resolve]
  | cons c cs ih =>
    intro acc h
    have ⟨h1, h2, h3, _, _⟩ := h c (by simp)
    have hcs : ∀ x ∈ cs, PlainName x := fun x hx => h x (by simp [hx])
    simp only [resolve, h3, ite_false, h1, h2, or_self]
    rw [ih _ hcs]
    simp

/-- The cleaner, also rejecting a component that holds `/` or NUL. -/
def cleanComponents : List String → Option (List String)
  | [] => some []
  | c :: cs =>
    if c = ".." ∨ c.contains '/' ∨ c.contains (Char.ofNat 0) then none
    else (cleanComponents cs).map (fun rest =>
      if c = "" ∨ c = "." then rest else c :: rest)

theorem cleanComponents_plain : ∀ (cs out : List String),
    cleanComponents cs = some out → ∀ c ∈ out, PlainName c := by
  intro cs
  induction cs with
  | nil =>
    intro out h
    simp [cleanComponents] at h
    subst h
    simp
  | cons c cs ih =>
    intro out h
    unfold cleanComponents at h
    split at h
    · simp at h
    · rename_i hbad
      cases hrec : cleanComponents cs with
      | none =>
        rw [hrec] at h
        simp at h
      | some rest =>
        rw [hrec] at h
        simp only [Option.map_some, Option.some.injEq] at h
        have ih' := ih rest hrec
        split at h
        · subst h
          exact ih'
        · rename_i hskip
          subst h
          intro x hx
          simp only [List.mem_cons] at hx
          rcases hx with rfl | hx
          · simp only [not_or] at hbad hskip
            refine ⟨hskip.1, hskip.2, hbad.1, ?_, ?_⟩
            · simpa using hbad.2.1
            · simpa using hbad.2.2
          · exact ih' x hx

/-- The gate, unchanged except for the cleaner it calls. -/
def gate (name : String) : Option (List String) :=
  if name.startsWith "/" then none
  else match cleanComponents (components name) with
    | some (r :: rs) => some (r :: rs)
    | _ => none

/-- Extraction, unchanged except for the gate it calls. -/
def extractAll (dest : List String) (entries : List RawEntry) :
    List (List String × ByteArray) :=
  entries.filterMap fun e =>
    if isRegular e then (gate e.name).map fun rel => (dest ++ rel, e.data)
    else none

/-- Every emitted path is the destination followed by a non-empty list
    of plain names. -/
theorem extractAll_contained : ∀ (dest : List String) (entries : List RawEntry)
    (path : List String) (bytes : ByteArray),
    (path, bytes) ∈ extractAll dest entries →
    ∃ rel, rel ≠ [] ∧ path = dest ++ rel ∧ ∀ c ∈ rel, PlainName c := by
  intro dest entries path bytes h
  unfold extractAll at h
  rw [List.mem_filterMap] at h
  obtain ⟨e, _, hfe⟩ := h
  split at hfe
  · cases hg : gate e.name with
    | none =>
      rw [hg] at hfe
      simp at hfe
    | some rel =>
      rw [hg] at hfe
      simp only [Option.map_some, Option.some.injEq, Prod.mk.injEq] at hfe
      unfold gate at hg
      split at hg
      · simp at hg
      · split at hg
        · rename_i r rs hc
          injection hg with hg
          subst hg
          exact ⟨_, by simp, hfe.1.symm, cleanComponents_plain _ _ hc⟩
        · simp at hg
  · simp at hfe

/-- Containment: resolving an emitted path gives the resolved
    destination followed by the relative path. -/
theorem extractAll_resolves_inside : ∀ (dest : List String)
    (entries : List RawEntry) (path : List String) (bytes : ByteArray),
    (path, bytes) ∈ extractAll dest entries →
    ∃ rel, rel ≠ [] ∧ resolve [] path = resolve [] dest ++ rel := by
  intro dest entries path bytes h
  obtain ⟨rel, hne, hpath, hplain⟩ := extractAll_contained dest entries path bytes h
  exact ⟨rel, hne, by rw [hpath, resolve_append, resolve_plain rel _ hplain]⟩

end Contained

-- The new gate agrees with the old one on every name in the pilot's tests.
#eval ["hello.txt", "dir/nested.bin", "../evil.txt", "a/../../evil2.txt",
  "/abs.txt", "./dot.txt", "a//b.txt", "a/./c.txt", ".", "", "a/b/../c"].all
  (fun n => Contained.gate n == TarPilot.gate n)

-- Expect only the standard axioms.
#print axioms Contained.extractAll_contained
#print axioms Contained.extractAll_resolves_inside
