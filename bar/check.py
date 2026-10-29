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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BAR_VERSION = "2"
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Limit for each long step (the proof check, the tests), in seconds. CI
# sets it so both steps fit inside the job's own limit.
STEP_TIMEOUT = int(os.environ.get("BAR_STEP_TIMEOUT_MINUTES", "120")) * 60

# Page sections the page must have.
PROVED = "What is proved"
NOT_PROVED = "What is not proved"
TRUST = "What you must trust"
RECHECK = "Re-check"
SECTIONS = [PROVED, NOT_PROVED, TRUST, RECHECK]
TRUST_WORDS = ["kernel", "compiler", "runtime", "hardware"]
RECHECK_COMMAND = "lake comparator --paranoid"

# Lean features that let the code that runs differ from the code that
# was proved, skip the kernel, or change what a statement means without
# changing its text. Matched outside comments and string literals.
# `sorry` is allowed in the challenge file only.
MODIFIERS = r"(@\[[^\]]*\][ \t]*)?((scoped|local|private|protected|noncomputable|public)[ \t]+)*"
FORBIDDEN = [
    ("sorry", re.compile(r"\bsorry\b")),
    ("admit", re.compile(r"\badmit\b")),
    ("implemented_by", re.compile(r"[iI]mplemented_?[bB]y\w*")),
    ("extern", re.compile(r"\bextern(Attr)?\b")),
    ("unsafe", re.compile(r"\b\w*[uU]nsafe\w*\b")),
    ("native evaluation",
     re.compile(r"\bnative_decide\b|\+\s*native\b|\bnative\s*:=\s*true\b"
                r"|\bofReduce(Bool|Nat)\b|\btrustCompiler\b")),
    ("skipKernelTC", re.compile(r"\bskipKernelTC\b")),
    ("axiom", re.compile(rf"(?m)^[ \t]*{MODIFIERS}axiom\b")),
    # Metaprogramming can do any of the above from inside a string the
    # scan cannot read, and notation can change what a statement says.
    ("import Lean", re.compile(r"(?m)^[ \t]*((public|meta|private)[ \t]+)*import[ \t]+"
                               r"([^\n]*[ \t])?(Lean|Lake)(\.[\w.]+)?(?=\s|$)")),
    ("notation or macro", re.compile(rf"(?m)^[ \t]*{MODIFIERS}"
                                     r"(notation\d?|infixl|infixr|infix|prefix|postfix|macro|syntax|elab)"
                                     r"(?=[ \t]*[:(\"]|[ \t]+\w)")),
    ("metaprogram", re.compile(r"\b(macro_rules|elab_rules|declare_syntax_cat|run_cmd|run_elab|run_meta"
                               r"|simproc|dsimproc|simproc_decl|dsimproc_decl|binder_predicate)\b")),
]

INSTANCE = re.compile(rf"(?m)^[ \t]*{MODIFIERS}instance\b|\battribute[ \t]*\[[^\]]*\binstance\b")

# Keys a lakefile.toml may use. Anything else, such as extra compiler or
# linker arguments, plugins or native libraries, can change the program
# without changing the Lean code.
LAKE_KEYS = {
    "package": {"name", "version", "description", "keywords", "homepage", "license",
                "licenseFiles", "readmeFile", "defaultTargets", "require", "lean_lib",
                "lean_exe", "leanOptions", "testDriver", "lintDriver"},
    "lean_lib": {"name", "srcDir", "roots", "globs", "libName", "leanOptions"},
    "lean_exe": {"name", "srcDir", "root", "exeName", "leanOptions"},
    "require": {"name", "git", "rev", "subDir", "scope", "version", "path", "source"},
}
RISKY_OPTION = re.compile(r"^(weak\.)?(debug|compiler|interpreter)\.")

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
        ("project.spec_authors", list), ("project.entry_points", list), ("spec.files", list),
        ("spec.code", list), ("spec.approval", list), ("tests.files", list), ("trusted", list),
        ("ci", dict),
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
    ignored. Repeated headings keep all their text, joined in order."""
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
            found.setdefault(m.group(2), []).append(body)
            stack.append((level, body))
            for _, outer in stack[:-1]:
                outer.append(line)
            continue
        for _, body in stack:
            body.append(line)
    return {k: "\n\n".join("\n".join(b).strip() for b in bodies).strip()
            for k, bodies in found.items()}


def find_section(secs, title):
    """The text of every section whose heading starts with `title`,
    ignoring case, or None when there is none."""
    bodies = [body for heading, body in secs.items() if heading.lower().startswith(title.lower())]
    return "\n\n".join(bodies) if bodies else None


def reviewed_files(bar):
    """Every file the approval covers, in a fixed order: the spec files,
    comparator.json, the entry points, the test files, and the page."""
    files = list(bar.get("spec", {}).get("files", []))
    files.append("comparator.json")
    files += bar.get("project", {}).get("entry_points", [])
    files += bar.get("tests", {}).get("files", [])
    files.append(bar.get("project", {}).get("page", "README.md"))
    return list(dict.fromkeys(files))


def spec_hash(root, bar, read=None):
    """The hash a reviewer approves: the spec files, comparator.json, the
    entry points people run, the test files, the whole public page (a
    claim anywhere on it is a public claim), and the list of code under
    proof. `read` maps a path in the project to its text; by default it
    reads the working tree."""
    read = read or (lambda rel: read_text(root / rel))
    h = hashlib.sha256()
    covered = []
    for rel in reviewed_files(bar):
        data = read(rel).replace("\r\n", "\n").encode("utf-8")
        h.update(f"file {rel}\n{hashlib.sha256(data).hexdigest()}\n".encode())
        covered.append(rel)
    code = sorted(str(c) for c in bar.get("spec", {}).get("code", []))
    h.update(("code " + " ".join(code) + "\n").encode())
    covered.append("bar.toml: [spec] code = " + ", ".join(code))
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
                step = 2 if src[i] == "\\" else 1
                out.append("\n" * src.count("\n", i, i + step))
                i += step
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
    """Project Lean sources: every `.lean` file except those under
    `.lake` (build output and dependencies) and `.git`."""
    for path in sorted(root.rglob("*.lean")):
        rel = path.relative_to(root)
        if any(part in (".lake", ".git") for part in rel.parts):
            continue
        yield rel


def lakefile_problems(root, trusted):
    """What in the Lake configuration could change the program."""
    if (root / "lakefile.lean").is_file():
        return ["lakefile.lean runs Lean code to configure the build; use lakefile.toml"]
    path = root / "lakefile.toml"
    if not path.is_file():
        return ["no lakefile.toml"]
    try:
        cfg = tomllib.loads(read_text(path))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        return [f"lakefile.toml does not parse: {e}"]
    problems = []

    def keys(table, kind, where):
        for key, value in table.items():
            if key not in LAKE_KEYS[kind] and ("lakefile.toml", key) not in trusted:
                problems.append(f"{where} sets `{key}`")
            if key == "leanOptions" and isinstance(value, dict):
                problems.extend(f"{where} sets the option `{o}`" for o in value
                                if RISKY_OPTION.match(o) and ("lakefile.toml", o) not in trusted)
            if key == "srcDir" and isinstance(value, str):
                p = Path(value)
                if p.is_absolute() or ".." in p.parts:
                    problems.append(f"{where} has a srcDir outside the project: {value}")

    keys(cfg, "package", "lakefile.toml")
    for kind in ("lean_lib", "lean_exe", "require"):
        for i, table in enumerate(cfg.get(kind, [])):
            if isinstance(table, dict):
                keys(table, kind, f"lakefile.toml [[{kind}]] {table.get('name', i)}")
    return problems


DEPS_SCRIPT = r"""
import Lean
import {challenge}

open Lean

def walk (thms specMods projMods code : List Name) : CoreM Unit := do
  let env ← getEnv
  let modOf (c : Name) : Option Name :=
    (env.getModuleIdxFor? c).map fun i => env.header.moduleNames[i.toNat]!
  for thm in thms do
    let some ci := env.find? thm | IO.println s!"{{thm}}\tmissing\t{{thm}}\t-"
    let mut seen : NameSet := {{}}
    let mut todo := ci.type.getUsedConstants.toList
    while !todo.isEmpty do
      let c := todo.head!
      todo := todo.tail!
      if seen.contains c then continue
      seen := seen.insert c
      let some m := modOf c | continue
      if code.contains c then
        IO.println s!"{{thm}}\tcode\t{{c}}\t{{m}}"
      else if specMods.contains m then
        if let some info := env.find? c then
          todo := todo ++ info.type.getUsedConstants.toList
          if let some v := info.value? then
            todo := todo ++ v.getUsedConstants.toList
          if let .inductInfo v := info then
            todo := todo ++ v.ctors
      else if projMods.contains m then
        IO.println s!"{{thm}}\tother\t{{c}}\t{{m}}"

def declared (challenge : Name) : CoreM Unit := do
  let env ← getEnv
  for (n, ci) in env.constants.toList do
    if let .thmInfo _ := ci then
      if !n.isInternalDetail then
        if let some i := env.getModuleIdxFor? n then
          if env.header.moduleNames[i.toNat]! == challenge then
            IO.println s!"{{n}}\tdeclared\t{{n}}\t{{challenge}}"

#eval walk {thms} {spec} {proj} {code}
#eval declared `{challenge}
"""


def lean_names(names):
    return "[" + ", ".join("`" + n for n in names) + "]"


def statement_dependencies(root, bar, cmp_cfg):
    """Run DEPS_SCRIPT in the built project, inside a sandbox, and return
    (problems, code_seen). A problem is a project constant that an
    approved statement depends on but that neither the spec files fix
    nor the code-under-proof list names."""
    code = [str(c) for c in bar.get("spec", {}).get("code", [])]
    thms = cmp_cfg["theorem_names"]
    modules = [r.with_suffix("").as_posix().replace("/", ".") for r in lean_files(root)]
    spec_files = set(bar.get("spec", {}).get("files", []))
    spec_mods = [m for r, m in zip(lean_files(root), modules) if r.as_posix() in spec_files]
    script = DEPS_SCRIPT.format(challenge=cmp_cfg["challenge_module"], thms=lean_names(thms),
                                spec=lean_names(spec_mods), proj=lean_names(modules),
                                code=lean_names(code))
    # The project's compiled files are loaded here, outside the sandbox
    # `lake comparator` uses, so give this its own: no network, nothing
    # writable but a fresh /tmp, and the project read-only.
    cmd = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
           "--ro-bind", str(root), str(root), "--unshare-all", "--die-with-parent",
           "--chdir", str(root), "lake", "env", "lean", "--stdin"]
    run = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=STEP_TIMEOUT)
    if run.returncode != 0:
        tail = " / ".join(l.strip() for l in (run.stdout + run.stderr).strip().split("\n")[-3:])
        return [f"could not walk the statements (run `lake build` first): {tail}"], {}
    problems, seen, declared = [], {t: [] for t in thms}, set()
    for line in run.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        thm, kind, const, mod = parts
        if kind == "code":
            seen.setdefault(thm, []).append(const)
        elif kind == "other":
            problems.append(f"{thm} depends on {const} ({mod}), which is neither in the spec files "
                            "nor listed as code under proof")
        elif kind == "missing":
            problems.append(f"{thm} is not in the challenge module")
        elif kind == "declared":
            declared.add(thm)
    extra = sorted(declared - set(thms))
    if extra:
        problems.append("comparator.json does not name these theorems of the challenge file: "
                        + ", ".join(extra))
    problems += [f"{t} mentions no code under proof, so it says nothing about the library"
                 for t, cs in seen.items() if not cs and not any(t in p for p in problems)]
    return problems, seen


def dependencies(root):
    """Names of the packages lake-manifest.json pins: code that is built
    into the project but not scanned, so the page must name it."""
    path = root / "lake-manifest.json"
    try:
        manifest = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return [p.get("name") for p in manifest.get("packages", []) if isinstance(p, dict) and p.get("name")]


def git_spec_authors(root, files):
    """Names and emails of everyone who committed to the spec files."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%an%x00%ae%n%cn%x00%ce", "--", *files], cwd=root,
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
    """Live repository authority, review and source checks."""

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

    def pull_request(self, owner, repo, number):
        return self.get(f"/repos/{owner}/{repo}/pulls/{number}")

    def is_maintainer(self, owner, repo, login):
        """Current repository write authority; no fixed roster or org token."""
        permission = self.get(f"/repos/{owner}/{repo}/collaborators/"
                              f"{urllib.parse.quote(login, safe='')}/permission")
        return isinstance(permission, dict) and permission.get("permission") in {"write", "maintain", "admin"}

    def reviews(self, owner, repo, number):
        found, page = [], 1
        while True:
            batch = self.get(f"/repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100&page={page}")
            found += batch
            if len(batch) < 100:
                return found
            page += 1

    def commit_logins(self, owner, repo, path, ref=None):
        """GitHub logins of the authors and committers of every commit to a path."""
        logins, page = set(), 1
        revision = f"&sha={urllib.parse.quote(ref, safe='')}" if ref else ""
        while True:
            batch = self.get(f"/repos/{owner}/{repo}/commits?path={urllib.parse.quote(path)}"
                             f"&per_page=100&page={page}{revision}")
            for c in batch:
                for who in ("author", "committer"):
                    login = (c.get(who) or {}).get("login")
                    if login:
                        logins.add(login.lower())
            if len(batch) < 100:
                return logins
            page += 1

    def required_checks(self, full_name):
        """The default branch and the status checks it requires, from
        both branch protection and rulesets."""
        branch = self.get(f"/repos/{full_name}")["default_branch"]
        found = set()
        info = self.get(f"/repos/{full_name}/branches/{urllib.parse.quote(branch)}")
        req = ((info.get("protection") or {}).get("required_status_checks") or {})
        found.update(req.get("contexts") or [])
        found.update(c.get("context") for c in req.get("checks") or [] if c.get("context"))
        for rule in self.get(f"/repos/{full_name}/rules/branches/{urllib.parse.quote(branch)}"):
            if rule.get("type") == "required_status_checks":
                found.update(c.get("context") for c in
                             (rule.get("parameters") or {}).get("required_status_checks", []) if c.get("context"))
        return branch, found

    def parent(self, full_name):
        """The repo a fork was made from, or None."""
        info = self.get(f"/repos/{full_name}")
        return (info.get("parent") or {}).get("full_name")

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
    missing = [f for f in reviewed_files(bar) if not (root / f).is_file()]
    if not files or missing or not authors:
        rep.unmet(1, "bar.toml needs [spec] files and [project] spec_authors, and every reviewed "
                  "file must exist" + (f"; missing: {', '.join(missing)}" if missing else ""))
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
    owner, repo, number = m.groups()
    prefix = git_prefix(root)
    try:
        here = os.environ.get("GITHUB_REPOSITORY")
        if here and f"{owner}/{repo}".lower() != here.lower():
            # CI in a contributor's fork runs with the fork's name.
            if (github.parent(here) or "").lower() != f"{owner}/{repo}".lower():
                rep.add(1, "FAIL", f"{said}; the pull request is not in {here} or the repo it was forked from")
                return
        try:
            maintainer = github.is_maintainer(owner, repo, reviewer)
        except urllib.error.HTTPError as e:
            if e.code != 403:
                raise
            rep.add(1, "SKIP", f"{said}; GitHub shows a collaborator's permission only to a token with "
                    f"push access to {owner}/{repo} (HTTP 403), so read item 1 from the library's CI run")
            return
        if not maintainer:
            rep.unmet(1, f"{said}; {reviewer} has no current write, maintain or admin access to {owner}/{repo}")
            return
        pull = github.pull_request(owner, repo, number)
        if str((pull.get("user") or {}).get("login", "")).lower() == reviewer.lower():
            rep.add(1, "FAIL", f"{said}; the reviewer authored the approval pull request")
            return
        head = (pull.get("head") or {}).get("sha")
        if not head:
            rep.add(1, "SKIP", f"{said}; GitHub did not return the pull request head")
            return
        for rel in files:
            if reviewer.lower() in github.commit_logins(owner, repo, prefix + rel, ref=head):
                rep.add(1, "FAIL", f"{said}; GitHub shows {reviewer} as an author of a commit to {rel}")
                return
        reviews = github.reviews(owner, repo, number)
        mine = [r for r in reviews
                if str((r.get("user") or {}).get("login", "")).lower() == reviewer.lower()
                and r.get("state") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}]
        latest = max(enumerate(mine), key=lambda pair: (
            pair[1].get("submitted_at") or "", pair[1].get("id") or 0, pair[0]))[1] if mine else None
        if not latest or latest.get("state") != "APPROVED":
            rep.unmet(1, f"{said}; GitHub shows no current approving review by {reviewer} on that pull request")
            return
        if latest.get("commit_id") != head:
            rep.unmet(1, f"{said}; the approving review is not on the pull request's current head")
            return
        mine = [latest]
        # The review must be of this exact text: hash the spec as it was
        # at the commit the reviewer approved.
        for r in mine:
            commit = r.get("commit_id")
            if not commit:
                continue
            at = spec_hash(root, bar, lambda rel: github.read(owner, repo, commit, prefix + rel))[0]
            # The reviewed pull request must be the one that records this
            # approval, so the review is of the spec, not of something else.
            then = tomllib.loads(github.read(owner, repo, commit, prefix + "bar.toml"))
            recorded = any(x.get("sha256") == current and str(x.get("reviewer", "")).lower() == reviewer.lower()
                           for x in then.get("spec", {}).get("approval", []) if isinstance(x, dict))
            if at == current and recorded:
                rep.add(1, "PASS", f"{said}; confirmed on GitHub at commit {commit[:12]}")
                return
    except Exception as e:  # network, HTTP or JSON error: say so, do not guess
        rep.add(1, "SKIP", f"{said}; could not confirm it on GitHub: {e}")
        return
    rep.unmet(1, f"{said}; the text {reviewer} approved on GitHub is not the text this hash covers")


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
        if not bar.get("spec", {}).get("code"):
            problems.append("bar.toml [spec] code names no code under proof")
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
                             capture_output=True, text=True, timeout=STEP_TIMEOUT)
    except FileNotFoundError:
        rep.add(3, "FAIL", "`lake` is not on the PATH")
        return
    except subprocess.TimeoutExpired:
        rep.add(3, "FAIL", f"`{RECHECK_COMMAND}` did not finish in {STEP_TIMEOUT // 60} minutes")
        return
    tail = " / ".join(line.strip() for line in (run.stdout + run.stderr).strip().split("\n")[-3:])
    if run.returncode != 0:
        only_sorry = "'sorryAx'" in (run.stdout + run.stderr) and "Illegal axiom" in (run.stdout + run.stderr) \
            and not re.search(r"Illegal axiom detected: '(?!sorryAx')", run.stdout + run.stderr)
        if only_sorry and rep.in_progress:
            rep.add(3, "OPEN", f"`{RECHECK_COMMAND}`: a proof is still `sorry`, which an in-progress "
                    "project may have")
        else:
            rep.add(3, "FAIL", f"`{RECHECK_COMMAND}` exited {run.returncode}: {tail}")
        return
    problems, _ = statement_dependencies(root, bar, cmp_cfg)
    if problems:
        rep.add(3, "FAIL", f"`{RECHECK_COMMAND}` passes, but " + "; ".join(problems))
        return
    n = len(cmp_cfg["theorem_names"])
    rep.add(3, "PASS", f"`{RECHECK_COMMAND}` accepts all {n} theorems under every bundled kernel, "
            "and each statement depends only on the spec files, the code under proof, and code "
            "outside the project")


def check_source(root, bar, cmp_cfg, rep):
    challenge = None
    if cmp_cfg and cmp_cfg.get("challenge_module"):
        challenge = module_path(cmp_cfg["challenge_module"])
    trusted = {(t.get("file"), t.get("feature")) for t in bar.get("trusted", [])}
    hits, allowed, instances, count = [], [], [], 0
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
        if rel != challenge:
            instances += [f"{rel.as_posix()}:{text.count(chr(10), 0, m.start()) + 1}"
                          for m in INSTANCE.finditer(text)]
    if count == 0:
        rep.add(4, "FAIL", "no Lean files found")
        return
    hits += [f"{p}" for p in lakefile_problems(root, trusted)]
    note = f"; {len(allowed)} listed as trusted in bar.toml" if allowed else ""
    if instances:
        note += (f"; instance declarations for the reviewer to read, since an instance can change "
                 f"what a statement means: {', '.join(instances[:10])}"
                 + (f", and {len(instances) - 10} more" if len(instances) > 10 else ""))
    if hits:
        shown = ", ".join(hits[:10]) + (f", and {len(hits) - 10} more" if len(hits) > 10 else "")
        only_sorry = all(h.endswith((" sorry", " admit")) for h in hits)
        if only_sorry and rep.in_progress:
            rep.add(4, "OPEN", f"unfinished proofs, which an in-progress project may have: {shown}{note}")
        else:
            rep.add(4, "FAIL", f"forbidden features: {shown}{note}")
    else:
        rep.add(4, "PASS", f"{count} Lean files, none uses a forbidden feature{note}; that the "
                f"entry points call the proved functions {backing(rep)}")


def record_fields(text):
    fields = {}
    for key in ("Oracle", "Seed", "Inputs", "Failures"):
        m = re.search(rf"(?m)^\s*[-*]\s*{key}:\s*(\S.*?)\s*$", text)
        fields[key] = m.group(1) if m else None
    return fields


def committed_text(root, rel):
    """The file as committed at HEAD: its text, False when git tracks no
    such file, or None when this is not a git checkout."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=root,
                             capture_output=True, text=True, timeout=60)
        if top.returncode != 0:
            return None
        out = subprocess.run(["git", "show", f"HEAD:{top.stdout.strip()}{rel}"], cwd=root,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.replace("\r\n", "\n") if out.returncode == 0 else False


def check_tests(root, bar, rep, run_tests=False):
    rel = bar.get("tests", {}).get("results", "tests/TEST-RESULTS.md")
    path = root / rel
    command = bar.get("tests", {}).get("command")
    committed = committed_text(root, rel) if run_tests else None
    if run_tests:
        if not command:
            rep.unmet(5, "bar.toml gives no [tests] command to run")
            return
        try:
                run = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                                 text=True, timeout=STEP_TIMEOUT)
        except subprocess.TimeoutExpired:
            rep.add(5, "FAIL", f"`{command}` did not finish in {STEP_TIMEOUT // 60} minutes")
            return
        if run.returncode != 0:
            tail = " / ".join(l.strip() for l in (run.stdout + run.stderr).strip().split("\n")[-3:])
            rep.add(5, "FAIL", f"`{command}` exited {run.returncode}: {tail}")
            return
    if not path.is_file():
        rep.unmet(5, f"no test record at {rel}")
        return
    fields = record_fields(read_text(path))
    if run_tests and committed is not None:
        if committed is False:
            rep.unmet(5, f"{rel} is not committed; the record must be in the repo, not only made in CI")
            return
        old = record_fields(committed)
        stale = [k for k in ("Seed", "Inputs", "Failures") if old.get(k) != fields.get(k)]
        if stale:
            rep.unmet(5, f"the committed {rel} differs from a fresh run in: {', '.join(stale)}")
            return
    missing = [k for k, v in fields.items() if v is None]
    if missing:
        rep.unmet(5, f"{rel} does not record: {', '.join(missing)}")
        return
    inputs = re.sub(r"[,_ ]", "", fields["Inputs"])
    failures = fields["Failures"].split()[0]
    if not inputs.isdigit() or int(inputs) == 0:
        rep.unmet(5, f"{rel}: Inputs must be a positive count, not '{fields['Inputs']}'")
    elif failures != "0":
        rep.add(5, "FAIL", f"{rel} records {fields['Failures']} failures")
    else:
        rep.add(5, "PASS", f"{int(inputs):,} inputs, seed {fields['Seed']}, 0 failures, "
                f"oracle {fields['Oracle']}")


def check_page(root, page_secs, page, bar, rep, page_text=None):
    if page_secs is None:
        rep.unmet(6, f"no page at {page}")
        return
    problems = []
    for title in SECTIONS:
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
        for dep in dependencies(root):
            if dep.lower() not in trust:
                problems.append(f"'{TRUST}' does not name the dependency {dep}")
    status = bar["project"]["status"]
    line = re.search(r"(?im)^[ \t>*_]*status[*_]*:[*_ \t]*(.+)$", page_text or "")
    said = line.group(1).lower() if line else None
    if said is None:
        problems.append("no `Status:` line on the page")
    elif status == "in-progress" and ("in progress" not in said or re.search(r"(?<!not )verified", said)):
        problems.append(f"the page's status line does not say in progress: '{line.group(1).strip()}'")
    elif status == "verified" and ("verified" not in said or "not" in said):
        problems.append(f"the page's status line does not say verified: '{line.group(1).strip()}'")
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


CALLS_BAR = re.compile(r"(?m)^[ \t]*(-[ \t]+)?uses:[ \t]*['\"]?"
                       r"(Proven-Commons/mission/|\./)\.github/workflows/verified-bar\.yml\b")


def github_repo(root):
    """owner/name of the repo on GitHub: from CI, or from the origin remote."""
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    try:
        out = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(\.git)?/?$", out.stdout.strip())
    return m.group(1) if out.returncode == 0 and m else None


def check_ci(root, bar, rep, offline, github):
    """A workflow at the top of the git repo, where GitHub runs them,
    that calls the verified-bar workflow, and a default branch that
    requires its check."""
    top = root
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                             capture_output=True, text=True, timeout=60)
        if out.returncode == 0:
            top = Path(out.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    flows = top / ".github" / "workflows"
    calling = [f for f in (sorted(flows.glob("*.y*ml")) if flows.is_dir() else [])
               if CALLS_BAR.search(read_text(f))]
    if not calling:
        rep.unmet(7, "no workflow in .github/workflows at the top of the repo calls the verified-bar workflow")
        return
    where = calling[0].relative_to(top).as_posix()
    wanted = bar.get("ci", {}).get("required_check", "bar / bar")
    repo = github_repo(root)
    if offline or not repo:
        rep.add(7, "SKIP", f"{where} calls the verified-bar workflow; the branch rule was not read "
                + ("(--offline)" if offline else "(no GitHub repo found)"))
        return
    try:
        branch, checks = github.required_checks(repo)
    except Exception as e:  # network, HTTP or JSON error: say so, do not guess
        rep.add(7, "SKIP", f"{where} calls the verified-bar workflow; could not read the branch rule: {e}")
        return
    if wanted in checks:
        rep.add(7, "PASS", f"{where} calls the verified-bar workflow, and {repo}'s default branch "
                f"{branch} requires the `{wanted}` check")
    else:
        rep.unmet(7, f"{where} calls the verified-bar workflow, but {repo}'s default branch {branch} "
                  f"does not require the `{wanted}` check")


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
    check_page(root, page_secs, page, bar, rep,
               read_text(root / page) if (root / page).is_file() else None)
    check_ci(root, bar, rep, offline, github or GitHub())
    return bar, rep


# Output ---------------------------------------------------------------

def verdict(bar, rep):
    statuses = [r["status"] for r in rep.rows]
    if "FAIL" in statuses:
        return "Does not meet the verified bar."
    if bar["project"]["status"] == "verified" and any(s != "PASS" for s in statuses):
        return "Marked verified, but not every item passed in this run."
    if all(s == "PASS" for s in statuses):
        return "Meets the verified bar."
    if "OPEN" in statuses:
        return "In progress: no failures, some items still open. Do not call it verified."
    return "No failures, but some items were not checked in this run. Do not call it verified on this run."


def markdown(bar, rep, root):
    name = bar.get("project", {}).get("name", root.name)
    lines = [f"## Verified bar {BAR_VERSION}: {name}", "", f"**{verdict(bar, rep)}**",
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
    if any(r["status"] == "FAIL" for r in rep.rows):
        return 1
    # A project that calls itself verified must pass every item, in every run.
    if bar["project"]["status"] == "verified" and any(r["status"] != "PASS" for r in rep.rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
