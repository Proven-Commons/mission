#!/usr/bin/env python3
"""Differential tests for the Proven Commons tar pilot.

Compares the Lean implementation against Python's `tarfile` module and
against an independent implementation of the extraction spec written
below. Run from anywhere:

    python3 tests/run_tests.py

It builds the Lean project if the executable is missing, runs all
cases in a temporary directory, writes `tests/TEST-RESULTS.md`, and
exits non-zero if any case fails.
"""

import io
import os
import random
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PILOT_DIR = Path(__file__).resolve().parent.parent
EXE = PILOT_DIR / ".lake" / "build" / "bin" / "tar-pilot"
RESULTS = PILOT_DIR / "tests" / "TEST-RESULTS.md"

checks = 0
failures = []


def check(name, ok, detail=""):
    global checks
    checks += 1
    if not ok:
        failures.append(f"{name}: {detail}")
        print(f"FAIL {name}: {detail}")


def run_lean(*args, cwd=None):
    return subprocess.run([str(EXE), *args], capture_output=True, text=True, cwd=cwd)


def spec_gate(name):
    """The extraction spec, implemented independently of the Lean code.

    Returns the cleaned relative components, or None to reject.
    Absolute names are rejected. Any `..` is rejected. Empty and `.`
    components are dropped. An empty result is rejected.
    """
    if name.startswith("/"):
        return None
    out = []
    for comp in name.split("/"):
        if comp == "..":
            return None
        if comp in ("", "."):
            continue
        out.append(comp)
    return out if out else None


def is_regular(ti):
    return ti.isreg()


def build_archive_a(path):
    """Archive with normal, hostile, and edge-case entries, built with
    Python's tarfile as the reference implementation."""
    rng = random.Random(42)
    entries = [
        ("hello.txt", b"hello world", tarfile.REGTYPE),
        ("dir/nested.bin", bytes(range(256)) * 3, tarfile.REGTYPE),
        ("empty.txt", b"", tarfile.REGTYPE),
        ("big.bin", rng.randbytes(5000), tarfile.REGTYPE),
        ("dir", b"", tarfile.DIRTYPE),
        ("../evil.txt", b"evil", tarfile.REGTYPE),
        ("a/../../evil2.txt", b"evil2", tarfile.REGTYPE),
        ("/abs.txt", b"abs", tarfile.REGTYPE),
        ("./dot.txt", b"dot", tarfile.REGTYPE),
        ("a//b.txt", b"ab", tarfile.REGTYPE),
        ("a/./c.txt", b"ac", tarfile.REGTYPE),
        ("link.txt", b"hello.txt", tarfile.SYMTYPE),
        ("p" * 50 + "/" + "x" * 70 + ".txt", b"long name split over prefix", tarfile.REGTYPE),
        ("deep/" + "/".join(f"d{i}" for i in range(8)) + "/leaf.txt", b"leaf", tarfile.REGTYPE),
    ]
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as tf:
        for name, data, typ in entries:
            ti = tarfile.TarInfo(name)
            ti.type = typ
            ti.mtime = 0
            if typ == tarfile.SYMTYPE:
                ti.linkname = data.decode()
                ti.size = 0
                tf.addfile(ti)
            elif typ == tarfile.DIRTYPE:
                ti.size = 0
                tf.addfile(ti)
            else:
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
    return entries


def expected_manifest(entries_data):
    """Expected manifest lines from the spec, in archive order.
    entries_data: list of (name, data, typeflag_byte)."""
    lines = []
    for name, data, tcode in entries_data:
        if tcode not in (ord("0"), 0):
            lines.append(f"SKIP\t{name}\t{tcode}")
            continue
        rel = spec_gate(name)
        if rel is None:
            lines.append(f"REJECT\t{name}")
        else:
            joined = "/".join(["out"] + rel)
            lines.append(f"OK\t{joined}\t{len(data)}\t{sum(data)}")
    return lines


def main():
    if not EXE.exists():
        subprocess.run(["lake", "build"], cwd=PILOT_DIR, check=True)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        archive_a = td / "a.tar"
        entries = build_archive_a(archive_a)

        # Reference view of archive A from Python tarfile.
        with tarfile.open(archive_a) as tf:
            members = tf.getmembers()
            ref_entries = []
            for m in members:
                data = tf.extractfile(m).read() if m.isreg() else b""
                tcode = m.type[0] if isinstance(m.type, bytes) else ord(m.type)
                ref_entries.append((m.name, data, tcode))

        # 1. list: Lean agrees with tarfile on name, size, typeflag.
        r = run_lean("list", str(archive_a))
        check("list-exit", r.returncode == 0, r.stderr)
        lean_list = []
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            lean_list.append((parts[0], int(parts[1]), int(parts[2])))
        # tarfile strips the trailing slash from directory names when
        # reading; the raw header keeps it. Normalize both sides.
        norm = lambda nl: [(n.rstrip("/") if t == 53 else n, s, t) for (n, s, t) in nl]
        lean_list, ref_list = norm(lean_list), norm(
            [(n, len(d), t) for (n, d, t) in ref_entries])
        check("list-match", lean_list == ref_list,
              f"lean={lean_list} ref={ref_list}")

        # 2. manifest: Lean agrees with the spec on every entry.
        r = run_lean("manifest", str(archive_a), "out")
        check("manifest-exit", r.returncode == 0, r.stderr)
        norm_skip = lambda ls: [
            "\t".join([p[0], p[1].rstrip("/")] + p[2:]) if l.startswith("SKIP")
            else l for l in ls for p in [l.split("\t")]]
        lean_manifest = norm_skip(r.stdout.splitlines())
        exp_manifest = norm_skip(expected_manifest(ref_entries))
        check("manifest-match", lean_manifest == exp_manifest,
              f"lean={lean_manifest} expected={exp_manifest}")
        ok_count = sum(1 for l in exp_manifest if l.startswith("OK"))
        rej_count = sum(1 for l in exp_manifest if l.startswith("REJECT"))
        skip_count = sum(1 for l in exp_manifest if l.startswith("SKIP"))

        # 3. create: Lean writes an archive Python can read back exactly.
        src = td / "src"
        (src / "sub").mkdir(parents=True)
        files = {"x.txt": b"created by lean", "sub/y.bin": bytes(range(200)),
                 "q" * 60 + "/" + "z" * 50 + ".bin": random.Random(7).randbytes(1200)}
        for rel, data in files.items():
            p = src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        out_tar = td / "created.tar"
        r = run_lean("create", str(out_tar), *files.keys(), cwd=src)
        check("create-exit", r.returncode == 0, r.stderr)
        got = {}
        if r.returncode == 0:
            with tarfile.open(out_tar) as tf:
                for m in tf.getmembers():
                    if m.isreg():
                        got[m.name] = tf.extractfile(m).read()
        check("create-readback", got == files, f"got={list(got)} want={list(files)}")

        # 4. Lean reads its own archive back with the same manifest.
        if r.returncode == 0:
            r2 = run_lean("manifest", str(out_tar), "out")
            exp2 = []
            for rel, data in files.items():
                joined = "/".join(["out"] + spec_gate(rel))
                exp2.append(f"OK\t{joined}\t{len(data)}\t{sum(data)}")
            check("self-manifest", r2.stdout.splitlines() == exp2,
                  f"lean={r2.stdout.splitlines()} expected={exp2}")

        # 5. Hostile and broken input must fail cleanly, not crash.
        raw = archive_a.read_bytes()
        trunc = td / "trunc.tar"
        trunc.write_bytes(raw[:1000])
        r = run_lean("list", str(trunc))
        check("truncated-fails", r.returncode == 1, f"rc={r.returncode}")
        garbage = td / "garbage.tar"
        garbage.write_bytes(random.Random(1).randbytes(4096))
        r = run_lean("list", str(garbage))
        check("garbage-fails", r.returncode == 1, f"rc={r.returncode}")
        badsum = td / "badsum.tar"
        mutated = bytearray(raw)
        mutated[10] ^= 0xFF  # corrupt a name byte; checksum now wrong
        badsum.write_bytes(bytes(mutated))
        r = run_lean("list", str(badsum))
        check("bad-checksum-fails", r.returncode == 1, f"rc={r.returncode}")

    # 6. Axiom check: only the three standard axioms.
    ax = subprocess.run(["lake", "env", "lean", "TarPilot/Verify.lean"],
                        cwd=PILOT_DIR, capture_output=True, text=True)
    ax_out = ax.stdout + ax.stderr
    check("axioms-run", ax.returncode == 0, ax_out[:400])
    for thm in ["gate_sound", "cleanComponents_sound", "extractAll_safe",
                "extractArchive_safe"]:
        check(f"axioms-{thm}", thm in ax_out, ax_out[:400])
    bad_axioms = [w for w in ["sorryAx"] if w in ax_out]
    check("axioms-no-sorry", not bad_axioms, ax_out[:400])

    lean_ver = subprocess.run(["lean", "--version"], capture_output=True,
                              text=True).stdout.strip()

    lines = [
        "# Test results",
        "",
        f"Run by `tests/run_tests.py` against Python's `tarfile` module.",
        f"Lean: {lean_ver}. Python: {sys.version.split()[0]}.",
        "",
        f"- Checks run: {checks}",
        f"- Failures: {len(failures)}",
        f"- Archive A entries compared (list and manifest): {len(ref_entries)}",
        f"- Manifest outcome on archive A: {ok_count} extracted, "
        f"{rej_count} rejected by the path gate, {skip_count} skipped as non-regular",
        f"- Files written by the Lean `create` command and read back by Python: {len(files)}",
        "- Broken inputs rejected with exit code 1: truncated archive, "
        "random garbage, corrupted checksum",
        "",
        "Axiom check (`TarPilot/Verify.lean`):",
        "",
        "```",
        ax_out.strip(),
        "```",
        "",
    ]
    if failures:
        lines += ["## Failures", ""] + [f"- {f}" for f in failures] + [""]
    RESULTS.write_text("\n".join(lines))
    print(f"{checks - len(failures)}/{checks} checks passed; results in {RESULTS}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
