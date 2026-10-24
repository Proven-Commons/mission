# Pilot: a tar extractor that cannot escape its destination

This pilot reads a tar archive (ustar format) and extracts regular files into an in-memory list of paths and file contents. Every path it emits is built by joining the destination with a cleaned relative path. A machine-checked proof shows the cleaned path can never climb out of the destination.

It is the first Proven Commons project, built to the verified bar in the root README. Status: pilot complete, October 2026.

## Run it

Needs Lean 4.35.0 (install with elan, toolchain pinned in `lean-toolchain`).

```
cd pilot
lake build
.lake/build/bin/tar-pilot list <file.tar>
.lake/build/bin/tar-pilot manifest <file.tar> out
.lake/build/bin/tar-pilot create <out.tar> <file> [more files...]
```

`manifest` prints what extraction would do, in archive order, and writes nothing to disk: `OK` with the final path, size, and byte sum for an extracted file, `REJECT` for a regular file whose name fails the path gate, `SKIP` for a non-regular entry.

## What is proved

The path gate and the extraction rule, in `TarPilot/Path.lean` and `TarPilot/Archive.lean`:

- `gate_sound`: a name that passes the gate gives relative components with no `..`, no empty component, no `.`, and the list is not empty.
- `cleanComponents_sound`: the component cleaner behind the gate has the same properties.
- `extractAll_safe`: every path the extractor emits is the destination components followed by a gated relative path, so no emitted path escapes the destination.
- `extractArchive_safe`: the same guarantee for an archive read from bytes.

The gate rules: absolute names are rejected. Any `..` component is rejected. Empty and `.` components are dropped. A name with nothing left is rejected. Only regular files (typeflag `0` or NUL) are extracted. Directory, link, and other entries are skipped, so a link entry cannot place a later entry outside the destination.

Axiom check: each proof depends only on the standard Lean axioms (`propext`, `Classical.choice`, `Quot.sound`, or a subset). Full output is recorded in `tests/TEST-RESULTS.md`.

## What is not proved

Read this before trusting the pilot with real archives:

- Header parsing, octal fields, checksums, and archive writing are tested, not proved. The tests compare the Lean code against Python's `tarfile` module and against an independent copy of the extraction spec. Results are in `tests/TEST-RESULTS.md`: 16 checks, 0 failures, on 14 archive entries covering normal files, hostile names, a long name split over the ustar prefix field, and broken inputs (truncated, garbage, bad checksum).
- Extraction works on an in-memory model. Nothing here writes files to disk, so the step from a proved in-memory path to a safe write on a real filesystem (races, symlinked destination folders) is outside this pilot.
- Names that are not valid UTF-8 read as empty and are rejected by the gate. GNU tar extensions (longname entries, pax headers), base-256 size fields, and sparse files are not supported. An archive using them fails to parse instead of being read in a wrong way.
- The Lean compiler, runtime, and kernel are trusted, as in every Lean project. A bug in them is outside the proof.

## Re-check it

```
cd pilot
lake build
lake env lean TarPilot/Verify.lean
python3 tests/run_tests.py
```

The build fails if a proof breaks. The second command prints the axiom list. The test script rebuilds if needed, reruns every comparison, and rewrites `tests/TEST-RESULTS.md`.

## Layout

- `TarPilot/Path.lean`: the path gate and its proofs.
- `TarPilot/Octal.lean`: octal fields.
- `TarPilot/Header.lean`: the 512-byte ustar header, checksum, build and parse.
- `TarPilot/Archive.lean`: whole-archive parse and write, extraction, and the safety theorems.
- `TarPilot/Verify.lean`: the axiom check.
- `Main.lean`: the command line front end.
- `tests/run_tests.py`: differential tests against Python's `tarfile`.
