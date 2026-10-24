#!/usr/bin/env python3
"""Check a Proven Commons library repo against the verified bar.

The bar is in `playbook/verified-bar.md` of Proven-Commons/mission. This
script checks each item it can check by machine, and checks that the
items only a person can judge carry a valid approval by a reviewer who
did not write the specification. It never reports a person's judgment as
its own.

    python3 check.py [PROJECT_DIR] [--no-lean] [--offline] [--run-tests]
                     [--markdown FILE] [--json FILE]
    python3 check.py [PROJECT_DIR] --spec-hash

PROJECT_DIR defaults to the current directory. `--no-lean` skips the
proof check (`lake comparator --paranoid`). `--offline` skips asking
GitHub whether the recorded approval exists. `--run-tests` reruns the
project's differential tests first, so the record checked is fresh.
`--spec-hash` prints the
hash a reviewer approves, and what it covers, then exits.

Each item gets one status:
  PASS  checked and met
  FAIL  checked and not met
  OPEN  not met yet, which a project marked `in-progress` may be
  SKIP  not checked in this run

Exit status: 0 when nothing failed, 1 when something failed, 2 when the
project cannot be read at all. Needs Python 3.11 or later and nothing
outside the standard library.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Page sections. The first three are covered by the spec approval.
PROVED = "What is proved"
NOT_PROVED = "What is not proved"
TRUST = "What you must trust"
RECHECK = "Re-check"
APPROVED_SECTIONS = [PROVED, NOT_PROVED, TRUST]
TRUST_WORDS = ["kernel", "compiler", "runtime", "hardware"]
RECHECK_COMMAND = "lake comparator --paranoid"

# Lean features that let the code that runs differ from the code that
# was proved, or that skip the kernel. Matched outside comments and
# string literals. `sorry` is allowed in the challenge file only.
FORBIDDEN = [
    ("sorry", re.compile(r"\bsorry\b")),
    ("admit", re.compile(r"\badmit\b")),
    ("implemented_by", re.compile(r"\bimplemented_?[bB]y\b")),
    ("extern", re.compile(r"\bextern\b")),
    ("unsafe", re.compile(r"\b\w*[uU]nsafe\w*\b")),
    ("native evaluation",
     re.compile(r"\bnative_decide\b|\+\s*native\b|\bnative\s*:=\s*true\b"
                r"|\bofReduce(Bool|Nat)\b|\btrustCompiler\b")),
    ("skipKernelTC", re.compile(r"\bskipKernelTC\b")),
    ("axiom", re.compile(r"(?m)^[ \t]*(@\[[^\]]*\][ \t]*)?"
                         r"((private|protected|noncomputable)[ \t]+)*axiom\b")),
]

NOTATION = re.compile(r"(?m)^[ \t]*(@\[[^\]]*\][ \t]*)?((scoped|local)[ \t]+)?"
                      r"(notation|infixl?|infixr|prefix|postfix|macro|"
                      r"macro_rules|syntax|elab|elab_rules)\b")

ITEMS = {
    1: "Specification public, approved by a separate reviewer, and pinned",
    2: "Each public claim names the theorem behind it",
    3: "Proofs match the approved statements, in one command",
    4: "The code that runs is the code that was proved",
    5: "Differential tests ran, with the record in the repo",
    6: "The public page lists what is outside the proof",
    7: "The check runs in CI",
}


class ProjectError(Exception):
    pass


# Reading the project --------------------------------------------------

def read_text(path):
    """File contents with line endings normalised to `\\n`."""
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


def load_bar(root):
    path = root / "bar.toml"
    if not path.is_file():
        raise ProjectError("no bar.toml at the project root")
    try:
        bar = tomllib.loads(read_text(path))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ProjectError(f"bar.toml does not parse: {e}")
    shape = [
        ("project", dict), ("spec", dict), ("tests", dict),
        ("project.spec_authors", list), ("spec.files", list), ("spec.approval", list),
        ("trusted", list),
    ]
    for key, kind in shape:
        node = bar
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if node is not None and not isinstance(node, kind):
            raise ProjectError(f"bar.toml: {key} must be a {'table' if kind is dict else 'list'}")
    for key in ("spec.approval", "trusted"):
        parent, child = key.split(".") if "." in key else (None, key)
        entries = (bar.get(parent, {}) if parent else bar).get(child, [])
        if any(not isinstance(e, dict) for e in entries):
            raise ProjectError(f"bar.toml: each [[{key}]] entry must be a table")
    status = bar.get("project", {}).get("status")
    if status not in ("in-progress", "verified"):
        raise ProjectError('bar.toml: [project] status must be "in-progress" or "verified"')
    return bar


def load_comparator(root):
    path = root / "comparator.json"
    if not path.is_file():
        return None, "no comparator.json at the project root"
    try:
        cfg = json.loads(read_text(path))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"comparator.json does not parse: {e}"
    if not isinstance(cfg, dict):
        return None, "comparator.json is not a JSON object"
    return cfg, None


def module_path(module):
    return Path(*module.split(".")).with_suffix(".lean")


def sections(markdown):
    """Map each heading's text to the text under it, up to the next
    heading of the same or a higher level. Headings in code fences are
    ignored."""
    found, stack, fence = {}, [], False
    for line in markdown.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            body = []
            found.setdefault(m.group(2), body)
            stack.append((level, body))
            for _, outer in stack[:-1]:
                outer.append(line)
            continue
        for _, body in stack:
            body.append(line)
    return {k: "\n".join(v).strip() for k, v in found.items()}


def find_section(secs, title):
    """The section whose heading starts with `title`, ignoring case."""
    for heading, body in secs.items():
        if heading.lower().startswith(title.lower()):
            return body
    return None


def spec_hash(root, bar, read=None):
    """The hash a reviewer approves: the spec files, and the page
    sections that state what is proved, what is not, and what to trust.
    `read` maps a path in the project to its text; by default it reads
    the working tree."""
    read = read or (lambda rel: read_text(root / rel))
    files = bar.get("spec", {}).get("files", [])
    page = bar.get("project", {}).get("page", "README.md")
    h = hashlib.sha256()
    covered = []
    for rel in files:
        data = read(rel).replace("\r\n", "\n").encode("utf-8")
        h.update(f"file {rel}\n{hashlib.sha256(data).hexdigest()}\n".encode())
        covered.append(rel)
    secs = sections(read(page).replace("\r\n", "\n"))
    for title in APPROVED_SECTIONS:
        # Every section whose heading starts with the title, so a second
        # "What is proved" further down cannot add unreviewed claims.
        matching = [(head, body) for head, body in secs.items()
                    if head.lower().startswith(title.lower())]
        if not matching:
            raise ProjectError(f"{page} has no section '{title}'")
        for head, body in matching:
            body = "\n".join(line.rstrip() for line in body.split("\n"))
            h.update(f"section {head}\n{hashlib.sha256(body.encode()).hexdigest()}\n".encode())
            covered.append(f"{page}: {head}")
    return h.hexdigest(), covered


def strip_lean(src):
    """Lean source with comments and string and char literals blanked
    out, keeping every newline so line numbers stay right."""
    out, i, n = [], 0, len(src)
    ident = re.compile(r"[\w'!?₀-ₜᵢ-ᵪ]")
    char_lit = re.compile(r"'(\\(x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]+\}|.)|[^\\'\n])'")
    raw_lit = re.compile(r'r(#*)"')
    while i < n:
        prev = src[i - 1] if i else " "
        if src.startswith("/-", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("/-", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("-/", i):
                    depth, i = depth - 1, i + 2
                else:
                    out.append("\n" if src[i] == "\n" else "")
                    i += 1
            continue
        if src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        m = raw_lit.match(src, i)
        if m and not ident.match(prev):
            end = src.find('"' + m.group(1), m.end())
            end = n if end < 0 else end + 1 + len(m.group(1))
            out.append("\n" * src.count("\n", i, end) + '""')
            i = end
            continue
        if src[i] == '"':
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\n":
                    out.append("\n")
                i += 2 if src[i] == "\\" else 1
            out.append('""')
            i += 1
            continue
        if src[i] == "'" and not ident.match(prev):
            m = char_lit.match(src, i)
            if m:
                out.append("' '")
                i = m.end()
                continue
        out.append(src[i])
        i += 1
    return "".join(out)


def lean_files(root):
    """Project Lean sources: every `.lean` file outside hidden folders
    (`.lake`, `.git`, a checkout of this tool) and outside build output."""
    for path in sorted(root.rglob("*.lean")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts[0] in ("build", "lake-packages"):
            continue
        yield rel


def git_spec_authors(root, files):
    """Names and emails of everyone who committed to the spec files."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%an%x00%ae", "--", *files], cwd=root,
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return sorted({line for line in out.stdout.split("\n") if line})


def git_prefix(root):
    """Where the project sits inside its git repo, as `dir/` or ``."""
    try:
        out = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=root,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


class GitHub:
    """The two GitHub API reads the approval check needs."""

    def get(self, path, raw=False):
        headers = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                   "User-Agent": "proven-commons-bar"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        return body.decode("utf-8") if raw else json.loads(body)

    def reviews(self, owner, repo, number):
        return self.get(f"/repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100")

    def read(self, owner, repo, commit, path):
        quote = urllib.parse.quote
        return self.get(f"/repos/{owner}/{repo}/contents/{quote(path)}?ref={quote(commit)}", raw=True)


# The checks -----------------------------------------------------------

class Report:
    def __init__(self, in_progress):
        self.in_progress = in_progress
        self.rows = []

    def add(self, item, status, detail):
        self.rows.append({"item": item, "title": ITEMS[item], "status": status, "detail": detail})

    def unmet(self, item, detail):
        """A requirement that is not met: open while in progress, a
        failure once the project says it is verified."""
        self.add(item, "OPEN" if self.in_progress else "FAIL", detail)


def check_spec(root, bar, rep, offline, github):
    spec = bar.get("spec", {})
    files = spec.get("files", [])
    authors = [a.lower() for a in bar.get("project", {}).get("spec_authors", [])]
    missing = [f for f in files if not (root / f).is_file()]
    if not files or missing or not authors:
        rep.unmet(1, "bar.toml needs [spec] files that exist and [project] spec_authors"
                  + (f"; missing: {', '.join(missing)}" if missing else ""))
        return
    try:
        current, _ = spec_hash(root, bar)
    except (ProjectError, OSError) as e:
        rep.unmet(1, f"cannot hash the spec: {e}")
        return
    approvals = spec.get("approval", [])
    match = [a for a in approvals if a.get("sha256") == current]
    if not match:
        last = approvals[-1] if approvals else None
        why = (f"the spec changed after the last approval ({last.get('reviewer')}, {last.get('date')})"
               if last else "no approval recorded")
        rep.unmet(1, f"{why}; the current spec hash is {current}")
        return
    a = match[-1]
    reviewer = str(a.get("reviewer", ""))
    if not reviewer or reviewer.lower() in authors:
        rep.add(1, "FAIL", f"the approving reviewer '{reviewer}' is listed as a spec author")
        return
    committers = git_spec_authors(root, files) or []
    if any(re.search(rf"(^|[\x00+]){re.escape(reviewer.lower())}([\x00@]|$)", c.lower())
           for c in committers):
        rep.add(1, "FAIL", f"the approving reviewer '{reviewer}' committed to the spec files")
        return
    record = str(a.get("record", ""))
    said = f"approved by {reviewer} on {a.get('date')}, record {record or '(none)'}"
    if offline:
        rep.add(1, "SKIP", f"{said}; not confirmed on GitHub (--offline)")
        return
    m = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?", record)
    if not m:
        rep.add(1, "FAIL", f"{said}; the record must be the URL of the pull request the reviewer approved")
        return
    here = os.environ.get("GITHUB_REPOSITORY")
    if here and f"{m.group(1)}/{m.group(2)}".lower() != here.lower():
        rep.add(1, "FAIL", f"{said}; the pull request is not in {here}")
        return
    owner, repo, number = m.groups()
    prefix = git_prefix(root)
    try:
        reviews = github.reviews(owner, repo, number)
        mine = [r for r in reviews if r.get("state") == "APPROVED"
                and str((r.get("user") or {}).get("login", "")).lower() == reviewer.lower()]
        if not mine:
            rep.add(1, "FAIL", f"{said}; GitHub shows no approving review by {reviewer} on that pull request")
            return
        # The review must be of this exact text: hash the spec as it was
        # at the commit the reviewer approved.
        for r in mine:
            commit = r.get("commit_id")
            if commit:
                at = spec_hash(root, bar, lambda rel: github.read(owner, repo, commit, prefix + rel))[0]
                if at == current:
                    rep.add(1, "PASS", f"{said}; confirmed on GitHub at commit {commit[:12]}")
                    return
    except Exception as e:  # network, HTTP or JSON error: say so, do not guess
        rep.add(1, "FAIL", f"{said}; could not confirm it on GitHub: {e}")
        return
    rep.add(1, "FAIL", f"{said}; the text {reviewer} approved on GitHub is not the text this hash covers")


def backing(rep):
    """How the person-judged part of an item stands, from item 1."""
    row = next((r for r in rep.rows if r["item"] == 1), None)
    if row and row["status"] == "PASS":
        return "rests on the spec approval (item 1)"
    return "would rest on a spec approval (item 1), which is not in place"


def check_claims(page_secs, page, cmp_cfg, rep):
    proved = find_section(page_secs, PROVED) if page_secs is not None else None
    names = (cmp_cfg or {}).get("theorem_names") or []
    if proved is None:
        rep.unmet(2, f"{page} has no '{PROVED}' section")
        return
    if not names:
        rep.unmet(2, "comparator.json names no theorems")
        return
    absent = [t for t in names if not re.search(rf"(?<![\w.]){re.escape(t)}(?![\w.])", proved)]
    if absent:
        rep.unmet(2, f"'{PROVED}' does not name: {', '.join(absent)}")
    else:
        rep.add(2, "PASS", f"'{PROVED}' names all {len(names)} theorems; that the claims match "
                f"them {backing(rep)}")


def check_proofs(root, bar, cmp_cfg, cmp_err, rep, no_lean):
    problems = []
    if cmp_err:
        problems.append(cmp_err)
    else:
        for key in ("challenge_module", "solution_module", "theorem_names", "permitted_axioms"):
            if not cmp_cfg.get(key):
                problems.append(f"comparator.json has no {key}")
        extra = set(cmp_cfg.get("permitted_axioms") or []) - STANDARD_AXIOMS
        if extra:
            problems.append(f"comparator.json permits non-standard axioms: {', '.join(sorted(extra))}")
        if cmp_cfg.get("challenge_module"):
            challenge = module_path(cmp_cfg["challenge_module"]).as_posix()
            if challenge not in bar.get("spec", {}).get("files", []):
                problems.append(f"the challenge file {challenge} is not one of the approved spec files")
    toolchain = root / "lean-toolchain"
    pin = read_text(toolchain).strip() if toolchain.is_file() else ""
    if not re.fullmatch(r"leanprover/lean4:v\d+\.\d+\.\d+(-rc\d+)?", pin):
        problems.append(f"lean-toolchain must pin an exact Lean release, not '{pin or 'nothing'}'")
    if not (root / "lake-manifest.json").is_file():
        problems.append("no lake-manifest.json (lake comparator needs one)")
    if problems:
        rep.add(3, "FAIL", "; ".join(problems))
        return
    if no_lean:
        rep.add(3, "SKIP", f"configuration is valid; `{RECHECK_COMMAND}` not run (--no-lean)")
        return
    try:
        run = subprocess.run(["lake", "comparator", "--paranoid"], cwd=root,
                             capture_output=True, text=True, timeout=4 * 3600)
    except FileNotFoundError:
        rep.add(3, "FAIL", "`lake` is not on the PATH")
        return
    except subprocess.TimeoutExpired:
        rep.add(3, "FAIL", f"`{RECHECK_COMMAND}` did not finish in 4 hours")
        return
    tail = " / ".join(line.strip() for line in (run.stdout + run.stderr).strip().split("\n")[-3:])
    if run.returncode == 0:
        n = len(cmp_cfg["theorem_names"])
        rep.add(3, "PASS", f"`{RECHECK_COMMAND}` accepts all {n} theorems under every bundled kernel")
    else:
        rep.add(3, "FAIL", f"`{RECHECK_COMMAND}` exited {run.returncode}: {tail}")


def check_source(root, bar, cmp_cfg, rep):
    challenge = None
    if cmp_cfg and cmp_cfg.get("challenge_module"):
        challenge = module_path(cmp_cfg["challenge_module"])
    trusted = {(t.get("file"), t.get("feature")) for t in bar.get("trusted", [])}
    hits, allowed, notation, count = [], [], 0, 0
    for rel in lean_files(root):
        count += 1
        text = strip_lean(read_text(root / rel))
        for name, rx in FORBIDDEN:
            if name == "sorry" and rel == challenge:
                continue
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                where = f"{rel.as_posix()}:{line} {name}"
                (allowed if (rel.as_posix(), name) in trusted else hits).append(where)
        notation += len(NOTATION.findall(text))
    if count == 0:
        rep.add(4, "FAIL", "no Lean files found")
        return
    note = f"; {len(allowed)} listed as trusted in bar.toml" if allowed else ""
    if notation:
        note += f"; {notation} notation or macro declarations for the reviewer to read"
    if hits:
        shown = ", ".join(hits[:10]) + (f", and {len(hits) - 10} more" if len(hits) > 10 else "")
        rep.add(4, "FAIL", f"forbidden features: {shown}{note}")
    else:
        rep.add(4, "PASS", f"{count} Lean files, none uses a forbidden feature{note}; that entry "
                f"points call the proved functions {backing(rep)}")


def check_tests(root, bar, rep, run_tests=False):
    rel = bar.get("tests", {}).get("results", "tests/TEST-RESULTS.md")
    path = root / rel
    command = bar.get("tests", {}).get("command")
    if run_tests:
        if not command:
            rep.unmet(5, "bar.toml gives no [tests] command to run")
            return
        try:
            run = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                                 text=True, timeout=4 * 3600)
        except subprocess.TimeoutExpired:
            rep.unmet(5, f"`{command}` did not finish in 4 hours")
            return
        if run.returncode != 0:
            tail = " / ".join(l.strip() for l in (run.stdout + run.stderr).strip().split("\n")[-3:])
            rep.unmet(5, f"`{command}` exited {run.returncode}: {tail}")
            return
    if not path.is_file():
        rep.unmet(5, f"no test record at {rel}")
        return
    text = read_text(path)
    fields = {}
    for key in ("Oracle", "Seed", "Inputs", "Failures"):
        m = re.search(rf"(?m)^\s*[-*]\s*{key}:\s*(\S.*?)\s*$", text)
        fields[key] = m.group(1) if m else None
    missing = [k for k, v in fields.items() if v is None]
    if missing:
        rep.unmet(5, f"{rel} does not record: {', '.join(missing)}")
        return
    inputs = re.sub(r"[,_ ]", "", fields["Inputs"])
    failures = fields["Failures"].split()[0]
    if not inputs.isdigit() or int(inputs) == 0:
        rep.unmet(5, f"{rel}: Inputs must be a positive count, not '{fields['Inputs']}'")
    elif failures != "0":
        rep.unmet(5, f"{rel} records {fields['Failures']} failures")
    else:
        rep.add(5, "PASS", f"{int(inputs):,} inputs, seed {fields['Seed']}, 0 failures, "
                f"oracle {fields['Oracle']}")


def check_page(page_secs, page, bar, rep):
    if page_secs is None:
        rep.unmet(6, f"no page at {page}")
        return
    problems = []
    for title in APPROVED_SECTIONS + [RECHECK]:
        if find_section(page_secs, title) is None:
            problems.append(f"no '{title}' section")
    trust = (find_section(page_secs, TRUST) or "").lower()
    if trust:
        absent = [w for w in TRUST_WORDS if w not in trust]
        if absent:
            problems.append(f"'{TRUST}' does not mention: {', '.join(absent)}")
        for t in bar.get("trusted", []):
            if t.get("file") and t["file"].lower() not in trust:
                problems.append(f"'{TRUST}' does not name the trusted file {t['file']}")
    recheck = find_section(page_secs, RECHECK) or ""
    if recheck and RECHECK_COMMAND not in recheck:
        problems.append(f"'{RECHECK}' does not give `{RECHECK_COMMAND}`")
    test_cmd = bar.get("tests", {}).get("command")
    if recheck and test_cmd and test_cmd not in recheck:
        problems.append(f"'{RECHECK}' does not give the test command `{test_cmd}`")
    if problems:
        rep.unmet(6, "; ".join(problems))
    else:
        rep.add(6, "PASS", f"all sections present; that they are accurate {backing(rep)}")


def check_ci(root, rep):
    flows = root / ".github" / "workflows"
    files = sorted(flows.glob("*.y*ml")) if flows.is_dir() else []
    for f in files:
        text = read_text(f)
        if "verified-bar.yml" in text or RECHECK_COMMAND in text:
            rep.add(7, "PASS", f"{f.relative_to(root).as_posix()} runs the bar check; that the default "
                    "branch requires it is a repo setting this script cannot see")
            return
    rep.unmet(7, "no workflow in .github/workflows runs the bar check")


def check(root, no_lean=False, offline=False, github=None, run_tests=False):
    bar = load_bar(root)
    rep = Report(bar["project"]["status"] == "in-progress")
    cmp_cfg, cmp_err = load_comparator(root)
    page = bar.get("project", {}).get("page", "README.md")
    page_secs = sections(read_text(root / page)) if (root / page).is_file() else None
    check_spec(root, bar, rep, offline, github or GitHub())
    check_claims(page_secs, page, cmp_cfg, rep)
    check_proofs(root, bar, cmp_cfg, cmp_err, rep, no_lean)
    check_source(root, bar, cmp_cfg, rep)
    check_tests(root, bar, rep, run_tests)
    check_page(page_secs, page, bar, rep)
    check_ci(root, rep)
    return bar, rep


# Output ---------------------------------------------------------------

def verdict(bar, rep):
    statuses = [r["status"] for r in rep.rows]
    if "FAIL" in statuses:
        return "Does not meet the verified bar."
    if all(s == "PASS" for s in statuses):
        return "Meets the verified bar."
    if "OPEN" in statuses:
        return "In progress: no failures, some items still open. Do not call it verified."
    return "No failures, but some items were not checked in this run. Do not call it verified on this run."


def markdown(bar, rep, root):
    name = bar.get("project", {}).get("name", root.name)
    lines = [f"## Verified bar: {name}", "", f"**{verdict(bar, rep)}**",
             f"Project status in bar.toml: `{bar['project']['status']}`.", "",
             "| # | Item | Status | Detail |", "|---|------|--------|--------|"]
    for r in rep.rows:
        detail = r["detail"].replace("|", "\\|")
        lines.append(f"| {r['item']} | {r['title']} | {r['status']} | {detail} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--no-lean", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--run-tests", action="store_true")
    ap.add_argument("--spec-hash", action="store_true")
    ap.add_argument("--markdown")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    root = Path(args.project).resolve()
    try:
        if args.spec_hash:
            digest, covered = spec_hash(root, load_bar(root))
            print(digest)
            for c in covered:
                print(f"  covers {c}")
            return 0
        bar, rep = check(root, args.no_lean, args.offline, run_tests=args.run_tests)
    except (ProjectError, OSError, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    md = markdown(bar, rep, root)
    print(md)
    if args.markdown:
        with open(args.markdown, "a", encoding="utf-8") as f:
            f.write(md)
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"verdict": verdict(bar, rep), "status": bar["project"]["status"], "items": rep.rows},
            indent=2) + "\n")
    return 1 if any(r["status"] == "FAIL" for r in rep.rows) else 0


if __name__ == "__main__":
    sys.exit(main())
