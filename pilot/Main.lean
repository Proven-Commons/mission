/-
  Command line front end for the tar pilot.

    tar-pilot list <file.tar>
      Print one line per entry: name, data size, typeflag code.

    tar-pilot manifest <file.tar> <dest>
      Print what extraction would do, in archive order, without
      writing anything to disk:
        OK     <dest path> <size> <byte sum>   for an extracted file
        REJECT <name>                          for a regular file whose
                                               name fails the path gate
        SKIP   <name> <typeflag code>         for a non-regular entry

    tar-pilot create <out.tar> <file> [more files...]
      Build an archive. Each entry name is the path as given.
-/

import TarPilot

open TarPilot

def byteSum (b : ByteArray) : Nat :=
  b.toList.foldl (fun a x => a + x.toNat) 0

def runList (file : String) : IO UInt32 := do
  let data ← IO.FS.readBinFile file
  match parseArchive data with
  | none =>
    IO.eprintln s!"error: cannot parse {file} as a ustar archive"
    return 1
  | some entries =>
    for e in entries do
      IO.println s!"{e.name}\t{e.data.size}\t{e.typeflag.toNat}"
    return 0

def runManifest (file dest : String) : IO UInt32 := do
  let data ← IO.FS.readBinFile file
  match parseArchive data with
  | none =>
    IO.eprintln s!"error: cannot parse {file} as a ustar archive"
    return 1
  | some entries =>
    let destCs := if dest = "" then [] else dest.splitOn "/"
    for e in entries do
      if isRegular e then
        match gate e.name with
        | none => IO.println s!"REJECT\t{e.name}"
        | some rel =>
          let path := String.intercalate "/" (destCs ++ rel)
          IO.println s!"OK\t{path}\t{e.data.size}\t{byteSum e.data}"
      else
        IO.println s!"SKIP\t{e.name}\t{e.typeflag.toNat}"
    return 0

def runCreate (out : String) (files : List String) : IO UInt32 := do
  let mut pairs : List (String × ByteArray) := []
  for f in files do
    let data ← IO.FS.readBinFile f
    pairs := pairs ++ [(f, data)]
  match buildArchive pairs with
  | none =>
    IO.eprintln "error: a name does not fit the ustar name and prefix fields"
    return 1
  | some bytes =>
    IO.FS.writeBinFile out bytes
    return 0

def usage : IO UInt32 := do
  IO.eprintln "usage: tar-pilot list <file.tar>"
  IO.eprintln "       tar-pilot manifest <file.tar> <dest>"
  IO.eprintln "       tar-pilot create <out.tar> <file> [more files...]"
  return 2

def main (args : List String) : IO UInt32 := do
  match args with
  | ["list", file] => runList file
  | ["manifest", file, dest] => runManifest file dest
  | "create" :: out :: files =>
    if files.isEmpty then usage else runCreate out files
  | _ => usage
