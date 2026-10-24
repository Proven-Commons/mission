#!/usr/bin/env python3
"""Finding F6 of the 2026-10-24 bar audit: faults the pilot's own checks
let through.

Copies a checkout of Proven-Commons/tar into a temporary directory,
plants one fault at a time in `TarPilot/Path.lean`, and records the exit
code of `lake build` and of `python3 tests/run_tests.py`. The checkout
itself is not changed. Needs `lake` on the PATH.

    python3 -I plant_faults.py <tar checkout>

Faults:
- sorry: the proof of `gate_sound` replaced by `sorry`.
- axiom: `axiom cheat : False` added, and `gate_sound` proved from it.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def replace_proof(src, body, extra_decl=""):
    start = src.index("theorem gate_sound")
    proof = src.index(":= by", start)
    end = src.index("end TarPilot", proof)
    head = src[:start].rstrip() + "\n\n" + extra_decl
    return head + src[start:proof] + ":=" + body + "\n\n" + src[end:]


FAULTS = {
    "sorry": lambda s: replace_proof(s, " by\n  sorry"),
    "axiom": lambda s: replace_proof(s, "\n  cheat.elim",
                                     "axiom cheat : False\n\n"),
}


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    checkout = Path(sys.argv[1]).resolve()
    for name, plant in FAULTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "tar"
            shutil.copytree(checkout, work,
                            ignore=shutil.ignore_patterns(".git"))
            path = work / "TarPilot" / "Path.lean"
            path.write_text(plant(path.read_text()))
            build = run(["lake", "build"], work)
            tests = run([sys.executable, "tests/run_tests.py"], work)
            summary = (tests.stdout.strip().splitlines() or [""])[-1]
            axioms = [line for line in
                      (work / "tests" / "TEST-RESULTS.md").read_text().splitlines()
                      if "gate_sound" in line]
            print(f"## fault: {name}")
            print(f"lake build exit:          {build.returncode}")
            print(f"tests/run_tests.py exit:  {tests.returncode}  ({summary})")
            for line in axioms:
                print(f"TEST-RESULTS.md records:  {line}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
