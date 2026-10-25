/-!
# Decimal numbers on the wire

RESP writes lengths and integers in base 10. The parser accepts only the
canonical form: digits `0`-`9`, no sign on a natural number, and no leading
zero except for the number zero itself. That makes printing and parsing exact
inverses (`parseNat_encNat` and `encNat_of_parseNat`).

Digits are handled least significant first (`encRev`, `valRev`); the wire form
is the reverse.
-/

namespace Resp

/-- The ASCII byte for a digit value below 10. -/
def digit (d : Nat) : UInt8 := (48 + d).toUInt8

def isDigit (b : UInt8) : Bool := 48 ≤ b && b ≤ 57

/-- Digits of `n`, least significant first. -/
def encRev (n : Nat) : List UInt8 :=
  if n < 10 then [digit n] else digit (n % 10) :: encRev (n / 10)
termination_by n
decreasing_by omega

/-- Value of a digit list, least significant first. -/
def valRev : List UInt8 → Nat
  | [] => 0
  | d :: ds => (d.toNat - 48) + 10 * valRev ds

/-- Canonical decimal form of a natural number. -/
def encNat (n : Nat) : List UInt8 := (encRev n).reverse

/-- Parse a whole field as a canonical natural number. -/
def parseNat (l : List UInt8) : Option Nat :=
  if l ≠ [] ∧ l.all isDigit = true ∧ (l.head? ≠ some 48 ∨ l = [48]) then
    some (valRev l.reverse)
  else none

theorem digit_toNat {d : Nat} (h : d < 10) : (digit d).toNat = 48 + d := by
  simp [digit, Nat.toUInt8, UInt8.toNat_ofNat]
  omega

theorem isDigit_digit {d : Nat} (h : d < 10) : isDigit (digit d) = true := by
  simp only [isDigit, Bool.and_eq_true, decide_eq_true_eq, UInt8.le_iff_toNat_le,
    digit_toNat h]
  simp
  omega

theorem encRev_ne_nil (n : Nat) : encRev n ≠ [] := by
  rw [encRev]; split <;> simp

theorem encRev_all_digit (n : Nat) : ∀ b ∈ encRev n, isDigit b = true := by
  induction n using Nat.strongRecOn with
  | _ n ih =>
    rw [encRev]
    split
    · simp [isDigit_digit (by assumption)]
    · intro b hb
      simp only [List.mem_cons] at hb
      rcases hb with rfl | hb
      · exact isDigit_digit (Nat.mod_lt _ (by omega))
      · exact ih (n / 10) (by omega) b hb

theorem valRev_encRev (n : Nat) : valRev (encRev n) = n := by
  induction n using Nat.strongRecOn with
  | _ n ih =>
    rw [encRev]
    split
    · simp [valRev, digit_toNat (by assumption : n < 10)]
    · simp only [valRev, digit_toNat (Nat.mod_lt n (by omega : 10 > 0)), ih (n / 10) (by omega)]
      omega

/-- The most significant digit of `encRev n` is `0` only when `n = 0`. -/
theorem encRev_last (n : Nat) : (encRev n).getLast? ≠ some 48 ∨ encRev n = [48] := by
  induction n using Nat.strongRecOn with
  | _ n ih =>
    rw [encRev]
    split
    · rename_i h
      by_cases h0 : n = 0
      · subst h0; right; rfl
      · left
        simp only [List.getLast?_singleton, ne_eq, Option.some.injEq]
        intro he
        have := congrArg UInt8.toNat he
        rw [digit_toNat h] at this
        simp at this
        omega
    · rename_i h
      left
      have hne := encRev_ne_nil (n / 10)
      rw [List.getLast?_cons, List.getLast?_eq_some_getLast hne]
      simp only [Option.getD_some]
      rcases ih (n / 10) (by omega) with h1 | h1
      · rwa [List.getLast?_eq_some_getLast hne] at h1
      · -- `n / 10 = 0` would put `n` below 10
        have := congrArg valRev h1
        rw [valRev_encRev] at this
        simp [valRev] at this
        omega

theorem isDigit_toNat {b : UInt8} (h : isDigit b = true) : 48 ≤ b.toNat ∧ b.toNat ≤ 57 := by
  simp only [isDigit, Bool.and_eq_true, decide_eq_true_eq, UInt8.le_iff_toNat_le] at h
  simpa using h

theorem digit_sub {b : UInt8} (h : isDigit b = true) : digit (b.toNat - 48) = b := by
  have := isDigit_toNat h
  apply UInt8.toNat_inj.mp
  rw [digit_toNat (by omega)]
  omega

/-- A digit list whose top digit is not `0` has a positive value. -/
theorem valRev_pos : ∀ (ds : List UInt8), ds ≠ [] → (∀ b ∈ ds, isDigit b = true) →
    ds.getLast? ≠ some 48 → 0 < valRev ds
  | [], h, _, _ => absurd rfl h
  | [d], _, hd, hl => by
    have := isDigit_toNat (hd d (by simp))
    simp only [List.getLast?_singleton, ne_eq, Option.some.injEq] at hl
    have : d.toNat ≠ 48 := fun h => hl (UInt8.toNat_inj.mp (by simpa using h))
    simp [valRev]; omega
  | d :: e :: ds, _, hd, hl => by
    have := valRev_pos (e :: ds) (by simp) (fun b hb => hd b (List.mem_cons_of_mem _ hb))
      (by rwa [List.getLast?_cons_cons] at hl)
    simp only [valRev] at this ⊢
    omega

/-- Canonical digit lists are exactly the images of `encRev`. -/
theorem encRev_valRev : ∀ (ds : List UInt8), ds ≠ [] → (∀ b ∈ ds, isDigit b = true) →
    (ds.getLast? ≠ some 48 ∨ ds = [48]) → encRev (valRev ds) = ds
  | [], h, _, _ => absurd rfl h
  | [d], _, hd, _ => by
    have h := isDigit_toNat (hd d (by simp))
    rw [encRev, ite_eq_left (by simp [valRev]; omega)]
    simp [valRev, digit_sub (hd d (by simp))]
  | d :: e :: ds, _, hd, hl => by
    have hd' : ∀ b ∈ e :: ds, isDigit b = true := fun b hb => hd b (List.mem_cons_of_mem _ hb)
    have hl' : (e :: ds).getLast? ≠ some 48 := by
      rcases hl with hl | hl
      · rwa [List.getLast?_cons_cons] at hl
      · simp at hl
    have hpos := valRev_pos (e :: ds) (by simp) hd' hl'
    have hdig := isDigit_toNat (hd d (by simp))
    have ih := encRev_valRev (e :: ds) (by simp) hd' (Or.inl hl')
    generalize hm : valRev (e :: ds) = m at hpos ih
    have hv : valRev (d :: e :: ds) = (d.toNat - 48) + 10 * m := by
      simp only [valRev] at hm ⊢; rw [hm]
    rw [hv, encRev, ite_eq_right (by omega)]
    have h1 : ((d.toNat - 48) + 10 * m) % 10 = d.toNat - 48 := by omega
    have h2 : ((d.toNat - 48) + 10 * m) / 10 = m := by omega
    rw [h1, h2, ih, digit_sub (hd d (by simp))]

theorem parseNat_encNat (n : Nat) : parseNat (encNat n) = some n := by
  unfold parseNat encNat
  rw [ite_eq_left]
  · simp [valRev_encRev]
  · refine ⟨by simpa using encRev_ne_nil n, ?_, ?_⟩
    · simpa using encRev_all_digit n
    · rw [List.head?_reverse]
      rcases encRev_last n with h | h
      · exact Or.inl h
      · right; rw [h]; rfl

theorem encNat_of_parseNat {l : List UInt8} {n : Nat} (h : parseNat l = some n) :
    encNat n = l := by
  unfold parseNat at h
  split at h
  · rename_i hc
    obtain ⟨hne, hall, hhead⟩ := hc
    simp only [Option.some.injEq] at h
    subst h
    unfold encNat
    rw [encRev_valRev]
    · simp
    · simpa using hne
    · simpa using hall
    · rcases hhead with h | h
      · left; rwa [List.getLast?_reverse]
      · right; subst h; rfl
  · simp at h

theorem encNat_ne_nil (n : Nat) : encNat n ≠ [] := by
  simp [encNat, encRev_ne_nil]

theorem encNat_no_crlf (n : Nat) : ∀ b ∈ encNat n, b ≠ 13 ∧ b ≠ 10 := by
  intro b hb
  have := isDigit_toNat (encRev_all_digit n b (by simpa [encNat] using hb))
  constructor <;> intro h <;> subst h <;> simp at this

theorem encNat_head (n : Nat) : (encNat n).head? ≠ some 45 := by
  intro h
  have hm := List.mem_of_mem_head? h
  have := isDigit_toNat (encRev_all_digit n 45 (by simpa [encNat] using hm))
  simp at this

end Resp
