/-
  Command line front end, used by the differential tests.
  Reads lines of three numbers `lo hi x` and prints `clamp lo hi x`
  for each. It calls the proved function, not a copy of it.
-/

import Clamp

def main : IO Unit := do
  let stdin ← IO.getStdin
  let stdout ← IO.getStdout
  repeat
    let line ← stdin.getLine
    if line.isEmpty then break
    match (line.trimAscii.toString.splitOn " ").map String.toNat? with
    | [some lo, some hi, some x] => stdout.putStrLn s!"{Clamp.clamp lo hi x}"
    | _ => stdout.putStrLn "error"
