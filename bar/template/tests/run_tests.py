#!/usr/bin/env python3
"""Differential tests: the Lean `clamp` executable against the oracle.

The oracle is Python's own `max(lo, min(hi, x))`, the original this
template stands in for. Inputs are edge cases, random triples from a
recorded seed, and mutations of those triples that move `x` to just
inside and just outside the range. Run from anywhere:

    python3 tests/run_tests.py [--seed N] [--count N]

It builds the executable if it is missing, writes `tests/TEST-RESULTS.md`,
and exits non-zero if any input disagrees.
"""

import argparse
import platform
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / ".lake" / "build" / "bin" / "clamp"
RESULTS = ROOT / "tests" / "TEST-RESULTS.md"


def oracle(lo, hi, x):
    return max(lo, min(hi, x))


def inputs(seed, count):
    """Edge cases, then random triples, each followed by its mutations.
    Returns the cases and how many of them are mutations."""
    edges = [0, 1, 2, 2**8 - 1, 2**32, 2**64 - 1, 2**64, 2**100]
    cases = [(lo, hi, x) for lo in edges for hi in edges for x in edges]
    rng = random.Random(seed)
    mutated = 0
    while len(cases) < count:
        bits = rng.choice([4, 16, 64, 128])
        lo, hi, x = (rng.getrandbits(bits) for _ in range(3))
        cases.append((lo, hi, x))
        for m in (lo - 1, lo, hi, hi + 1):
            if m >= 0 and len(cases) < count:
                cases.append((lo, hi, m))
                mutated += 1
    return cases[:count], mutated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261024)
    ap.add_argument("--count", type=int, default=1_000_000)
    args = ap.parse_args()

    if not EXE.exists():
        subprocess.run(["lake", "build", "clamp"], cwd=ROOT, check=True)

    cases, mutated = inputs(args.seed, args.count)
    stdin = "".join(f"{lo} {hi} {x}\n" for lo, hi, x in cases)
    out = subprocess.run([str(EXE)], input=stdin, capture_output=True,
                         text=True, check=True).stdout.split("\n")
    failures = [(c, got) for c, got in zip(cases, out)
                if got != str(oracle(*c))]
    if len(out) < len(cases):
        failures.append(("missing output", f"{len(out)} lines"))

    lean = subprocess.run(["lake", "env", "lean", "--version"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    lines = [
        "# Test results",
        "",
        "Written by `tests/run_tests.py`. Rerun it to check these numbers.",
        "",
        f"- Oracle: Python {platform.python_version()} `max(lo, min(hi, x))`",
        f"- Lean: {lean}",
        f"- Seed: {args.seed}",
        f"- Inputs: {len(cases)}",
        f"- Mutated: {mutated} of the inputs move x to just inside or outside the range",
        f"- Failures: {len(failures)}",
        "",
    ]
    if failures:
        lines += ["## Failures", ""]
        lines += [f"- `{c}`: Lean printed `{got}`" for c, got in failures[:50]]
        lines.append("")
    RESULTS.write_text("\n".join(lines))
    print(f"{len(cases) - len(failures)}/{len(cases)} inputs agree; "
          f"results in {RESULTS}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
