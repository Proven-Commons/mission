import Resp.Command

/-!
# What the server guarantees

Command level, for any store and any spelling of the command name that Redis
would accept (names are case-insensitive):

* `get_after_set`: a `GET` after `SET k v` returns `v`.
* `get_after_set_other`: a `SET` leaves every other key's `GET` reply unchanged.
* `get_after_del`: a `GET` after `DEL k` returns the null bulk string.

Wire level:

* `parseRequest_encodeRequest`: the server reads back exactly the request a
  client printed, whatever follows it.
* `serve_encodeAll`: on a byte stream of printed requests, the server answers
  each request in order, exactly as running the commands one by one would, and
  leaves no bytes unread.
* `wire_set_get` and `wire_del_get`: the two headline facts above, end to end
  through the parser, the store, and the printer.
-/

namespace Resp

theorem isCmd_iff {name cmd : Bytes} : isCmd name cmd = true ↔ name.map upper = cmd := by
  simp [isCmd]

/-- A name cannot be two different commands. -/
theorem isCmd_false {name c d : Bytes} (h : isCmd name c = true) (hne : c ≠ d) :
    isCmd name d = false := by
  rw [isCmd_iff] at h
  simp only [isCmd, beq_eq_false_iff_ne, ne_eq]
  rw [h]; exact hne

theorem exec_set {s : Store} {name k v : Bytes} (h : isCmd name cSET = true) :
    exec s name [k, v] = (s.set k v, ok) := by
  unfold exec
  simp [h, isCmd_false h (by decide : cSET ≠ cPING), isCmd_false h (by decide : cSET ≠ cECHO)]

theorem exec_get {s : Store} {name k : Bytes} (h : isCmd name cGET = true) :
    exec s name [k] = (s, match s.get k with | some v => .bulk v | none => .nullBulk) := by
  unfold exec
  simp only [h, isCmd_false h (by decide : cGET ≠ cPING), isCmd_false h (by decide : cGET ≠ cECHO),
    isCmd_false h (by decide : cGET ≠ cSET), Bool.false_eq_true, ite_false, ite_true]
  split <;> simp_all

theorem exec_del_one {s : Store} {name k : Bytes} (h : isCmd name cDEL = true) :
    (exec s name [k]).1 = s.del k := by
  unfold exec
  simp only [h, isCmd_false h (by decide : cDEL ≠ cPING), isCmd_false h (by decide : cDEL ≠ cECHO),
    isCmd_false h (by decide : cDEL ≠ cSET), isCmd_false h (by decide : cDEL ≠ cGET),
    Bool.false_eq_true, ite_false, ite_true]
  simp only [countDel]
  split <;> rfl

/-- A `GET` after `SET k v` returns `v`. -/
theorem get_after_set (s : Store) {set get : Bytes} (k v : Bytes)
    (hs : isCmd set cSET = true) (hg : isCmd get cGET = true) :
    (exec (exec s set [k, v]).1 get [k]).2 = .bulk v := by
  rw [exec_set hs, exec_get hg]
  simp

/-- `SET` on one key leaves the reply for any other key unchanged. -/
theorem get_after_set_other (s : Store) {set get : Bytes} {k k' : Bytes} (v : Bytes)
    (hs : isCmd set cSET = true) (hg : isCmd get cGET = true) (hk : k' ≠ k) :
    (exec (exec s set [k, v]).1 get [k']).2 = (exec s get [k']).2 := by
  rw [exec_set hs, exec_get hg, exec_get hg]
  simp [Store.get_set_other s v hk]

/-- A `GET` after `DEL k` returns the null bulk string. -/
theorem get_after_del (s : Store) {del get : Bytes} (k : Bytes)
    (hd : isCmd del cDEL = true) (hg : isCmd get cGET = true) :
    (exec (exec s del [k]).1 get [k]).2 = .nullBulk := by
  rw [exec_del_one hd, exec_get hg]
  simp [Store.get_del_self]

/-! ## Wire level -/

theorem bulks_map (args : List Bytes) : bulks (args.map .bulk) = some args := by
  induction args with
  | nil => rfl
  | cons a as ih => simp [bulks, ih]

theorem wf_request (args : List Bytes) : (Value.array (args.map .bulk)).WF := by
  simp only [Value.WF]
  induction args with
  | nil => simp [Value.WFList]
  | cons a as ih => simp [Value.WFList, Value.WF, ih]

theorem depth_request (args : List Bytes) : (Value.array (args.map .bulk)).depth ≤ 2 := by
  simp only [Value.depth]
  suffices Value.depthList (args.map .bulk) ≤ 1 by omega
  induction args with
  | nil => simp [Value.depthList]
  | cons a as ih => simp [Value.depthList, Value.depth, ih]

theorem parseRequest_encodeRequest (args : List Bytes) (rest : Bytes) :
    parseRequest (encodeRequest args ++ rest) = some (args, rest) := by
  unfold parseRequest encodeRequest
  rw [parseValue_encode _ 2 rest (wf_request args) (depth_request args)]
  simp [bulks_map]

/-- Run commands one by one. -/
def runAll : Store → List (Bytes × List Bytes) → List Value → Store × List Value
  | s, [], acc => (s, acc.reverse)
  | s, (name, args) :: rs, acc => runAll (exec s name args).1 rs ((exec s name args).2 :: acc)

/-- Commands printed back to back as a client would send them. -/
def encodeAll (rs : List (Bytes × List Bytes)) : Bytes :=
  (rs.map fun r => encodeRequest (r.1 :: r.2)).flatten

theorem parseRequest_nil : parseRequest [] = none := by
  simp [parseRequest, parseValue]

theorem serveAux_encodeAll (rs : List (Bytes × List Bytes)) (s : Store) (acc : List Value)
    (n : Nat) (hn : rs.length < n) :
    serveAux n s (encodeAll rs) acc = ((runAll s rs acc).1, (runAll s rs acc).2, []) := by
  induction rs generalizing s acc n with
  | nil =>
    obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := ⟨n - 1, by simp at hn; omega⟩
    simp [serveAux, encodeAll, runAll, parseRequest_nil]
  | cons r rs ih =>
    obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := ⟨n - 1, by simp at hn; omega⟩
    obtain ⟨name, args⟩ := r
    have he : encodeAll ((name, args) :: rs) = encodeRequest (name :: args) ++ encodeAll rs := by
      simp [encodeAll]
    rw [he, serveAux, parseRequest_encodeRequest]
    simp only
    rw [ih _ _ _ (by simp at hn; omega)]
    simp [runAll]

theorem length_le_encodeAll (rs : List (Bytes × List Bytes)) : rs.length ≤ (encodeAll rs).length := by
  induction rs with
  | nil => simp
  | cons r rs ih =>
    have : 1 ≤ (encodeRequest (r.1 :: r.2)).length := by simp [encodeRequest, encode]
    simp only [encodeAll, List.map_cons, List.flatten_cons, List.length_append, List.length_cons] at *
    omega

/-- **The server over the wire.** Given printed requests, `serve` answers each
one in order exactly as running the commands one by one would, and reads every
byte. -/
theorem serve_encodeAll (s : Store) (rs : List (Bytes × List Bytes)) :
    serve s (encodeAll rs) = ((runAll s rs []).1, (runAll s rs []).2, []) := by
  unfold serve
  apply serveAux_encodeAll
  have := length_le_encodeAll rs
  omega

/-- End to end: `SET k v` then `GET k`, sent as bytes, get `+OK` and then `v`. -/
theorem wire_set_get (s : Store) (k v : Bytes) :
    (serve s (encodeAll [(cSET, [k, v]), (cGET, [k])])).2.1 = [ok, .bulk v] := by
  rw [serve_encodeAll]
  have hs : isCmd cSET cSET = true := by decide
  have hg : isCmd cGET cGET = true := by decide
  simp [runAll, exec_set hs, exec_get hg]

/-- End to end: `GET k` after `DEL k` gets the null bulk string `$-1`. -/
theorem wire_del_get (s : Store) (k : Bytes) :
    (serve s (encodeAll [(cDEL, [k]), (cGET, [k])])).2.1.getLast? = some .nullBulk := by
  rw [serve_encodeAll]
  have hd : isCmd cDEL cDEL = true := by decide
  have hg : isCmd cGET cGET = true := by decide
  simp [runAll, exec_get hg, exec_del_one hd, Store.get_del_self]

end Resp
