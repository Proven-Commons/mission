import Resp

/-!
Command line front end.

* `resp serve`: read RESP requests from standard input until it ends, answer
  them in order, and write the replies to standard output.
* `resp decode`: read one hex-encoded input per line and print, for each, the
  value the parser reads from its front as one line of JSON. The differential
  tests use this to compare the parser against hiredis.
-/

open Resp

partial def readAll (h : IO.FS.Stream) (acc : ByteArray := .empty) : IO ByteArray := do
  let chunk ← h.read 65536
  if chunk.isEmpty then return acc else readAll h (acc ++ chunk)

def hexDigit (n : Nat) : Char := "0123456789abcdef".toList[n]!

def toHex (bs : Bytes) : String :=
  String.ofList (bs.flatMap fun b => [hexDigit (b.toNat / 16), hexDigit (b.toNat % 16)])

def hexVal (c : Char) : Option Nat :=
  if '0' ≤ c ∧ c ≤ '9' then some (c.toNat - '0'.toNat)
  else if 'a' ≤ c ∧ c ≤ 'f' then some (c.toNat - 'a'.toNat + 10)
  else none

def ofHex : List Char → Option Bytes
  | [] => some []
  | a :: b :: rest => do
    let hi ← hexVal a
    let lo ← hexVal b
    let tl ← ofHex rest
    pure ((hi * 16 + lo).toUInt8 :: tl)
  | _ => none

partial def toJson : Value → String
  | .simple s => s!"[\"S\",\"{toHex s}\"]"
  | .error s => s!"[\"E\",\"{toHex s}\"]"
  | .integer i => s!"[\"I\",{i}]"
  | .bulk b => s!"[\"B\",\"{toHex b}\"]"
  | .nullBulk => "[\"NB\"]"
  | .array xs => "[\"A\",[" ++ ",".intercalate (xs.map toJson) ++ "]]"
  | .nullArray => "[\"NA\"]"

def decodeLine (line : String) : String :=
  match ofHex line.trimAscii.toString.toList with
  | none => "{\"ok\":false,\"bad_hex\":true}"
  | some bs => match decode bs with
    | some (v, rest) => s!"\{\"ok\":true,\"v\":{toJson v},\"used\":{bs.length - rest.length}}"
    | none => "{\"ok\":false}"

def main (args : List String) : IO UInt32 := do
  match args with
  | ["serve"] =>
    let input ← readAll (← IO.getStdin)
    let (_, replies, rest) := serve [] input.toList
    let out ← IO.getStdout
    for r in replies do
      out.write (ByteArray.mk (encode r).toArray)
    out.flush
    if rest.isEmpty then return 0
    else
      IO.eprintln s!"stopped: {rest.length} bytes at the end do not form a request"
      return 2
  | ["decode"] =>
    let input ← readAll (← IO.getStdin)
    let text := String.fromUTF8! input
    let out ← IO.getStdout
    for line in text.splitOn "\n" do
      if !line.trimAscii.isEmpty then
        out.putStrLn (decodeLine line)
    return 0
  | _ =>
    IO.eprintln "usage: resp serve | resp decode"
    return 1
