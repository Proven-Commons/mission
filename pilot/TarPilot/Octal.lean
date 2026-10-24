/-
  Octal numbers as used in tar header fields.

  A numeric field holds octal digits, usually zero padded, and ends with
  a NUL or a space. Blank fields read as zero. This code is covered by
  the differential tests in `tests/`, not by a proof.
-/

namespace TarPilot

/-- Strip leading and trailing spaces and NUL bytes. -/
def trimField (bs : List UInt8) : List UInt8 :=
  let noLead := bs.dropWhile (fun b => b = 32)
  (noLead.reverse.dropWhile (fun b => b = 0 ∨ b = 32)).reverse

/-- Parse an octal field. Fails on any byte that is not an octal digit
    after trimming. An empty field parses as 0. -/
def parseOctal (bs : List UInt8) : Option Nat :=
  let digits := trimField bs
  digits.foldl (fun acc b =>
    match acc with
    | none => none
    | some n =>
      if 48 ≤ b.toNat ∧ b.toNat ≤ 55 then some (n * 8 + (b.toNat - 48))
      else none) (some 0)

/-- Octal digit bytes of `n`, most significant first. Zero gives `['0']`. -/
def octalDigits (n : Nat) : List UInt8 :=
  match Nat.toDigits 8 n with
  | [] => [48]
  | ds => ds.map (fun c => c.toNat.toUInt8)

/-- Format `n` as a tar numeric field of width `w`: octal digits zero
    padded on the left to `w - 1` bytes, then one space.
    Returns `none` if the digits do not fit. -/
def formatOctal (n w : Nat) : Option (List UInt8) :=
  let ds := octalDigits n
  if ds.length + 1 ≤ w then
    some (List.replicate (w - 1 - ds.length) 48 ++ ds ++ [32])
  else none

end TarPilot
