import Resp.Value

/-!
# The printer and the parser are inverses

* `parseValue_encode`: parsing what the printer wrote gives the same value back,
  and leaves the bytes after it untouched (so values can be streamed back to back).
* `parseValue_sound`: whatever the parser accepts is a well-formed value, and the
  input was exactly its printed form followed by the rest. The parser accepts no
  other spelling of a value.
* `decode_encode` and `decode_sound`: the same two facts for `decode`.
-/

namespace Resp

/-! ## Lines -/

theorem readLine_append {l : List UInt8} (h : LineOk l) (rest : List UInt8) :
    readLine (l ++ 13 :: 10 :: rest) = some (l, rest) := by
  induction l with
  | nil => simp [readLine]
  | cons b l ih =>
    have hb := h b (by simp)
    have ih := ih (fun x hx => h x (by simp [hx]))
    simp only [List.cons_append]
    rw [readLine.eq_def]
    split <;> simp_all

theorem readLine_sound {bs l r : List UInt8} (h : readLine bs = some (l, r)) :
    LineOk l ∧ bs = l ++ 13 :: 10 :: r := by
  induction bs generalizing l r with
  | nil => simp [readLine] at h
  | cons b t ih =>
    rw [readLine.eq_def] at h
    split at h
    next => simp at h
    next rest heq =>
      simp only [Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl⟩ := h
      simp only [List.cons.injEq] at heq
      obtain ⟨rfl, rfl⟩ := heq
      simp [LineOk]
    next => simp at h
    next => simp at h
    next b' t' _ h13 h10 heq =>
      simp only [List.cons.injEq] at heq
      obtain ⟨rfl, rfl⟩ := heq
      split at h
      next l' r' hl =>
        simp only [Option.some.injEq, Prod.mk.injEq] at h
        obtain ⟨rfl, rfl⟩ := h
        obtain ⟨hok, rfl⟩ := ih hl
        refine ⟨?_, by simp⟩
        intro x hx
        simp only [List.mem_cons] at hx
        rcases hx with rfl | hx
        · exact ⟨h13, h10⟩
        · exact hok x hx
      next => simp at h

theorem lineOk_encNat (n : Nat) : LineOk (encNat n) := encNat_no_crlf n

/-! ## Numbers -/

theorem parseInt_encInt {i : Int} (h : IntOk i) : parseInt (encInt i) = some i := by
  unfold encInt IntOk at *
  split
  · rename_i hneg
    simp only [parseInt, parseNat_encNat]
    rw [ite_eq_left (by omega)]
    simp; omega
  · rename_i hpos
    have hhead := encNat_head i.toNat
    unfold parseInt
    split
    · rename_i t he
      exact absurd (by rw [he]; rfl) hhead
    · simp only [parseNat_encNat]
      rw [ite_eq_left (by omega)]
      simp; omega

theorem parseInt_sound {l : List UInt8} {i : Int} (h : parseInt l = some i) :
    IntOk i ∧ encInt i = l := by
  unfold parseInt at h
  split at h
  · rename_i t
    split at h
    · rename_i n hn
      split at h
      · rename_i hr
        simp only [Option.some.injEq] at h
        subst h
        refine ⟨by unfold IntOk; omega, ?_⟩
        unfold encInt
        rw [ite_eq_left (by omega)]
        simp [encNat_of_parseNat hn]
      · simp at h
    · simp at h
  · split at h
    · rename_i n hn
      split at h
      · simp only [Option.some.injEq] at h
        subst h
        refine ⟨by unfold IntOk; omega, ?_⟩
        unfold encInt
        rw [ite_eq_right (by omega)]
        simp [encNat_of_parseNat hn]
      · simp at h
    · simp at h

theorem lineOk_encInt (i : Int) : LineOk (encInt i) := by
  unfold encInt
  split
  · intro b hb
    simp only [List.mem_cons] at hb
    rcases hb with rfl | hb
    · decide
    · exact lineOk_encNat _ b hb
  · exact lineOk_encNat _

theorem parseLen_encNat (n : Nat) : parseLen (encNat n) = some (some n) := by
  unfold parseLen
  rw [ite_eq_right]
  · simp [parseNat_encNat]
  · intro h
    exact encNat_head n (by rw [h]; rfl)

theorem parseLen_null : parseLen [45, 49] = some none := by
  simp [parseLen]

theorem parseLen_sound {l : List UInt8} {o : Option Nat} (h : parseLen l = some o) :
    (o = none ∧ l = [45, 49]) ∨ (∃ n, o = some n ∧ encNat n = l) := by
  unfold parseLen at h
  split at h
  · simp_all
  · split at h
    · rename_i n hn
      simp only [Option.some.injEq] at h
      exact Or.inr ⟨n, h.symm, encNat_of_parseNat hn⟩
    · simp at h

/-! ## Bulk payloads -/

theorem takeExact_append (p rest : List UInt8) :
    takeExact p.length (p ++ rest) = some (p, rest) := by
  induction p with
  | nil => simp [takeExact]
  | cons b p ih => simp [takeExact, ih]

theorem takeExact_sound {n : Nat} {bs p r : List UInt8} (h : takeExact n bs = some (p, r)) :
    p.length = n ∧ bs = p ++ r := by
  induction n generalizing bs p r with
  | zero => simp [takeExact] at h; simp [h]
  | succ n ih =>
    cases bs with
    | nil => simp [takeExact] at h
    | cons b bs =>
      simp only [takeExact] at h
      split at h
      · rename_i p' r' hp
        simp only [Option.some.injEq, Prod.mk.injEq] at h
        obtain ⟨rfl, rfl⟩ := h
        obtain ⟨h1, rfl⟩ := ih hp
        simp [h1]
      · simp at h

theorem takeBulk_append (p rest : List UInt8) :
    takeBulk p.length (p ++ 13 :: 10 :: rest) = some (p, rest) := by
  simp [takeBulk, takeExact_append]

theorem takeBulk_sound {n : Nat} {bs p r : List UInt8} (h : takeBulk n bs = some (p, r)) :
    p.length = n ∧ bs = p ++ 13 :: 10 :: r := by
  unfold takeBulk at h
  split at h
  · rename_i p' r' hp
    simp only [Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨rfl, rfl⟩ := h
    exact takeExact_sound hp
  · simp at h

/-! ## Printer then parser -/

theorem depth_pos (v : Value) : 1 ≤ v.depth := by
  cases v <;> simp [Value.depth]

mutual
/-- Parsing what the printer wrote gives back the value and the untouched rest. -/
theorem parseValue_encode (v : Value) (fuel : Nat) (rest : List UInt8)
    (hwf : v.WF) (hd : v.depth ≤ fuel) :
    parseValue fuel (encode v ++ rest) = some (v, rest) := by
  obtain ⟨f, rfl⟩ : ∃ f, fuel = f + 1 := ⟨fuel - 1, by have := depth_pos v; omega⟩
  match v with
  | .simple s =>
    simp only [Value.WF] at hwf
    simp [encode, parseValue, readLine_append hwf]
  | .error s =>
    simp only [Value.WF] at hwf
    simp [encode, parseValue, readLine_append hwf]
  | .integer i =>
    simp only [Value.WF] at hwf
    simp [encode, parseValue, readLine_append (lineOk_encInt i), parseInt_encInt hwf]
  | .bulk b =>
    simp [encode, parseValue, readLine_append (lineOk_encNat _), parseLen_encNat,
      takeBulk_append]
  | .nullBulk =>
    simp [encode, parseValue, readLine, parseLen_null]
  | .nullArray =>
    simp [encode, parseValue, readLine, parseLen_null]
  | .array xs =>
    simp only [Value.WF] at hwf
    simp only [Value.depth] at hd
    have := parseMany_encodeList xs f rest hwf (by omega)
    simp [encode, parseValue, readLine_append (lineOk_encNat _), parseLen_encNat, this]

theorem parseMany_encodeList (xs : List Value) (fuel : Nat) (rest : List UInt8)
    (hwf : Value.WFList xs) (hd : Value.depthList xs ≤ fuel) :
    parseMany fuel xs.length (encodeList xs ++ rest) = some (xs, rest) := by
  match xs with
  | [] => simp [encodeList, parseMany]
  | x :: xs =>
    simp only [Value.WFList] at hwf
    simp only [Value.depthList] at hd
    have h1 := parseValue_encode x fuel (encodeList xs ++ rest) hwf.1 (by omega)
    have h2 := parseMany_encodeList xs fuel rest hwf.2 (by omega)
    simp [encodeList, parseMany, h1, h2]
end

/-! ## Parser then printer -/

theorem parseMany_sound_of {fuel : Nat}
    (hv : ∀ bs v rest, parseValue fuel bs = some (v, rest) → v.WF ∧ bs = encode v ++ rest) :
    ∀ n bs xs rest, parseMany fuel n bs = some (xs, rest) →
      Value.WFList xs ∧ xs.length = n ∧ bs = encodeList xs ++ rest := by
  intro n
  induction n with
  | zero =>
    intro bs xs rest h
    simp only [parseMany, Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨rfl, rfl⟩ := h
    simp [Value.WFList, encodeList]
  | succ n ih =>
    intro bs xs rest h
    simp only [parseMany] at h
    split at h
    next x r hx =>
      split at h
      next xs' r' hxs =>
        simp only [Option.some.injEq, Prod.mk.injEq] at h
        obtain ⟨rfl, rfl⟩ := h
        obtain ⟨w1, rfl⟩ := hv _ _ _ hx
        obtain ⟨w2, hl, rfl⟩ := ih _ _ _ hxs
        simp [Value.WFList, encodeList, w1, w2, hl]
      next => simp at h
    next => simp at h

theorem parseValue_sound_aux (fuel : Nat) :
    ∀ bs v rest, parseValue fuel bs = some (v, rest) → v.WF ∧ bs = encode v ++ rest := by
  induction fuel with
  | zero => intro bs v rest h; simp [parseValue] at h
  | succ f ih =>
    have hm := parseMany_sound_of ih
    intro bs v rest h
    rw [parseValue.eq_def] at h
    simp only at h
    split at h
    next t =>
      split at h
      next l r hl =>
        simp only [Option.some.injEq, Prod.mk.injEq] at h
        obtain ⟨rfl, rfl⟩ := h
        obtain ⟨hok, rfl⟩ := readLine_sound hl
        simp [Value.WF, encode, hok]
      next => simp at h
    next t =>
      split at h
      next l r hl =>
        simp only [Option.some.injEq, Prod.mk.injEq] at h
        obtain ⟨rfl, rfl⟩ := h
        obtain ⟨hok, rfl⟩ := readLine_sound hl
        simp [Value.WF, encode, hok]
      next => simp at h
    next t =>
      split at h
      next l r hl =>
        split at h
        next i hi =>
          simp only [Option.some.injEq, Prod.mk.injEq] at h
          obtain ⟨rfl, rfl⟩ := h
          obtain ⟨-, rfl⟩ := readLine_sound hl
          obtain ⟨hok, rfl⟩ := parseInt_sound hi
          simp [Value.WF, encode, hok]
        next => simp at h
      next => simp at h
    next t =>
      split at h
      next l r hl =>
        obtain ⟨-, rfl⟩ := readLine_sound hl
        split at h
        next hn =>
          simp only [Option.some.injEq, Prod.mk.injEq] at h
          obtain ⟨rfl, rfl⟩ := h
          rcases parseLen_sound hn with ⟨-, rfl⟩ | ⟨n, hn', -⟩
          · simp [Value.WF, encode]
          · simp at hn'
        next n hn =>
          split at h
          next b r' hb =>
            simp only [Option.some.injEq, Prod.mk.injEq] at h
            obtain ⟨rfl, rfl⟩ := h
            rcases parseLen_sound hn with ⟨hn', -⟩ | ⟨m, hm', rfl⟩
            · simp at hn'
            · simp only [Option.some.injEq] at hm'
              subst hm'
              obtain ⟨hlen, rfl⟩ := takeBulk_sound hb
              simp [Value.WF, encode, hlen]
          next => simp at h
        next => simp at h
      next => simp at h
    next t =>
      split at h
      next l r hl =>
        obtain ⟨-, rfl⟩ := readLine_sound hl
        split at h
        next hn =>
          simp only [Option.some.injEq, Prod.mk.injEq] at h
          obtain ⟨rfl, rfl⟩ := h
          rcases parseLen_sound hn with ⟨-, rfl⟩ | ⟨n, hn', -⟩
          · simp [Value.WF, encode]
          · simp at hn'
        next n hn =>
          split at h
          next xs r' hxs =>
            simp only [Option.some.injEq, Prod.mk.injEq] at h
            obtain ⟨rfl, rfl⟩ := h
            rcases parseLen_sound hn with ⟨hn', -⟩ | ⟨m, hm', rfl⟩
            · simp at hn'
            · simp only [Option.some.injEq] at hm'
              subst hm'
              obtain ⟨hwf, hlen, rfl⟩ := hm _ _ _ _ hxs
              simp [Value.WF, encode, hwf, hlen]
          next => simp at h
        next => simp at h
      next => simp at h
    next => simp at h

/-- Whatever the parser accepts is a well-formed value, and the input was exactly
its printed form followed by the rest. -/
theorem parseValue_sound {fuel : Nat} {bs rest : List UInt8} {v : Value}
    (h : parseValue fuel bs = some (v, rest)) : v.WF ∧ bs = encode v ++ rest :=
  parseValue_sound_aux fuel bs v rest h

/-! ## `decode` -/

mutual
theorem depth_le_length (v : Value) : v.depth ≤ (encode v).length := by
  match v with
  | .array xs =>
    have := depthList_le_length xs
    simp [Value.depth, encode]
    omega
  | .simple _ | .error _ | .integer _ | .bulk _ | .nullBulk | .nullArray =>
    simp [Value.depth, encode]

theorem depthList_le_length (xs : List Value) : Value.depthList xs ≤ (encodeList xs).length := by
  match xs with
  | [] => simp [Value.depthList]
  | x :: xs =>
    have := depth_le_length x
    have := depthList_le_length xs
    simp [Value.depthList, encodeList]
    omega
end

/-- **Round trip.** Decoding the printed form of a well-formed value gives the
value back, whatever bytes follow it. -/
theorem decode_encode (v : Value) (rest : List UInt8) (hwf : v.WF) :
    decode (encode v ++ rest) = some (v, rest) := by
  unfold decode
  apply parseValue_encode v _ rest hwf
  have := depth_le_length v
  simp
  omega

/-- **Exactness.** `decode` accepts only printed forms of well-formed values. -/
theorem decode_sound {bs rest : List UInt8} {v : Value}
    (h : decode bs = some (v, rest)) : v.WF ∧ bs = encode v ++ rest :=
  parseValue_sound h

/-- The printer never writes the same bytes for two different values. -/
theorem encode_injective {v w : Value} (hv : v.WF) (hw : w.WF)
    (h : encode v = encode w) : v = w := by
  have h1 := decode_encode v [] hv
  have h2 := decode_encode w [] hw
  rw [h] at h1
  rw [h1] at h2
  simpa using h2

/-- The parser only consumes input; the rest is a suffix of what it was given. -/
theorem decode_suffix {bs rest : List UInt8} {v : Value}
    (h : decode bs = some (v, rest)) : rest <:+ bs :=
  ⟨encode v, (decode_sound h).2.symm⟩

end Resp
