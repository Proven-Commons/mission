# redis: a RESP parser and key-value store with machine-checked proofs

This repo is a Lean 4 rebuild of the core of Redis's wire protocol: the RESP2
parser and printer, and a small key-value store that serves `PING`, `ECHO`,
`SET`, `GET`, `DEL`, `EXISTS`, `APPEND`, and `STRLEN`. Proofs a computer checks
show that printing and parsing are exact inverses, and that a get after a set
returns the set value and a get after a delete returns nothing. Differential
tests compare it with hiredis and with a real `redis-server`.

It is the Wave 1 Redis project of [Proven Commons](https://github.com/Proven-Commons/mission),
held to the verified bar in the [founding brief](https://github.com/Proven-Commons/mission/blob/main/FOUNDING-BRIEF.md#the-verified-bar).

Where it lives: for now in `projects/redis` of the mission repo, until an org
owner creates `Proven-Commons/redis`. The folder is a complete Lean project and
moves to that repo unchanged; run every command below from this folder.

**Status: not yet verified.** Proofs complete, no `sorry`, standard axioms only,
differential tests recorded. The specification in [`SPEC.md`](SPEC.md) still needs
approval from a reviewer who did not write it. Until then, do not call this
project verified.

## Run it

Needs Lean 4.35.0 (install with elan; the toolchain is pinned in `lean-toolchain`).

```
lake build
printf '*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$2\r\nhi\r\n*2\r\n$3\r\nGET\r\n$1\r\nk\r\n' | .lake/build/bin/resp serve
```

`resp serve` reads requests from standard input until it ends and writes the
replies (`+OK\r\n$2\r\nhi\r\n` above). `resp decode` reads hex inputs, one per line,
and prints the parsed value of each as JSON; the tests use it.

## What is proved

In `Resp/RoundTrip.lean`, `Resp/Store.lean`, and `Resp/Laws.lean`. `SPEC.md` gives
each rule in plain words.

Parser and printer:

- `decode_encode`: for every well-formed value `v` and any bytes `rest`,
  `decode (encode v ++ rest) = some (v, rest)`. Reading what the printer wrote
  gives the same value back and leaves the next bytes alone, so values can be
  streamed back to back.
- `decode_sound`: whatever `decode` accepts is a well-formed value, and the
  input was exactly its printed form plus the rest. The parser accepts nothing
  else: no leading zeros, no `+5` or `-0`, no bare CR or LF inside a line, no
  missing CR LF after a bulk payload, no integer outside 64 bits.
- `decode_suffix`: what is left after a parse is a suffix of the input.
- `encode_injective`: two different values never print to the same bytes.
- The parser is a total function: it returns `none` instead of crashing, and
  nesting is bounded by fuel taken from the input length.

Store and commands:

- `Store.get_set_self`, `Store.get_set_other`, `Store.get_del_self`,
  `Store.get_del_other`: the store laws. `Store.keys_set_nodup`: no key is
  stored twice.
- `get_after_set`: a `GET k` after `SET k v` replies with `v`, for any store and
  any case spelling of the command names.
- `get_after_set_other`: a `SET` leaves the `GET` reply for every other key unchanged.
- `get_after_del`: a `GET k` after `DEL k` replies with the null bulk string.

Over the wire:

- `parseRequest_encodeRequest`: the server reads back exactly the request a
  client printed.
- `serve_encodeAll`: on a byte stream of printed requests, `serve` answers each
  one in order exactly as running the commands one by one would, and reads
  every byte.
- `wire_set_get`, `wire_del_get`: the bytes for `SET k v` then `GET k` get the
  replies `+OK` and `v`; the bytes for `DEL k` then `GET k` end with `$-1`.

Axiom check: every theorem above depends only on `propext`, `Classical.choice`,
and `Quot.sound`, or a subset. The output is in `tests/TEST-RESULTS.md`.

## What is tested, not proved

`tests/run_tests.py`, seed `20261025`, results in [`tests/TEST-RESULTS.md`](tests/TEST-RESULTS.md):

1. **Parser against an independent specification.** 200,000 inputs (valid
   encodings, valid encodings with trailing data, and mutations of them), run
   through the Lean parser and a separate Python copy of the RESP2 rules.
   0 mismatches in value, bytes read, or rejection.
2. **Parser against hiredis 3.5.0**, the C parser Redis clients use, on the
   same 200,000 inputs. Every input the Lean parser accepts, hiredis accepts
   with the same value and the same length. 0 mismatches. Inputs that only
   hiredis accepts are counted by cause: hiredis does not check the CR LF after
   a bulk payload (`$3\r\nabcXY` reads as `abc`), and hiredis also reads RESP3
   types. Both are deliberate differences. No difference has another cause.
3. **Server against redis-server 7.0.15.** 2,000 sessions of 50 random commands
   each (100,000 commands, 2.2 MB of replies), covering mixed-case names, binary
   keys and values, wrong argument counts, unknown commands with long and
   binary arguments, and empty requests. Reply bytes identical in every session.

A seeded bug in one error message made the server check fail in 40 of 50
sessions, which shows the check can catch a wrong reply.

Finding on the way: hiredis-py 3.1.0 crashes Python with a segmentation fault
on a RESP3 map whose key is an array, for example `%1\r\n*0\r\n:1\r\n`. hiredis-py
3.5.0 raises `TypeError` instead, so upstream has fixed it; the tests use 3.5.0.

## What is not proved, and what you must trust

- **Reply text.** That each reply matches Redis byte for byte is tested (check 3
  above), not proved. The proofs say what the replies are; the tests say they
  match Redis 7.0. Other Redis versions word some errors differently.
- **Scope.** RESP2 only. No RESP3, inline commands, expiry, other data types,
  persistence, `SET` options, or other commands. A real Redis command outside the
  table in `SPEC.md` gets the unknown command error here.
- **Integer replies.** `DEL`, `EXISTS`, `APPEND`, and `STRLEN` reply with counts
  and lengths. These are not proved to stay below 2^63; no real input comes close.
- **Performance.** This is a model, not a production server. Bytes are Lean
  lists and the store is an association list, so a lookup costs time in
  proportion to the number of keys. On one machine, 100,000 mixed `SET` and `GET`
  requests over 1,000 keys took about 8 seconds. If speed matters, use it the
  way AWS uses its Lean Cedar model: as the specification that a fast server is
  checked against with differential tests.
- **No network code.** `resp serve` reads standard input and writes standard
  output. Sockets, timeouts, and partial reads are outside the proof.
- **Trusted base.** The Lean kernel, compiler, and runtime, as in every Lean
  project. The command line front end in `Main.lean` (hex and JSON handling,
  standard input and output) is not proved.

## Re-check it

```
python3 tests/run_tests.py
```

One command. It rebuilds the project (the build fails if a proof breaks),
fails if any `.lean` file contains `sorry` or `admit`, prints the axioms, reruns
all three differential checks, and rewrites `tests/TEST-RESULTS.md`. Checks 2 and
3 need `pip install hiredis==3.5.0` and `redis-server` 7.0; if either is missing,
the report says SKIPPED and the run fails. CI runs the same steps on every push that
touches this folder (`.github/workflows/redis-check.yml` in the mission repo).

To check only the proofs and axioms: `lake build && lake env lean Resp/Verify.lean`.

## Target score

Scored on the brief's six points, 0 to 3 each:

| Point | Score | Why |
| --- | --- | --- |
| Harm if it fails | 2 | A parser bug in a protocol front end lets one client desync or corrupt another's replies; Redis often sits in front of sessions and caches. |
| Reach | 3 | Redis and its protocol are spoken by clients in almost every language, and many other servers reuse RESP. |
| Specification size | 3 | RESP2 fits on one page. |
| Oracle | 3 | `redis-server` and hiredis are both open source and easy to run. |
| Slice | 3 | The parser and printer stand alone; the store adds a small, separate slice. |
| Upstream stance | 1 | Not yet contacted. |
| **Total** | **15 / 18** | |

## Layout

- `Resp/Decimal.lean`: canonical decimal numbers, with both round-trip proofs.
- `Resp/Value.lean`: RESP2 values, the printer, and the parser.
- `Resp/RoundTrip.lean`: printer and parser are inverses.
- `Resp/Store.lean`: the key-value store and its laws.
- `Resp/Command.lean`: commands, requests, and the `serve` loop.
- `Resp/Laws.lean`: command-level and wire-level theorems.
- `Resp/Verify.lean`: the axiom check.
- `Main.lean`: the command line front end.
- `SPEC.md`: the specification in plain words.
- `tests/run_tests.py`: the differential tests.

## Next steps

1. Independent review of `SPEC.md`.
2. Contact Redis and hiredis maintainers with the results.
3. Offer the decimal lemmas and the list-based parser lemmas to CSLib.
4. Prove the reply wording for each command against a written table, so check 3
   tests the table instead of carrying the whole claim.
