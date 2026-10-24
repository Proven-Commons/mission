#!/usr/bin/env python3
"""Findings F2 to F4 of the 2026-10-24 bar audit: archives the tar
pilot reads differently from Python's `tarfile`.

Builds each probe archive in a temporary directory, runs the pilot's
`manifest` command on it, and prints what the pilot extracts next to
what `tarfile` reads. Nothing is extracted to disk. Run it with the
path to a built `tar-pilot` executable:

    python3 -I probe_formats.py <tar>/.lake/build/bin/tar-pilot

Exit status is 0 when the probes ran, whatever they found.
"""

import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

LONG = "d/" + "n" * 120 + ".txt"


def one_file(fmt, name, data=b"x", typ=tarfile.REGTYPE, pax=None):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=fmt) as t:
        ti = tarfile.TarInfo(name)
        ti.size = len(data)
        ti.type = typ
        if pax:
            ti.pax_headers = pax
        t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def patch_header(raw, offset, new_bytes):
    """Overwrite bytes in the first header and fix its checksum."""
    hdr = bytearray(raw[:512])
    hdr[offset:offset + len(new_bytes)] = new_bytes
    hdr[148:156] = b" " * 8
    hdr[148:156] = ("%06o\0 " % sum(hdr)).encode()
    return bytes(hdr) + raw[512:]


def probes(work):
    yield ("GNU longname entry (Python, format=GNU)",
           one_file(tarfile.GNU_FORMAT, LONG))
    yield ("pax long path (Python's default format)",
           one_file(tarfile.PAX_FORMAT, LONG))
    yield ("pax path override",
           one_file(tarfile.PAX_FORMAT, "safe.txt",
                    pax={"path": "other/dir/real.txt"}))
    yield ("pax path override that climbs out",
           one_file(tarfile.PAX_FORMAT, "safe.txt",
                    pax={"path": "../../etc/cron.d/x"}))
    yield ("pax non-ASCII name",
           one_file(tarfile.PAX_FORMAT, "café/notes.txt"))
    # ustar: name field holds "file.txt", prefix field holds "p"*30 + "/" + ...
    split = one_file(tarfile.USTAR_FORMAT, "p" * 30 + "/" + "q" * 90 + "/file.txt")
    yield ("invalid UTF-8 in the prefix field, valid name",
           patch_header(split, 345, b"\xff"))
    yield ("invalid UTF-8 in the name field, valid prefix",
           patch_header(split, 0, b"\xff"))
    yield ("contiguous file, typeflag 7",
           one_file(tarfile.USTAR_FORMAT, "contig.bin", typ=tarfile.CONTTYPE))
    gnu_tar = shutil.which("tar")
    if gnu_tar:
        src = work / "src" / "d"
        src.mkdir(parents=True)
        (src / ("n" * 120 + ".txt")).write_bytes(b"x")
        out = work / "systar.tar"
        subprocess.run([gnu_tar, "cf", str(out), "d"], cwd=work / "src",
                       check=True)
        version = subprocess.run([gnu_tar, "--version"], capture_output=True,
                                 text=True).stdout.splitlines()[0]
        yield (f"system tar, default format ({version})", out.read_bytes())


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    exe = sys.argv[1]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for i, (label, raw) in enumerate(probes(work)):
            path = work / f"probe{i}.tar"
            path.write_bytes(raw)
            r = subprocess.run([exe, "manifest", str(path), "out"],
                               capture_output=True, text=True)
            with tarfile.open(path) as t:
                ref = [(m.name, m.type.decode()) for m in t.getmembers()
                       if not m.isdir()]
            print(f"## {label}")
            print(f"tarfile reads:   {ref}")
            print(f"tar-pilot exit:  {r.returncode}")
            for line in (r.stdout + r.stderr).strip().splitlines():
                print(f"tar-pilot says:  {line}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
