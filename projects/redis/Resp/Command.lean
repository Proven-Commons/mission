import Resp.RoundTrip
import Resp.Store

/-!
# Commands and the request loop

A small Redis-compatible command set over the store:
`PING`, `ECHO`, `SET key value`, `GET`, `DEL`, `EXISTS`, `APPEND`, `STRLEN`.
Replies, including error text, match Redis 7.0 byte for byte; the differential
tests check that against a real `redis-server`.

A request is a RESP array of bulk strings, as Redis clients send it. `serve`
reads requests one after another from a byte stream and returns the replies.
-/

namespace Resp

def ascii (s : String) : Bytes := s.toUTF8.toList

def upper (b : UInt8) : UInt8 := if 97 ≤ b ∧ b ≤ 122 then b - 32 else b

/-! Command names as bytes, so proofs can compute with them. -/
def cPING : Bytes := [80, 73, 78, 71]
def cECHO : Bytes := [69, 67, 72, 79]
def cSET : Bytes := [83, 69, 84]
def cGET : Bytes := [71, 69, 84]
def cDEL : Bytes := [68, 69, 76]
def cEXISTS : Bytes := [69, 88, 73, 83, 84, 83]
def cAPPEND : Bytes := [65, 80, 80, 69, 78, 68]
def cSTRLEN : Bytes := [83, 84, 82, 76, 69, 78]

/-- Command names are case-insensitive. -/
def isCmd (name cmd : Bytes) : Bool := name.map upper == cmd

def ok : Value := .simple (ascii "OK")

def arityError (cmd : String) : Value :=
  .error (ascii s!"ERR wrong number of arguments for '{cmd}' command")

/-- C string view: Redis formats names with `%s`, which stops at a NUL byte. -/
def cstr (b : Bytes) : Bytes := b.takeWhile (· ≠ 0)

/-- The argument preview in Redis's unknown command error, capped near 128 bytes. -/
def argPreview : List Bytes → Bytes → Bytes
  | [], acc => acc
  | a :: as, acc =>
    if acc.length < 128 then
      argPreview as (acc ++ [39] ++ (cstr a).take (128 - acc.length) ++ [39, 32])
    else acc

/-- Redis turns CR and LF into spaces so an error stays on one line. -/
def oneLine (b : Bytes) : Bytes := b.map fun c => if c = 13 ∨ c = 10 then 32 else c

def unknownError (name : Bytes) (args : List Bytes) : Value :=
  .error (oneLine (ascii "ERR unknown command '" ++ (cstr name).take 128 ++
    ascii "', with args beginning with: " ++ argPreview args []))

def countDel : Store → List Bytes → Store × Nat
  | s, [] => (s, 0)
  | s, k :: ks =>
    let (s', n) := countDel (s.del k) ks
    match s.get k with
    | some _ => (s', n + 1)
    | none => (s', n)

def countExists (s : Store) : List Bytes → Nat
  | [] => 0
  | k :: ks => (if (s.get k).isSome then 1 else 0) + countExists s ks

/-- Run one command: name and arguments. -/
def exec (s : Store) (name : Bytes) (args : List Bytes) : Store × Value :=
  if isCmd name cPING then
    match args with
    | [] => (s, .simple (ascii "PONG"))
    | [m] => (s, .bulk m)
    | _ => (s, arityError "ping")
  else if isCmd name cECHO then
    match args with
    | [m] => (s, .bulk m)
    | _ => (s, arityError "echo")
  else if isCmd name cSET then
    match args with
    | [k, v] => (s.set k v, ok)
    | _ :: _ :: _ => (s, .error (ascii "ERR syntax error"))
    | _ => (s, arityError "set")
  else if isCmd name cGET then
    match args with
    | [k] => match s.get k with
      | some v => (s, .bulk v)
      | none => (s, .nullBulk)
    | _ => (s, arityError "get")
  else if isCmd name cDEL then
    match args with
    | [] => (s, arityError "del")
    | ks => let (s', n) := countDel s ks; (s', .integer n)
  else if isCmd name cEXISTS then
    match args with
    | [] => (s, arityError "exists")
    | ks => (s, .integer (countExists s ks))
  else if isCmd name cAPPEND then
    match args with
    | [k, v] =>
      let nv := (s.get k).getD [] ++ v
      (s.set k nv, .integer nv.length)
    | _ => (s, arityError "append")
  else if isCmd name cSTRLEN then
    match args with
    | [k] => (s, .integer ((s.get k).getD []).length)
    | _ => (s, arityError "strlen")
  else (s, unknownError name args)

/-! ## Requests -/

def bulks : List Value → Option (List Bytes)
  | [] => some []
  | .bulk b :: xs => (bulks xs).map (b :: ·)
  | _ => none

/-- A request: one array of bulk strings. Nesting depth 2 is all a request needs. -/
def parseRequest (bs : Bytes) : Option (List Bytes × Bytes) :=
  match parseValue 2 bs with
  | some (.array xs, r) => (bulks xs).map (·, r)
  | _ => none

/-- How a client writes a request. -/
def encodeRequest (args : List Bytes) : Bytes := encode (.array (args.map .bulk))

def serveAux : Nat → Store → Bytes → List Value → Store × List Value × Bytes
  | 0, s, bs, acc => (s, acc.reverse, bs)
  | n + 1, s, bs, acc =>
    match parseRequest bs with
    | some ([], r) => serveAux n s r acc
    | some (name :: args, r) =>
      let (s', reply) := exec s name args
      serveAux n s' r (reply :: acc)
    | none => (s, acc.reverse, bs)

/-- Answer every request at the front of `bs`. Returns the final store, the
replies in order, and any bytes that do not form a request. An empty request
gets no reply, as in Redis. -/
def serve (s : Store) (bs : Bytes) : Store × List Value × Bytes :=
  serveAux (bs.length + 1) s bs []

end Resp
