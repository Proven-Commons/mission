#!/usr/bin/env python3
"""Why bar item 4 exists: a program can differ from its proof while
every proof check passes.

Copies a checkout of Proven-Commons/tar into a temporary directory and
adds `@[implemented_by]` to the path gate, pointing it at a function
that checks nothing. Then it shows three things:

- `lake comparator` accepts the headline theorem against a challenge
  file that states it word for word;
- `#print axioms` still lists only the standard three;
- the compiled program extracts `../evil.txt` to `out/../evil.txt`.

The checkout itself is not changed. Needs `lake` and bubblewrap.

    python3 -I implemented_by.py <tar checkout>
"""

import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

STATEMENT = '''theorem Spec.extract_safe : ∀ (dest : List String) (data : ByteArray)
    (out : List (List String × ByteArray)) (path : List String) (bytes : ByteArray),
    extractArchive dest data = some out → (path, bytes) ∈ out →
    ∃ rel, path = dest ++ rel ∧ ".." ∉ rel ∧ "" ∉ rel ∧ "." ∉ rel ∧ rel ≠ []'''


def run(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "tar"
        shutil.copytree(Path(sys.argv[1]).resolve(), work, ignore=shutil.ignore_patterns(".git"))

        # The change: a gate that keeps every name, wired in by implemented_by.
        path = work / "TarPilot" / "Path.lean"
        src = path.read_text()
        src = src.replace("/-- The gate every entry name must pass",
                          'def gateUnsafe (name : String) : Option (List String) := '
                          'some (name.splitOn "/")\n\n/-- The gate every entry name must pass', 1)
        src = src.replace("def gate (name : String)", "@[implemented_by gateUnsafe]\ndef gate (name : String)", 1)
        path.write_text(src)

        # A challenge that states the headline theorem, and a solution that proves it.
        (work / "Challenge.lean").write_text(f"import TarPilot.Archive\nopen TarPilot\n\n{STATEMENT} := sorry\n")
        (work / "Solution.lean").write_text(f"import TarPilot.Archive\nopen TarPilot\n\n{STATEMENT} :=\n"
                                            "  extractArchive_safe\n")
        (work / "comparator.json").write_text(
            '{"challenge_module": "Challenge", "solution_module": "Solution",\n'
            ' "theorem_names": ["Spec.extract_safe"],\n'
            ' "permitted_axioms": ["propext", "Quot.sound", "Classical.choice"]}\n')
        lakefile = work / "lakefile.toml"
        lakefile.write_text(lakefile.read_text().replace(
            'defaultTargets = ["TarPilot", "tar-pilot"]',
            'defaultTargets = ["TarPilot", "tar-pilot", "Challenge", "Solution"]')
            + '\n[[lean_lib]]\nname = "Challenge"\n\n[[lean_lib]]\nname = "Solution"\n')

        build = run(["lake", "build"], work)
        print(f"lake build exit:       {build.returncode}")
        cmp = run(["lake", "comparator"], work)
        print(f"lake comparator exit:  {cmp.returncode}  ({(cmp.stdout + cmp.stderr).strip().splitlines()[-1]})")
        (work / "Axioms.lean").write_text("import TarPilot\n#print axioms TarPilot.extractArchive_safe\n")
        ax = run(["lake", "env", "lean", "Axioms.lean"], work)
        print(f"#print axioms:         {ax.stdout.strip()}")

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as t:
            ti = tarfile.TarInfo("../evil.txt")
            ti.size = 1
            t.addfile(ti, io.BytesIO(b"x"))
        archive = work / "evil.tar"
        archive.write_bytes(buf.getvalue())
        out = run([str(work / ".lake" / "build" / "bin" / "tar-pilot"), "manifest", str(archive), "out"], work)
        print(f"program on ../evil.txt: {out.stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
