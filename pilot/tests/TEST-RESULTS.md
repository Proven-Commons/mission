# Test results

Run by `tests/run_tests.py` against Python's `tarfile` module.
Lean: Lean (version 4.35.0, x86_64-unknown-linux-gnu, commit eb6cafb7290e8bd5f2937522d8d804f58f02bafc, Release). Python: 3.12.3.

- Checks run: 16
- Failures: 0
- Archive A entries compared (list and manifest): 14
- Manifest outcome on archive A: 9 extracted, 3 rejected by the path gate, 2 skipped as non-regular
- Files written by the Lean `create` command and read back by Python: 3
- Broken inputs rejected with exit code 1: truncated archive, random garbage, corrupted checksum

Axiom check (`TarPilot/Verify.lean`):

```
'TarPilot.gate_sound' depends on axioms: [propext, Classical.choice, Quot.sound]
'TarPilot.cleanComponents_sound' depends on axioms: [propext]
'TarPilot.extractAll_safe' depends on axioms: [propext, Classical.choice, Quot.sound]
'TarPilot.extractArchive_safe' depends on axioms: [propext, Classical.choice, Quot.sound]
```
