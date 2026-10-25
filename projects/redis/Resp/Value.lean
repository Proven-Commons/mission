import Resp.Decimal

/-!
# RESP2 values, the printer, and the parser

The wire format is RESP2, the Redis serialization protocol
(https://redis.io/docs/latest/develop/reference/protocol-spec/):

* `+<line>\r\n` simple string, `-<line>\r\n` error
* `:<integer>\r\n` signed 64-bit integer
* `$<len>\r\n<bytes>\r\n` bulk string, `$-1\r\n` null bulk string
* `*<count>\r\n<values>` array, `*-1\r\n` null array

The parser is total and strict: it returns `none` instead of crashing, and it
accepts only what the printer could have written. `Resp.RoundTrip` proves both
directions.
-/

namespace Resp

inductive Value where
  | simple (s : List UInt8)
  | error (s : List UInt8)
  | integer (i : Int)
  | bulk (b : List UInt8)
  | nullBulk
  | array (xs : List Value)
  | nullArray
  deriving Repr, Inhabited, BEq

/-- A simple string or error line holds no CR and no LF. -/
def LineOk (s : List UInt8) : Prop := ∀ b ∈ s, b ≠ 13 ∧ b ≠ 10

/-- RESP integers are signed 64-bit. -/
def IntOk (i : Int) : Prop := -2^63 ≤ i ∧ i < 2^63

mutual
/-- The values the protocol can carry. -/
def Value.WF : Value → Prop
  | .simple s => LineOk s
  | .error s => LineOk s
  | .integer i => IntOk i
  | .bulk _ => True
  | .nullBulk => True
  | .array xs => Value.WFList xs
  | .nullArray => True

def Value.WFList : List Value → Prop
  | [] => True
  | x :: xs => x.WF ∧ Value.WFList xs
end

mutual
/-- Nesting depth; the parser needs at least this much fuel. -/
def Value.depth : Value → Nat
  | .array xs => Value.depthList xs + 1
  | _ => 1

def Value.depthList : List Value → Nat
  | [] => 0
  | x :: xs => max x.depth (Value.depthList xs)
end

/-! ## Printer -/

def encInt (i : Int) : List UInt8 :=
  if i < 0 then 45 :: encNat i.natAbs else encNat i.toNat

mutual
def encode : Value → List UInt8
  | .simple s => 43 :: (s ++ [13, 10])
  | .error s => 45 :: (s ++ [13, 10])
  | .integer i => 58 :: (encInt i ++ [13, 10])
  | .bulk b => 36 :: (encNat b.length ++ 13 :: 10 :: (b ++ [13, 10]))
  | .nullBulk => [36, 45, 49, 13, 10]
  | .array xs => 42 :: (encNat xs.length ++ 13 :: 10 :: encodeList xs)
  | .nullArray => [42, 45, 49, 13, 10]

def encodeList : List Value → List UInt8
  | [] => []
  | x :: xs => encode x ++ encodeList xs
end

/-! ## Parser -/

/-- Split off one line ending in CR LF. A bare CR or LF before that is an error. -/
def readLine : List UInt8 → Option (List UInt8 × List UInt8)
  | [] => none
  | 13 :: 10 :: rest => some ([], rest)
  | 13 :: _ => none
  | 10 :: _ => none
  | b :: t => match readLine t with
    | some (l, r) => some (b :: l, r)
    | none => none

/-- A canonical signed 64-bit integer: no `+`, no `-0`, no leading zero. -/
def parseInt (l : List UInt8) : Option Int :=
  match l with
  | 45 :: t => match parseNat t with
    | some n => if 0 < n ∧ n ≤ 2^63 then some (-(n : Int)) else none
    | none => none
  | _ => match parseNat l with
    | some n => if n < 2^63 then some (n : Int) else none
    | none => none

/-- A bulk or array length: `-1` means null, otherwise a canonical natural number. -/
def parseLen (l : List UInt8) : Option (Option Nat) :=
  if l = [45, 49] then some none
  else match parseNat l with
    | some n => some (some n)
    | none => none

/-- Take exactly `n` bytes; `none` if the input is shorter. -/
def takeExact : Nat → List UInt8 → Option (List UInt8 × List UInt8)
  | 0, bs => some ([], bs)
  | _ + 1, [] => none
  | n + 1, b :: bs => match takeExact n bs with
    | some (p, r) => some (b :: p, r)
    | none => none

/-- The payload of a bulk string and its closing CR LF. -/
def takeBulk (n : Nat) (bs : List UInt8) : Option (List UInt8 × List UInt8) :=
  match takeExact n bs with
  | some (p, 13 :: 10 :: r) => some (p, r)
  | _ => none

mutual
/-- Parse one value from the front of the input and return the rest.
`fuel` bounds the nesting depth. -/
def parseValue : Nat → List UInt8 → Option (Value × List UInt8)
  | 0, _ => none
  | fuel + 1, bs => match bs with
    | 43 :: t => match readLine t with
      | some (l, r) => some (.simple l, r)
      | none => none
    | 45 :: t => match readLine t with
      | some (l, r) => some (.error l, r)
      | none => none
    | 58 :: t => match readLine t with
      | some (l, r) => match parseInt l with
        | some i => some (.integer i, r)
        | none => none
      | none => none
    | 36 :: t => match readLine t with
      | some (l, r) => match parseLen l with
        | some none => some (.nullBulk, r)
        | some (some n) => match takeBulk n r with
          | some (b, r') => some (.bulk b, r')
          | none => none
        | none => none
      | none => none
    | 42 :: t => match readLine t with
      | some (l, r) => match parseLen l with
        | some none => some (.nullArray, r)
        | some (some n) => match parseMany fuel n r with
          | some (xs, r') => some (.array xs, r')
          | none => none
        | none => none
      | none => none
    | _ => none
termination_by fuel _ => (fuel, 0)

/-- Parse `n` values in a row. -/
def parseMany (fuel : Nat) : Nat → List UInt8 → Option (List Value × List UInt8)
  | 0, bs => some ([], bs)
  | n + 1, bs => match parseValue fuel bs with
    | some (x, r) => match parseMany fuel n r with
      | some (xs, r') => some (x :: xs, r')
      | none => none
    | none => none
termination_by n _ => (fuel, n + 1)
end

/-- Parse one value from the front of a byte stream. -/
def decode (bs : List UInt8) : Option (Value × List UInt8) :=
  parseValue (bs.length + 1) bs

end Resp
