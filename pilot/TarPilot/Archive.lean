/-
  Whole-archive parsing, extraction, and writing.

  The extraction rule is the proved part, together with the path gate
  in `Path.lean`: `extractAll` only emits a path built as
  `dest ++ rel`, where `rel` passed the gate, and the theorem
  `extractAll_safe` states that every emitted relative path has no
  `..`, no empty component, no `.`, and is not empty.

  Parsing and writing are covered by differential tests against
  Python's `tarfile` module (see `tests/`), not by a proof.
-/

import TarPilot.Path
import TarPilot.Header

namespace TarPilot

/-- One archive entry as parsed: a name, a typeflag, and its data. -/
structure RawEntry where
  name : String
  typeflag : Char
  data : ByteArray

/-- Blocks of the archive, read from offset `off`. `fuel` counts down
    the blocks that can remain, which keeps the function total on
    hostile input: a size field that points past the end, or a block
    count that never reaches a full zero block, gives `none`. An
    archive that ends without its zero blocks is truncated, and a
    truncated archive is rejected whole, not read as a clean prefix. -/
def parseBlocks (data : ByteArray) (off : Nat) : Nat → Option (List RawEntry)
  | 0 => none
  | fuel + 1 =>
    if off + 512 > data.size then none
    else
      let block := data.extract off (off + 512)
      if block.toList.all (· = 0) then some []
      else match parseBlock block with
        | none => none
        | some h =>
          let dataOff := off + 512
          let padded := ((h.size + 511) / 512) * 512
          if dataOff + h.size > data.size then none
          else match parseBlocks data (dataOff + padded) fuel with
            | none => none
            | some rest =>
              some ({ name := h.name, typeflag := h.typeflag,
                      data := data.extract dataOff (dataOff + h.size) } :: rest)

/-- Parse a whole archive. -/
def parseArchive (data : ByteArray) : Option (List RawEntry) :=
  parseBlocks data 0 (data.size / 512 + 1)

/-- Regular files only: typeflag `0` or NUL. Directories, links, and
    everything else are never extracted, so a link entry cannot be used
    to place a later entry outside the destination. -/
def isRegular (e : RawEntry) : Bool :=
  e.typeflag == '0' || e.typeflag == Char.ofNat 0

/-- Extract entries into a list of `(path, data)` pairs, in memory.
    The path of each pair is the destination components followed by the
    gated relative components of the entry name. -/
def extractAll (dest : List String) (entries : List RawEntry) :
    List (List String × ByteArray) :=
  entries.filterMap fun e =>
    if isRegular e then
      (gate e.name).map fun rel => (dest ++ rel, e.data)
    else none

/-- Every path `extractAll` emits is the destination followed by a
    gated relative path: no `..`, no empty component, no `.`, and the
    relative path is not empty. So no emitted path escapes the
    destination. -/
theorem extractAll_safe : ∀ (dest : List String) (entries : List RawEntry)
    (path : List String) (bytes : ByteArray),
    (path, bytes) ∈ extractAll dest entries →
    ∃ rel, path = dest ++ rel ∧
      ".." ∉ rel ∧ "" ∉ rel ∧ "." ∉ rel ∧ rel ≠ [] := by
  intro dest entries path bytes h
  unfold extractAll at h
  rw [List.mem_filterMap] at h
  obtain ⟨e, _, hfe⟩ := h
  by_cases hreg : isRegular e
  · rw [if_pos hreg] at hfe
    cases hg : gate e.name with
    | none =>
      rw [hg] at hfe
      simp at hfe
    | some rel =>
      rw [hg] at hfe
      simp only [Option.map_some, Option.some.injEq, Prod.mk.injEq] at hfe
      obtain ⟨hpath, _⟩ := hfe
      obtain ⟨h1, h2, h3, h4⟩ := gate_sound e.name rel hg
      exact ⟨rel, hpath.symm, h1, h2, h3, h4⟩
  · rw [if_neg hreg] at hfe
    exact absurd hfe (by simp)

/-- Parse, then extract. -/
def extractArchive (dest : List String) (data : ByteArray) :
    Option (List (List String × ByteArray)) :=
  (parseArchive data).map (extractAll dest)

/-- The same guarantee for a whole archive read from bytes. -/
theorem extractArchive_safe : ∀ (dest : List String) (data : ByteArray)
    (out : List (List String × ByteArray)) (path : List String)
    (bytes : ByteArray),
    extractArchive dest data = some out → (path, bytes) ∈ out →
    ∃ rel, path = dest ++ rel ∧
      ".." ∉ rel ∧ "" ∉ rel ∧ "." ∉ rel ∧ rel ≠ [] := by
  intro dest data out path bytes h hmem
  unfold extractArchive at h
  cases hp : parseArchive data with
  | none =>
    rw [hp] at h
    simp at h
  | some entries =>
    rw [hp] at h
    simp only [Option.map_some, Option.some.injEq] at h
    subst h
    exact extractAll_safe dest entries path bytes hmem

/-- Build an archive from `(name, data)` pairs as regular files.
    Ends with two zero blocks, as the format expects. -/
def buildArchive (files : List (String × ByteArray)) : Option ByteArray :=
  let step := fun (acc : ByteArray) (f : String × ByteArray) => do
    let block ← buildBlock f.1 f.2.size '0'
    let padLen := ((f.2.size + 511) / 512) * 512 - f.2.size
    pure (acc ++ block ++ f.2 ++ ByteArray.mk (List.replicate padLen 0).toArray)
  (files.foldlM step ByteArray.empty).map
    (· ++ ByteArray.mk (List.replicate 1024 0).toArray)

end TarPilot
