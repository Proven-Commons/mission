#!/usr/bin/env python3
"""Differential tests for the Lean RESP parser and key-value server.

Three checks, all from one fixed seed:

1. Parser against an independent copy of the specification (written here in
   Python, from the RESP2 rules, without looking at the Lean code). Results must
   match exactly: same value, same number of bytes read, same rejections.
2. Parser against hiredis, the C parser that Redis clients use. Every input the
   Lean parser accepts, hiredis must accept with the same value and the same
   length. Inputs only hiredis accepts are counted by cause.
3. Server against a real redis-server: random command sessions are sent to
   both, and the reply bytes must be identical.

Usage: python3 tests/run_tests.py [--seed N] [--parser-cases N] [--sessions N]
It rebuilds the project if needed and rewrites tests/TEST-RESULTS.md.
hiredis (pip install hiredis) and redis-server must be installed for checks 2
and 3; a missing one is reported as skipped, never as passed.
"""

import argparse
import datetime
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, ".lake", "build", "bin", "resp")
RESULTS = os.path.join(ROOT, "tests", "TEST-RESULTS.md")

# ---------------------------------------------------------------------------
# Independent specification of strict RESP2.
# Values: ("S", bytes) ("E", bytes) ("I", int) ("B", bytes) ("NB",)
#         ("A", [values]) ("NA",)


def spec_line(bs, i):
    """Bytes up to the first CR LF from i. A bare CR or LF first is an error."""
    j = i
    while j < len(bs):
        c = bs[j]
        if c == 13:
            if j + 1 < len(bs) and bs[j + 1] == 10:
                return bs[i:j], j + 2
            return None
        if c == 10:
            return None
        j += 1
    return None


def spec_nat(f):
    if not f or not all(48 <= c <= 57 for c in f):
        return None
    if f[0] == 48 and len(f) > 1:
        return None
    return int(f)


def spec_int(f):
    if f[:1] == b"-":
        n = spec_nat(f[1:])
        if n is None or n == 0 or n > 2**63:
            return None
        return -n
    n = spec_nat(f)
    if n is None or n >= 2**63:
        return None
    return n


def spec_len(f):
    if f == b"-1":
        return -1
    return spec_nat(f)


def spec_parse(bs, i, depth, check_bulk_end=True):
    """Return (value, next index) or None."""
    if depth == 0 or i >= len(bs):
        return None
    t = bs[i]
    r = spec_line(bs, i + 1)
    if r is None or t not in b"+-:$*":
        return None
    line, j = r
    if t == ord("+"):
        return ("S", line), j
    if t == ord("-"):
        return ("E", line), j
    if t == ord(":"):
        n = spec_int(line)
        return None if n is None else (("I", n), j)
    n = spec_len(line)
    if n is None:
        return None
    if t == ord("$"):
        if n == -1:
            return ("NB",), j
        if j + n > len(bs):
            return None
        if check_bulk_end:
            if bs[j + n:j + n + 2] != b"\r\n":
                return None
        elif j + n + 2 > len(bs):
            return None
        return ("B", bs[j:j + n]), j + n + 2
    if n == -1:
        return ("NA",), j
    xs = []
    for _ in range(n):
        r = spec_parse(bs, j, depth - 1, check_bulk_end)
        if r is None:
            return None
        x, j = r
        xs.append(x)
    return ("A", xs), j


def spec_decode(bs, check_bulk_end=True):
    return spec_parse(bs, 0, len(bs) + 1, check_bulk_end)


def spec_encode(v):
    t = v[0]
    if t == "S":
        return b"+" + v[1] + b"\r\n"
    if t == "E":
        return b"-" + v[1] + b"\r\n"
    if t == "I":
        return b":" + str(v[1]).encode() + b"\r\n"
    if t == "B":
        return b"$" + str(len(v[1])).encode() + b"\r\n" + v[1] + b"\r\n"
    if t == "NB":
        return b"$-1\r\n"
    if t == "NA":
        return b"*-1\r\n"
    return b"*" + str(len(v[1])).encode() + b"\r\n" + b"".join(spec_encode(x) for x in v[1])


def from_lean(j):
    t = j[0]
    if t in ("S", "E", "B"):
        return (t, bytes.fromhex(j[1]))
    if t == "I":
        return ("I", j[1])
    if t == "A":
        return ("A", [from_lean(x) for x in j[1]])
    return (t,)


# ---------------------------------------------------------------------------
# Input generation.

LINE_BYTES = [b for b in range(256) if b not in (10, 13)]
RESP3_TYPES = b"_,#!=(%~|>"


def rand_line(rng):
    n = rng.choice([0, 1, 2, 5, 12, 40])
    return bytes(rng.choice(LINE_BYTES) for _ in range(n))


def rand_bytes(rng):
    n = rng.choice([0, 1, 2, 3, 8, 30, 200])
    return bytes(rng.randrange(256) for _ in range(n))


def rand_int(rng):
    return rng.choice([
        0, 1, -1, 9, 10, -10, rng.randrange(-1000, 1000), rng.randrange(-2**63, 2**63),
        2**63 - 1, -2**63,
    ])


def rand_value(rng, depth=3):
    k = rng.randrange(7 if depth > 0 else 5)
    if k == 0:
        return ("S", rand_line(rng))
    if k == 1:
        return ("E", rand_line(rng))
    if k == 2:
        return ("I", rand_int(rng))
    if k == 3:
        return ("B", rand_bytes(rng))
    if k == 4:
        return rng.choice([("NB",), ("NA",)])
    return ("A", [rand_value(rng, depth - 1) for _ in range(rng.choice([0, 1, 2, 3, 5]))])


SPECIAL = b"\r\n-+:$*0123456789" + RESP3_TYPES


def mutate(rng, bs):
    bs = bytearray(bs)
    for _ in range(rng.choice([1, 1, 1, 2, 3])):
        op = rng.randrange(6)
        if op == 0 and bs:  # replace a byte
            bs[rng.randrange(len(bs))] = rng.choice(SPECIAL) if rng.random() < 0.7 else rng.randrange(256)
        elif op == 1:  # insert a byte
            bs.insert(rng.randrange(len(bs) + 1), rng.choice(SPECIAL))
        elif op == 2 and bs:  # delete a byte
            del bs[rng.randrange(len(bs))]
        elif op == 3 and bs:  # truncate
            del bs[rng.randrange(len(bs)):]
        elif op == 4 and bs:  # duplicate a slice
            i = rng.randrange(len(bs))
            j = min(len(bs), i + rng.randrange(1, 8))
            bs[i:i] = bs[i:j]
        else:  # append junk
            bs += bytes(rng.choice(SPECIAL) for _ in range(rng.randrange(1, 4)))
    return bytes(bs)


HAND_CASES = [
    b"", b"+\r\n", b"+OK\r\n", b"-ERR x\r\n", b":0\r\n", b":-0\r\n", b":007\r\n", b":+5\r\n",
    b":9223372036854775807\r\n", b":9223372036854775808\r\n", b":-9223372036854775808\r\n",
    b":-9223372036854775809\r\n", b":\r\n", b":-\r\n", b"$0\r\n\r\n", b"$-1\r\n", b"$-2\r\n",
    b"$03\r\nabc\r\n", b"$3\r\nabc\r\n", b"$3\r\nabcXY", b"$3\r\nab", b"$3\r\nabc\r", b"*0\r\n",
    b"*-1\r\n", b"*-2\r\n", b"*00\r\n", b"*1\r\n", b"*2\r\n:1\r\n:2\r\n", b"+a\rb\r\n",
    b"+a\nb\r\n", b"+a\n", b"_\r\n", b"#t\r\n", b",1.5\r\n", b"x\r\n", b"$1\r\n\r\r\n",
    b"*1\r\n" * 30 + b":1\r\n", b"+OK\r\n+OK\r\n", b"$5\r\nhello\r\n:1\r\n",
]


def parser_inputs(rng, n):
    cases = list(HAND_CASES)
    while len(cases) < n:
        v = rand_value(rng)
        bs = spec_encode(v)
        r = rng.random()
        if r < 0.35:
            cases.append(bs)
        elif r < 0.45:
            cases.append(bs + spec_encode(rand_value(rng, 1)))
        else:
            cases.append(mutate(rng, bs))
    return cases


# ---------------------------------------------------------------------------
# Check 1 and 2: the parser.


def run_lean_decode(cases):
    # `resp decode` skips blank lines, so an empty input goes as a placeholder
    # and its answer is patched below.
    lines = [c.hex() if c else "00" for c in cases]
    out = subprocess.run([BIN, "decode"], input="\n".join(lines).encode(), capture_output=True, check=True)
    res = [json.loads(l) for l in out.stdout.decode().splitlines()]
    assert len(res) == len(cases), (len(res), len(cases))
    for i, c in enumerate(cases):
        if not c:
            res[i] = {"ok": False}
    return res


def project(v):
    """What hiredis can tell apart: it returns bytes for simple and bulk strings
    and None for both null kinds."""
    t = v[0]
    if t in ("S", "B"):
        return ("str", v[1])
    if t == "E":
        return ("err", v[1].decode("utf-8", "replace"))
    if t == "I":
        return ("int", v[1])
    if t in ("NB", "NA"):
        return ("nil",)
    return ("arr", [project(x) for x in v[1]])


def project_hiredis(x, hiredis):
    if isinstance(x, bytes):
        return ("str", x)
    if isinstance(x, hiredis.ReplyError):
        return ("err", str(x))
    if isinstance(x, bool):
        return ("bool", x)
    if isinstance(x, int):
        return ("int", x)
    if x is None:
        return ("nil",)
    if isinstance(x, list):
        return ("arr", [project_hiredis(y, hiredis) for y in x])
    return ("other", repr(x))


INCOMPLETE = object()


def hiredis_read(hiredis, bs):
    r = hiredis.Reader(notEnoughData=INCOMPLETE)
    try:
        r.feed(bs)
        x = r.gets()
    except Exception as e:  # ProtocolError, or TypeError for a RESP3 map with a list key
        return ("error", f"{type(e).__name__}: {e}")
    if x is INCOMPLETE:
        return ("incomplete", None)
    return ("value", x)


def check_parser(rng, n):
    cases = parser_inputs(rng, n)
    lean = run_lean_decode(cases)
    stats = {"inputs": len(cases), "lean_accepts": 0, "lean_rejects": 0,
             "spec_mismatch": 0, "reencode_mismatch": 0}
    failures = []
    for c, l in zip(cases, lean):
        s = spec_decode(c)
        if l["ok"]:
            stats["lean_accepts"] += 1
            v = from_lean(l["v"])
            if s is None or s[0] != v or s[1] != l["used"]:
                stats["spec_mismatch"] += 1
                failures.append(("spec", c, l, s))
            if spec_encode(v) != c[:l["used"]]:
                stats["reencode_mismatch"] += 1
                failures.append(("reencode", c, l, None))
        else:
            stats["lean_rejects"] += 1
            if s is not None:
                stats["spec_mismatch"] += 1
                failures.append(("spec", c, l, s))

    try:
        import hiredis
    except ImportError:
        return stats, None, failures, cases

    h = {"both_accept_same": 0, "both_reject": 0, "lean_only": 0, "value_mismatch": 0,
         "framing_mismatch": 0, "hiredis_only_bulk_end": 0, "hiredis_only_resp3": 0,
         "hiredis_only_unexplained": 0}
    for c, l in zip(cases, lean):
        kind, x = hiredis_read(hiredis, c)
        if l["ok"]:
            if kind != "value":
                h["lean_only"] += 1
                failures.append(("hiredis-rejects", c, l, (kind, x)))
                continue
            v = from_lean(l["v"])
            if project_hiredis(x, hiredis) != project(v):
                h["value_mismatch"] += 1
                failures.append(("hiredis-value", c, l, x))
                continue
            u = l["used"]
            k1, _ = hiredis_read(hiredis, c[:u])
            k2, _ = hiredis_read(hiredis, c[:u - 1])
            if k1 != "value" or k2 != "incomplete":
                h["framing_mismatch"] += 1
                failures.append(("hiredis-framing", c, l, (k1, k2)))
                continue
            h["both_accept_same"] += 1
        elif kind != "value":
            h["both_reject"] += 1
        elif spec_decode(c, check_bulk_end=False) is not None:
            h["hiredis_only_bulk_end"] += 1
        elif any(b in RESP3_TYPES for b in c):
            h["hiredis_only_resp3"] += 1
        else:
            h["hiredis_only_unexplained"] += 1
            failures.append(("hiredis-only", c, l, x))
    return stats, h, failures, cases


# ---------------------------------------------------------------------------
# Check 3: the server against redis-server.


def bulk_req(args):
    return b"*%d\r\n" % len(args) + b"".join(b"$%d\r\n%s\r\n" % (len(a), a) for a in args)


KEYS = [b"k0", b"k1", b"k2", b"k3", b"K0", b"", b"a b", b"\x00\r\n", bytes(range(1, 9))]
NOT_OPTIONS = [b"zz", b"foo", b"1", b"opt"]
UNKNOWN = [b"foo", b"nosuchcmd", b"x" * 200, b"bad\r\nname", b"nu\x00ll", b"SETX", b"gett"]


def rand_case(rng, name):
    return bytes(c ^ 32 if 97 <= (c | 32) <= 122 and rng.random() < 0.5 else c for c in name)


def rand_val(rng):
    k = rng.randrange(4)
    if k == 0:
        return str(rng.randrange(-1000, 100000)).encode()
    if k == 1:
        return b""
    return bytes(rng.randrange(256) for _ in range(rng.choice([1, 3, 10, 40])))


def rand_command(rng):
    key = lambda: rng.choice(KEYS)
    k = rng.randrange(100)
    if k < 20:
        return [rand_case(rng, b"set"), key(), rand_val(rng)]
    if k < 38:
        return [rand_case(rng, b"get"), key()]
    if k < 46:
        return [rand_case(rng, b"del")] + [key() for _ in range(rng.randrange(1, 4))]
    if k < 54:
        return [rand_case(rng, b"exists")] + [key() for _ in range(rng.randrange(1, 4))]
    if k < 62:
        return [rand_case(rng, b"append"), key(), rand_val(rng)]
    if k < 68:
        return [rand_case(rng, b"strlen"), key()]
    if k < 73:
        return [rand_case(rng, b"ping")] + [rand_val(rng) for _ in range(rng.choice([0, 0, 1, 2]))]
    if k < 77:
        return [rand_case(rng, b"echo")] + [rand_val(rng) for _ in range(rng.choice([1, 1, 0, 2]))]
    if k < 85:  # wrong number of arguments
        name = rng.choice([b"set", b"get", b"del", b"exists", b"append", b"strlen", b"echo"])
        n = {b"set": [0, 1], b"get": [0, 2], b"del": [0], b"exists": [0],
             b"append": [0, 1, 3], b"strlen": [0, 2], b"echo": [0, 2]}[name]
        return [rand_case(rng, name)] + [key() for _ in range(rng.choice(n))]
    if k < 88:
        return [rand_case(rng, b"set"), key(), rand_val(rng), rng.choice(NOT_OPTIONS)]
    if k < 97:
        args = [rng.choice(UNKNOWN)]
        for _ in range(rng.choice([0, 1, 2, 5])):
            args.append(rng.choice([rand_val(rng), b"y" * rng.choice([50, 130, 300]), b"a\r\nb", b"c\x00d"]))
        return args
    return []  # empty request: no reply


SENTINEL = [b"ECHO", b"--end-of-session--"]
SENTINEL_REPLY = b"$18\r\n--end-of-session--\r\n"


def recv_until(sock, suffix):
    buf = b""
    while not buf.endswith(suffix):
        chunk = sock.recv(1 << 16)
        if not chunk:
            raise RuntimeError("redis-server closed the connection")
        buf += chunk
    return buf


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def check_server(rng, sessions, per_session):
    exe = shutil.which("redis-server")
    if exe is None:
        return None, []
    version = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    port = free_port()
    tmp = tempfile.mkdtemp()
    proc = subprocess.Popen([exe, "--port", str(port), "--save", "", "--appendonly", "no",
                             "--dir", tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                sock = socket.create_connection(("127.0.0.1", port))
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("redis-server did not start")
        stats = {"redis_version": version, "sessions": sessions, "commands": 0,
                 "reply_bytes": 0, "mismatched_sessions": 0}
        failures = []
        for _ in range(sessions):
            cmds = [rand_command(rng) for _ in range(per_session)]
            stream = b"".join(bulk_req(c) for c in cmds) + bulk_req(SENTINEL)
            sock.sendall(bulk_req([b"FLUSHALL"]))
            recv_until(sock, b"+OK\r\n")
            sock.sendall(stream)
            want = recv_until(sock, SENTINEL_REPLY)
            got = subprocess.run([BIN, "serve"], input=stream, capture_output=True).stdout
            stats["commands"] += len(cmds)
            stats["reply_bytes"] += len(want)
            if got != want:
                stats["mismatched_sessions"] += 1
                failures.append(("server", cmds, want, got))
        sock.close()
        return stats, failures
    finally:
        proc.terminate()
        proc.wait()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--parser-cases", type=int, default=200000)
    ap.add_argument("--sessions", type=int, default=2000)
    ap.add_argument("--per-session", type=int, default=50)
    a = ap.parse_args()

    subprocess.run(["lake", "build"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    holes = []
    for d, _, files in os.walk(ROOT):
        if ".lake" in d or ".git" in d:
            continue
        for f in files:
            if f.endswith(".lean"):
                text = open(os.path.join(d, f), encoding="utf-8").read()
                if re.search(r"\b(sorry|admit)\b", text):
                    holes.append(os.path.relpath(os.path.join(d, f), ROOT))
    axioms = subprocess.run(["lake", "env", "lean", "Resp/Verify.lean"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()

    rng = random.Random(a.seed)
    t0 = time.time()
    pstats, hstats, pfail, _ = check_parser(rng, a.parser_cases)
    sstats, sfail = check_server(random.Random(a.seed + 1), a.sessions, a.per_session)
    elapsed = time.time() - t0
    failures = pfail + sfail

    ok = not failures and not holes and hstats is not None and sstats is not None
    lines = ["# Test results", "",
             f"Generated by `python3 tests/run_tests.py` on {datetime.date.today().isoformat()}.",
             f"Seed: `{a.seed}` (server sessions use seed + 1). Run time: {elapsed:.0f} s.", "",
             f"Overall: **{'PASS' if ok else 'FAIL'}**, {len(failures)} failures.", "",
             "## 0. Proof holes", "",
             ("Files containing `sorry` or `admit`: " + ", ".join(holes)) if holes
             else "No `sorry` or `admit` in any `.lean` file.", "",
             "## 1. Parser against the independent Python specification", ""]
    lines += [f"- {k}: {v}" for k, v in pstats.items()]
    lines += ["", "## 2. Parser against hiredis", ""]
    if hstats is None:
        lines.append("SKIPPED: hiredis is not installed (`pip install hiredis`).")
    else:
        import hiredis
        lines.append(f"hiredis version: {getattr(hiredis, '__version__', 'unknown')}")
        lines.append("")
        lines += [f"- {k}: {v}" for k, v in hstats.items()]
        lines += ["", "`hiredis_only_*` counts are inputs hiredis accepts and this parser rejects by "
                  "design: `bulk_end` means hiredis does not check the CR LF after a bulk payload; "
                  "`resp3` means the input holds a RESP3 type byte, which a RESP2 parser rejects "
                  "(a byte-presence check, not a full RESP3 parse). `hiredis_only_unexplained` must be 0."]
    lines += ["", "## 3. Server against redis-server", ""]
    if sstats is None:
        lines.append("SKIPPED: redis-server is not installed.")
    else:
        lines += [f"- {k}: {v}" for k, v in sstats.items()]
    lines += ["", "## Axiom check", "", "```", axioms, "```", ""]
    if failures:
        lines += ["## First failures", "", "```"]
        for f in failures[:20]:
            lines.append(repr(f)[:2000])
        lines += ["```", ""]
    with open(RESULTS, "w") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
