/-
  A proposed fix for finding F1 of the 2026-10-24 bar audit: statements
  that do imply containment, proved in core Lean.

  Two changes against Proven-Commons/tar at 7517a86:

  - The cleaner also rejects a component that holds `/` or NUL. On any
    archive that `parseArchive` reads, this changes no output: header names
    stop at the first NUL, and components come from `splitOn "/"`. The
    `#eval` at the end checks every name in the pilot's tests. The check
    makes the property easy to prove instead of resting on an unproved
    fact about `String.splitOn`.
  - Three theorems. `extractAll_contained`: every emitted path is the
    destination followed by a non-empty list of plain names.
    `extractAll_joined`: the path string the command-line tool builds, by
    joining the components with `/`, splits back into exactly those
    components. `extractAll_resolves_inside`: resolving that string the way
    POSIX resolves a relative path, without symlinks, gives the resolved
    destination followed by the plain names, so nothing climbs out. The
    last two assume the destination's own components hold no `/`, which
    is true of the destination the tool builds with `splitOn "/"`.

  Still outside the proof: the filesystem (symlinks already on disk,
  races between check and write) and whatever destination a caller passes.

  Run inside a checkout of Proven-Commons/tar at 7517a86:

      cp Contained.lean <tar>/ && cd <tar>
      lake build && lake env lean Contained.lean
-/

import TarPilot

open TarPilot

namespace Contained

/-- A component that names one entry inside its directory. -/
def PlainName (c : String) : Prop :=
  c ≠ "" ∧ c ≠ "." ∧ c ≠ ".." ∧ '/' ∉ c.toList ∧ Char.ofNat 0 ∉ c.toList

/-- The cleaner, also rejecting a component that holds `/` or NUL. -/
def cleanComponents : List String → Option (List String)
  | [] => some []
  | c :: cs =>
    if c = ".." ∨ '/' ∈ c.toList ∨ Char.ofNat 0 ∈ c.toList then none
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
            exact ⟨hskip.1, hskip.2, hbad.1, hbad.2.1, hbad.2.2⟩
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

/-- The components a system sees in a path string: the parts between `/`. -/
def pathComponents (s : String) : List String :=
  (s.split '/').toList.map (·.copy)

theorem pathComponents_join (l : List String) (hl : ∀ s ∈ l, '/' ∉ s.toList)
    (hne : l ≠ []) : pathComponents (String.intercalate "/" l) = l := by
  have h := String.toList_split_intercalate (c := '/') hl
  simp only [hne, ite_false] at h
  exact h

/-- The path string the command-line tool builds (`Main.lean`, `runManifest`)
    splits back into the destination followed by plain names. -/
theorem extractAll_joined : ∀ (dest : List String) (entries : List RawEntry)
    (path : List String) (bytes : ByteArray),
    (∀ d ∈ dest, '/' ∉ d.toList) →
    (path, bytes) ∈ extractAll dest entries →
    ∃ rel, rel ≠ [] ∧ (∀ c ∈ rel, PlainName c) ∧
      pathComponents (String.intercalate "/" path) = dest ++ rel := by
  intro dest entries path bytes hdest h
  obtain ⟨rel, hne, hpath, hplain⟩ := extractAll_contained dest entries path bytes h
  refine ⟨rel, hne, hplain, ?_⟩
  subst hpath
  apply pathComponents_join
  · intro s hs
    rcases List.mem_append.mp hs with hs | hs
    · exact hdest s hs
    · exact (hplain s hs).2.2.2.1
  · simp [hne]

/-- Resolve the components of a relative path as POSIX does, without
    symlinks: `..` drops the last component, or is kept when nothing is
    left to drop or the last is itself `..`; empty and `.` change nothing. -/
def resolve : List String → List String → List String
  | acc, [] => acc
  | acc, c :: cs =>
    if c = "" ∨ c = "." then resolve acc cs
    else if c = ".." then
      if acc = [] ∨ acc.getLast? = some ".." then resolve (acc ++ [".."]) cs
      else resolve acc.dropLast cs
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
      · split
        · exact ih ys _
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
    simp only [resolve, h1, h2, h3, or_self, ite_false]
    rw [ih _ hcs]
    simp

/-- Containment: the path string the tool builds, resolved as POSIX
    resolves a relative path, is the resolved destination followed by
    the plain names. No `..` in an archive can reach above it. -/
theorem extractAll_resolves_inside : ∀ (dest : List String)
    (entries : List RawEntry) (path : List String) (bytes : ByteArray),
    (∀ d ∈ dest, '/' ∉ d.toList) →
    (path, bytes) ∈ extractAll dest entries →
    ∃ rel, rel ≠ [] ∧ (∀ c ∈ rel, PlainName c) ∧
      resolve [] (pathComponents (String.intercalate "/" path)) = resolve [] dest ++ rel := by
  intro dest entries path bytes hdest h
  obtain ⟨rel, hne, hplain, hjoin⟩ := extractAll_joined dest entries path bytes hdest h
  exact ⟨rel, hne, hplain, by rw [hjoin, resolve_append, resolve_plain rel _ hplain]⟩

end Contained

-- The new gate agrees with the old one on every name in the pilot's
-- tests (tests/run_tests.py, archive A and the create inputs).
#eval ["hello.txt", "dir/nested.bin", "empty.txt", "big.bin", "dir", "../evil.txt",
  "a/../../evil2.txt", "/abs.txt", "./dot.txt", "a//b.txt", "a/./c.txt", "link.txt",
  String.ofList (List.replicate 50 'p') ++ "/" ++ String.ofList (List.replicate 70 'x') ++ ".txt",
  "deep/d0/d1/d2/d3/d4/d5/d6/d7/leaf.txt", "x.txt", "sub/y.bin",
  String.ofList (List.replicate 60 'q') ++ "/" ++ String.ofList (List.replicate 50 'z') ++ ".bin"].all
  (fun n => Contained.gate n == TarPilot.gate n)

-- The statement tells a safe gate from a broken one. WeakStatement's
-- `badGate` keeps "a/../../etc/passwd" as one component; joined under
-- "out" and resolved, that path is ["etc", "passwd"], not inside "out".
#eval Contained.resolve [] (Contained.pathComponents (String.intercalate "/" ["out", "a/../../etc/passwd"]))

-- Expect only the standard axioms.
#print axioms Contained.extractAll_contained
#print axioms Contained.extractAll_resolves_inside
