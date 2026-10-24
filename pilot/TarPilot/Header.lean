/-
  The ustar header block: 512 bytes at the start of each entry.

  Layout (byte offsets): name 0 (100), mode 100 (8), uid 108 (8), gid 116 (8),
  size 124 (12), mtime 136 (12), checksum 148 (8), typeflag 156 (1),
  linkname 157 (100), magic 257 (6), version 263 (2), uname 265 (32),
  gname 297 (32), devmajor 329 (8), devminor 337 (8), prefix 345 (155),
  pad 500 (12). Total 512.

  This code is covered by the differential tests in `tests/`, not by a
  proof. The proved part of the pilot is the path gate in `Path.lean`
  and the extraction rule in `Archive.lean`.
-/

import TarPilot.Octal

namespace TarPilot

/-- A parsed header. Only the fields the pilot uses. -/
structure Header where
  name : String
  size : Nat
  typeflag : Char
  deriving Repr, DecidableEq

/-- Byte at index `i`, or 0 when out of range. -/
def byteAt (b : ByteArray) (i : Nat) : UInt8 :=
  b.toList[i]?.getD 0

/-- The bytes of `b` in `[off, off + len)`, clamped to the array. -/
def sliceList (b : ByteArray) (off len : Nat) : List UInt8 :=
  (b.extract off (off + len)).toList

/-- A name field: bytes up to the first NUL, read as UTF-8.
    Invalid UTF-8 reads as the empty string. -/
def bytesToName (bs : List UInt8) : String :=
  let raw := bs.takeWhile (fun b => b ≠ 0)
  (String.fromUTF8? (ByteArray.mk raw.toArray)).getD ""

/-- The header checksum: sum of all 512 bytes, with the checksum field
    itself (bytes 148 to 155) counted as spaces. -/
def blockChecksum (bs : List UInt8) : Nat :=
  (bs.zipIdx).foldl
    (fun acc p => acc + (if 148 ≤ p.2 ∧ p.2 < 156 then 32 else p.1.toNat)) 0

/-- Parse one 512-byte header block. Fails on a short block, a bad
    magic, a checksum mismatch, or a bad size field. -/
def parseBlock (block : ByteArray) : Option Header :=
  if block.size < 512 then none
  else do
    if sliceList block 257 5 ≠ [117, 115, 116, 97, 114] then none else
    let stored ← parseOctal (sliceList block 148 8)
    if stored ≠ blockChecksum (sliceList block 0 512) then none else
    let size ← parseOctal (sliceList block 124 12)
    let name := bytesToName (sliceList block 0 100)
    let pfx := bytesToName (sliceList block 345 155)
    let fullName := if pfx = "" then name else pfx ++ "/" ++ name
    some { name := fullName, size := size,
           typeflag := Char.ofNat (byteAt block 156).toNat }

/-- Content padded on the right with NUL bytes to width `w`,
    or cut to `w` when longer. -/
def fieldBytes (content : List UInt8) (w : Nat) : List UInt8 :=
  content.take w ++ List.replicate (w - content.length) 0

/-- Split a long name at a `/` so the part before it fits the 155-byte
    prefix field and the part after it fits the 100-byte name field.
    Short names get an empty prefix. Fails when no split works. -/
def splitUstarName (name : String) : Option (String × String) :=
  if name.toUTF8.size ≤ 100 then some ("", name)
  else
    let cs := name.splitOn "/"
    let tries := (List.range cs.length).map fun k =>
      (String.intercalate "/" (cs.take (k + 1)), String.intercalate "/" (cs.drop (k + 1)))
    tries.find? (fun p =>
      p.1.toUTF8.size ≤ 155 ∧ p.2.toUTF8.size ≤ 100 ∧ p.2 ≠ "")

/-- Build a 512-byte header block for a regular file or directory.
    Mode is fixed at 0644, uid, gid, and mtime at 0.
    Fails when the size or the name does not fit. -/
def buildBlock (name : String) (size : Nat) (typeflag : Char) : Option ByteArray := do
  let (pfx, short) ← splitUstarName name
  let sizeF ← formatOctal size 12
  let modeF ← formatOctal 0o644 8
  let zero8 ← formatOctal 0 8
  let mtimeF ← formatOctal 0 12
  let pre := fieldBytes short.toUTF8.toList 100 ++ modeF ++ zero8 ++ zero8 ++
    sizeF ++ mtimeF
  let post := [typeflag.toNat.toUInt8] ++ List.replicate 100 0 ++
    [117, 115, 116, 97, 114, 0] ++ [48, 48] ++
    List.replicate 32 0 ++ List.replicate 32 0 ++ zero8 ++ zero8 ++
    fieldBytes pfx.toUTF8.toList 155 ++ List.replicate 12 0
  let blank := pre ++ List.replicate 8 32 ++ post
  let sum := blockChecksum blank
  let ds := octalDigits sum
  if ds.length > 6 then none else
  let chk := List.replicate (6 - ds.length) 48 ++ ds ++ [0, 32]
  some (ByteArray.mk (pre ++ chk ++ post).toArray)

end TarPilot
