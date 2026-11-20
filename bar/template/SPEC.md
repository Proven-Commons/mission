# Specification: clamp

This is the template's specification. Replace it with the real one. A reviewer who did not write it approves it together with `Clamp/Spec.lean` and the page sections listed in `bar.toml`.

## Scope

`Clamp.clamp lo hi x` returns `x` moved into the closed range from `lo` to `hi`. Inputs are natural numbers of any size. When `lo > hi` the range is empty and the result is `lo`.

## Valid inputs and errors

Every input is valid. The function is total and has no error case.

## What must always hold

Each property below is a theorem in `Clamp/Spec.lean`.

| Property | Theorem |
|----------|---------|
| With `lo ≤ hi`, the result is at least `lo` and at most `hi`. | `Clamp.Spec.clamp_in_range` |
| A value already in the range comes back unchanged. | `Clamp.Spec.clamp_of_mem` |

The first is a safety property. A function that always returns `lo` meets it, so the second is there to rule that function out.

## Oracle

The original this template stands in for is Python's `max(lo, min(hi, x))`.
