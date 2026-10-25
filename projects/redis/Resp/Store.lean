/-!
# The key-value store

A store is a list of key and value pairs with no repeated key. It is slow on
large data and easy to reason about; the laws below are what the command layer
relies on.
-/

namespace Resp

abbrev Bytes := List UInt8

abbrev Store := List (Bytes × Bytes)

namespace Store

def get : Store → Bytes → Option Bytes
  | [], _ => none
  | (k', v) :: s, k => if k' = k then some v else get s k

def del : Store → Bytes → Store
  | [], _ => []
  | (k', v) :: s, k => if k' = k then del s k else (k', v) :: del s k

def set (s : Store) (k v : Bytes) : Store := (k, v) :: del s k

/-- Keys appear at most once. -/
def Keys (s : Store) : List Bytes := s.map (·.1)

@[simp] theorem get_set_self (s : Store) (k v : Bytes) : get (set s k v) k = some v := by
  simp [set, get]

theorem get_del_self (s : Store) (k : Bytes) : get (del s k) k = none := by
  induction s with
  | nil => rfl
  | cons p s ih =>
    obtain ⟨k', v⟩ := p
    simp only [del]
    split
    · exact ih
    · simp [get, *]

theorem get_del_other (s : Store) {k k' : Bytes} (h : k' ≠ k) :
    get (del s k) k' = get s k' := by
  induction s with
  | nil => rfl
  | cons p s ih =>
    obtain ⟨k'', v⟩ := p
    simp only [del]
    split
    · rename_i he
      subst he
      simp [get, ih, Ne.symm h]
    · simp [get, ih]

theorem get_set_other (s : Store) {k k' : Bytes} (v : Bytes) (h : k' ≠ k) :
    get (set s k v) k' = get s k' := by
  simp [set, get, Ne.symm h, get_del_other s h]

theorem del_sublist (s : Store) (k : Bytes) : (del s k).Sublist s := by
  induction s with
  | nil => simp [del]
  | cons p s ih =>
    obtain ⟨k', v⟩ := p
    simp only [del]
    split
    · exact ih.cons _
    · exact ih.cons_cons _

theorem keys_del_nodup {s : Store} (h : (Keys s).Nodup) (k : Bytes) : (Keys (del s k)).Nodup := by
  induction s with
  | nil => simp [del, Keys]
  | cons p s ih =>
    obtain ⟨k', v⟩ := p
    simp only [Keys, List.map_cons, List.nodup_cons] at h
    simp only [del]
    split
    · exact ih h.2
    · simp only [Keys, List.map_cons, List.nodup_cons]
      refine ⟨?_, ih h.2⟩
      intro hm
      exact h.1 (((del_sublist s k).map (·.1)).subset hm)

/-- `set` keeps every key unique. -/
theorem keys_set_nodup {s : Store} (h : (Keys s).Nodup) (k v : Bytes) :
    (Keys (set s k v)).Nodup := by
  simp only [set, Keys, List.map_cons, List.nodup_cons]
  refine ⟨?_, keys_del_nodup h k⟩
  intro hm
  have := get_del_self s k
  have : ∀ (t : Store), k ∈ t.map (·.1) → (get t k).isSome := by
    intro t
    induction t with
    | nil => simp
    | cons q t iht =>
      obtain ⟨kq, vq⟩ := q
      simp only [List.map_cons, List.mem_cons]
      intro hq
      simp only [get]
      split
      · rfl
      · rcases hq with rfl | hq
        · simp_all
        · exact iht hq
  have := this _ hm
  simp_all

end Store
end Resp
