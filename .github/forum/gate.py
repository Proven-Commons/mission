#!/usr/bin/env python3
"""Forum gate: one GitHub Discussions board, its manifest, and who may post where.

GitHub Discussions has one permission for a whole board: anyone who can read it can start a thread in any
category except an Announcement one, and can reply anywhere unless the thread is locked. A board under the
forum standard (FORUM-STANDARD.md in the organisation's .github repository) describes itself in
.github/forum/board.toml: its categories, the contribution tiers, the named groups, and for each category
who may start a thread and who may reply. This script reads that manifest and does four jobs.

    python3 .github/forum/gate.py check              # manifest, forms and FORUM.md agree (no network)
    python3 .github/forum/gate.py checklist          # the categories an admin makes by hand, in order
    GH_TOKEN=... python3 .github/forum/gate.py audit  # the live categories against the manifest
    GH_TOKEN=... python3 .github/forum/gate.py labels # create the manifest's labels that are missing
    GH_TOKEN=... python3 .github/forum/gate.py event  # .github/workflows/forum.yml runs this on a new post

On a new thread or reply in a gated category, when the author is not eligible:

  - a new thread is moved to the category's open fallback (the Floor), and the gate replies to say why;
  - a reply is hidden (minimised, never deleted: anyone can still expand and read it), and the gate replies
    to say why and links the open thread where anyone can answer.

When an eligible author opens a thread in a category with `floor = true`, the gate opens a companion thread
in the fallback category, so that everyone who may read the room has a place to answer it. Nothing is ever
deleted: the record stays whole, and every action the gate takes is a reply in the thread itself.

Standard library only (Python 3.11 or later, for tomllib). The same file runs on every board in all three
organisations; a board differs only in its manifest, its forms and its FORUM.md.
"""
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request

VERSION = '1.0'
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MANIFEST = os.path.join(HERE, 'board.toml')
FORMS = os.path.join(ROOT, '.github', 'DISCUSSION_TEMPLATE')
FORUM_MD = os.path.join(ROOT, 'FORUM.md')

EVERYONE = 'everyone'
FORMATS = {'open': 'Open-ended discussion', 'qa': 'Question / Answer', 'announcement': 'Announcement', 'poll': 'Poll'}
ASSOCIATIONS = {'OWNER', 'MEMBER', 'COLLABORATOR', 'CONTRIBUTOR', 'FIRST_TIME_CONTRIBUTOR', 'FIRST_TIMER', 'NONE'}
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
LOGIN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?')
EMOJI = re.compile(r':[a-z0-9_+-]+:')
COLOR = re.compile(r'[0-9a-fA-F]{6}')
GATE_BOT = 'github-actions'            # the login GitHub shows for posts made with a workflow's GITHUB_TOKEN
FLOOR_MARK = re.compile(r'<!-- forum-gate floor: (https://github\.com/\S+) -->')
MAX_CATEGORIES = 25                    # GitHub's limit per repository or organisation


# ---------------------------------------------------------------- the manifest

def load(path=MANIFEST):
    with open(path, 'rb') as f:
        return tomllib.load(f)


def categories(m):
    return {c.get('slug'): c for c in m.get('categories', [])}


def tier_ids(m):
    return [t.get('id') for t in m.get('tiers', [])]


def rule_ok(m, rule):
    """An access rule is 'everyone', a tier id, or 'group:<name>'."""
    if rule == EVERYONE or rule in tier_ids(m):
        return True
    return isinstance(rule, str) and rule.startswith('group:') and rule[6:] in m.get('groups', {})


def validate(m):
    """Every error in the manifest, as a list of plain sentences; an empty list means it is sound."""
    errs = []
    if m.get('version') != 1:
        errs.append('version must be 1')
    if m.get('board') not in ('main', 'internal'):
        errs.append('board must be "main" or "internal"')
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9._-]+', str(m.get('repository', ''))):
        errs.append('repository must be owner/name')
    if not isinstance(m.get('public'), bool):
        errs.append('public must be true or false (can anyone without access read the board?)')
    if not m.get('name'):
        errs.append('name is required')

    gate = m.get('gate', {})
    if gate.get('mode', 'enforce') not in ('enforce', 'report', 'off'):
        errs.append('gate.mode must be enforce, report or off')
    if not all(isinstance(o, str) and o for o in gate.get('count_orgs', [])):
        errs.append('gate.count_orgs must be a list of organisation names')
    if 'signature' in gate:
        try:
            re.compile(gate['signature'])
        except (re.error, TypeError) as e:
            errs.append(f'gate.signature is not a valid regular expression ({e})')
    for x in gate.get('signature_exempt', []):
        if x not in ASSOCIATIONS and not (isinstance(x, str) and x.startswith('group:') and x[6:] in m.get('groups', {})):
            errs.append(f'gate.signature_exempt: {x!r} is neither one of {sorted(ASSOCIATIONS)} nor group:<name>')

    groups = m.get('groups', {})
    for g, members in groups.items():
        if not SLUG.fullmatch(g):
            errs.append(f'group {g!r}: name must be lower-case words joined by hyphens')
        if not isinstance(members, list) or not all(isinstance(x, str) and LOGIN.fullmatch(x) for x in members):
            errs.append(f'group {g!r}: must be a list of GitHub logins')
        elif len({x.lower() for x in members}) != len(members):
            errs.append(f'group {g!r}: a login is listed twice')

    seen = set()
    for i, t in enumerate(m.get('tiers', [])):
        tid = t.get('id')
        where = f'tier {tid or i}'
        if not isinstance(tid, str) or not SLUG.fullmatch(tid) or tid == EVERYONE:
            errs.append(f'{where}: id must be lower-case words joined by hyphens, and not "everyone"')
        if tid in seen:
            errs.append(f'{where}: id used twice')
        seen.add(tid)
        if not t.get('name'):
            errs.append(f'{where}: name is required')
        n = t.get('merged_prs')
        if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n < 1):
            errs.append(f'{where}: merged_prs must be a whole number of at least 1')
        if not set(t.get('associations', [])) <= ASSOCIATIONS:
            errs.append(f'{where}: associations may hold only {sorted(ASSOCIATIONS)}')
        for g in t.get('groups', []):
            if g not in groups:
                errs.append(f'{where}: group {g!r} is not defined under [groups]')
        if not (n or t.get('associations') or t.get('groups')):
            errs.append(f'{where}: needs at least one way in (merged_prs, associations or groups)')
        if n and not gate.get('count_orgs'):
            errs.append(f'{where}: counts merged pull requests, so gate.count_orgs must name the organisations')

    cats = m.get('categories', [])
    if not cats:
        errs.append('the board has no categories')
    if len(cats) > MAX_CATEGORIES:
        errs.append(f'{len(cats)} categories: GitHub allows at most {MAX_CATEGORIES}')
    by_slug, names = {}, set()
    for c in cats:
        s = c.get('slug')
        if not isinstance(s, str) or not SLUG.fullmatch(s):
            errs.append(f'category {c.get("name")!r}: slug must be lower-case words joined by hyphens')
            continue
        if s in by_slug:
            errs.append(f'category {s}: slug used twice')
        by_slug[s] = c
        if not c.get('name') or c['name'] in names:
            errs.append(f'category {s}: name missing or used twice')
        names.add(c.get('name'))
        if not EMOJI.fullmatch(str(c.get('emoji', ''))):
            errs.append(f'category {s}: emoji must be a shortcode such as :speech_balloon:')
        if c.get('format') not in FORMATS:
            errs.append(f'category {s}: format must be one of {sorted(FORMATS)}')
        if not c.get('section'):
            errs.append(f'category {s}: section is required')
        if not c.get('description'):
            errs.append(f'category {s}: description is required')
        for k in ('form', 'floor', 'agents', 'lock'):
            if k in c and not isinstance(c[k], bool):
                errs.append(f'category {s}: {k} must be true or false')
    for s, c in by_slug.items():
        start, reply = c.get('start', EVERYONE), c.get('reply', EVERYONE)
        for k, rule in (('start', start), ('reply', reply)):
            if not rule_ok(m, rule):
                errs.append(f'category {s}: {k} = {rule!r} is not "everyone", a tier id or group:<name>')
        gated = start != EVERYONE or reply != EVERYONE or c.get('agents') is False
        fb = c.get('fallback')
        if gated and not fb:
            errs.append(f'category {s}: a gated category needs a fallback, an open category for everyone else')
        if fb:
            f = by_slug.get(fb)
            if f is None:
                errs.append(f'category {s}: fallback {fb!r} is not a category on this board')
            elif fb == s or f.get('start', EVERYONE) != EVERYONE or f.get('reply', EVERYONE) != EVERYONE \
                    or f.get('format') not in ('open', 'qa') or f.get('agents') is False:
                errs.append(f'category {s}: fallback {fb!r} must be a different open category that anyone may post in')
        if c.get('floor') and not fb:
            errs.append(f'category {s}: floor = true needs a fallback to open the companion thread in')

    for lab in m.get('labels', []):
        if not lab.get('name') or not COLOR.fullmatch(str(lab.get('color', ''))):
            errs.append(f'label {lab.get("name")!r}: needs a name and a six-digit hex colour')
    return errs


def check(root=ROOT, m=None):
    """The offline check CI runs on every change: the manifest is sound, every form belongs to a category
    that says it has one (and the other way round), and FORUM.md names every category and, on a public
    board, every member of every group, so nobody holds a gated seat that the public can't see."""
    if m is None:
        m = load(os.path.join(root, '.github', 'forum', 'board.toml'))
    errs = validate(m)
    cats = categories(m)
    forms_dir = os.path.join(root, '.github', 'DISCUSSION_TEMPLATE')
    files = sorted(f for f in os.listdir(forms_dir) if f.endswith(('.yml', '.yaml'))) if os.path.isdir(forms_dir) else []
    for f in files:
        slug = f.rsplit('.', 1)[0]
        c = cats.get(slug)
        if c is None:
            errs.append(f'form {f}: no category with slug {slug!r}, so GitHub would never show it')
        elif not c.get('form'):
            errs.append(f'form {f}: category {slug} does not say form = true')
        text = open(os.path.join(forms_dir, f), encoding='utf-8').read()
        if not re.search(r'^body:\s*$', text, re.M):
            errs.append(f'form {f}: has no top-level body:')
        # the two YAML slips that make GitHub drop a form without a word: an unquoted value holding ': ',
        # and a bare yes/no/true/false option, which YAML reads as a boolean
        for n, line in enumerate(text.split('\n'), 1):
            v = re.match(r'\s+(?:label|description|placeholder|title|value):\s+(.*)$', line)
            if v and not v.group(1).startswith(('"', "'", '|', '>')) and (': ' in v.group(1) or ' #' in v.group(1)):
                errs.append(f'form {f}, line {n}: quote this value, it holds ": " or " #"')
            if re.fullmatch(r'\s+-\s+(?i:yes|no|true|false|on|off)\s*', line):
                errs.append(f'form {f}, line {n}: quote this option, or YAML reads it as true/false')
        ids = re.findall(r'^\s+id:\s*(\S+)\s*$', text, re.M)
        if len(ids) != len(set(ids)):
            errs.append(f'form {f}: an id is used twice')
    for slug, c in cats.items():
        if c.get('form') and not any(f.rsplit('.', 1)[0] == slug for f in files):
            errs.append(f'category {slug}: form = true but .github/DISCUSSION_TEMPLATE/{slug}.yml is missing')
    forum_md = os.path.join(root, 'FORUM.md')
    if not os.path.exists(forum_md):
        errs.append('FORUM.md is missing')
    else:
        doc = open(forum_md, encoding='utf-8').read()
        for slug in cats:
            if f'`{slug}`' not in doc:
                errs.append(f'FORUM.md does not list the category `{slug}`')
        if m.get('public'):
            for g, members in m.get('groups', {}).items():
                for who in members:
                    if not re.search(rf'@{re.escape(who)}\b', doc, re.I):
                        errs.append(f'FORUM.md does not name @{who}, a member of group {g} (a public board names every seat)')
    return errs


ASSOCIATION_WORDS = {'OWNER': 'owner', 'MEMBER': 'organisation member', 'COLLABORATOR': 'collaborator',
                     'CONTRIBUTOR': 'earlier contributor to this repository', 'FIRST_TIME_CONTRIBUTOR': 'first-time contributor',
                     'FIRST_TIMER': 'first-timer', 'NONE': 'anyone'}


def describe(m, rule):
    """An access rule in words, for the checklist and the gate's replies."""
    if rule == EVERYONE:
        return 'everyone'
    if rule.startswith('group:'):
        return f'members of the {rule[6:]} group'
    t = next(t for t in m['tiers'] if t['id'] == rule)
    ways = []
    if t.get('merged_prs'):
        n = t['merged_prs']
        ways.append(f'{n} merged pull request{"s" if n > 1 else ""} in {" or ".join(m["gate"]["count_orgs"])}')
    ways += [f'a seat in the {g} group' for g in t.get('groups', [])]
    who = [ASSOCIATION_WORDS[a] for a in t.get('associations', [])]
    if who:
        ways.append(who[0] if len(who) == 1 else ', '.join(who[:-1]) + ' or ' + who[-1])
    if m['tiers'].index(t) < len(m['tiers']) - 1:
        ways.append('a higher tier')
    return f'{t["name"]} ({", or ".join(ways)})'


def checklist(m):
    """The setup list an admin follows in GitHub's settings: categories cannot be made through the API."""
    out = [f'# {m["name"]}: categories for {m["repository"]}', '',
           'Discussions → the pencil next to Categories. Make the sections first, then each category below in '
           'order, with exactly this slug (a form only loads when the slug matches its file name). Delete any '
           'default category not listed.', '']
    sections = []
    for c in m['categories']:
        if c['section'] not in sections:
            sections.append(c['section'])
    for sec in sections:
        out.append(f'## {sec}')
        for c in (c for c in m['categories'] if c['section'] == sec):
            line = f'- [ ] {c["emoji"]} **{c["name"]}** `{c["slug"]}`, {FORMATS[c["format"]]}: {c["description"]}'
            extras = []
            if c.get('form'):
                extras.append('has a form')
            start, reply = c.get('start', EVERYONE), c.get('reply', EVERYONE)
            if start != EVERYONE and start == reply:
                extras.append('threads and replies: ' + describe(m, start))
            else:
                if start != EVERYONE:
                    extras.append('threads: ' + describe(m, start))
                if reply != EVERYONE:
                    extras.append('replies: ' + describe(m, reply))
            if c.get('agents') is False:
                extras.append('people only')
            if extras:
                line += ' *(' + '; '.join(extras) + ')*'
            out.append(line)
        out.append('')
    empty = [g for g, members in m.get('groups', {}).items() if not members]
    if empty:
        out.append('Groups with nobody in them yet (fill them by pull request, in board.toml and FORUM.md together): '
                   + ', '.join(empty))
    return '\n'.join(out)


# ---------------------------------------------------------------- GitHub

class GitHub:
    """The few calls the gate makes. The workflow's GITHUB_TOKEN is enough on a public board; a private
    organisation that counts merged pull requests across private repositories sets FORUM_SEARCH_TOKEN."""

    def __init__(self, token, search_token=None):
        self.token, self.search_token = token, search_token or token

    def _call(self, method, url, body=None, token=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': f'bearer {token or self.token}', 'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json', 'User-Agent': f'forum-gate/{VERSION}'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raise SystemExit(f'forum-gate: GitHub answered HTTP {e.code} to {method} {url.split("?")[0]}')
        except (urllib.error.URLError, TimeoutError) as e:
            raise SystemExit(f'forum-gate: could not reach GitHub ({e})')

    def graphql(self, query, variables):
        out = self._call('POST', 'https://api.github.com/graphql', {'query': query, 'variables': variables})
        if out.get('errors'):
            raise SystemExit('forum-gate: ' + '; '.join(str(x.get('message')) for x in out['errors']))
        return out['data']

    def rest(self, method, path, body=None):
        return self._call(method, 'https://api.github.com' + path, body)

    def merged_prs(self, login, orgs):
        """How many pull requests this author has had merged in these organisations (repositories the token
        can see: every public one, and private ones only with a token that reaches them)."""
        author = f'app/{login[:-5]}' if login.endswith('[bot]') else login
        q = f'is:pr is:merged author:{author} ' + ' '.join(f'org:{o}' for o in orgs)
        url = 'https://api.github.com/search/issues?per_page=1&q=' + urllib.parse.quote(q)
        return int(self._call('GET', url, token=self.search_token).get('total_count', 0))


CATEGORY_Q = """query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id hasDiscussionsEnabled
    discussionCategories(first: 25) { nodes { id slug name emoji description isAnswerable } }
  }
}"""
MOVE = """mutation($id: ID!, $cat: ID!) {
  updateDiscussion(input: {discussionId: $id, categoryId: $cat}) { discussion { url } }
}"""
COMMENT = """mutation($id: ID!, $body: String!, $reply: ID) {
  addDiscussionComment(input: {discussionId: $id, body: $body, replyToId: $reply}) { comment { url } }
}"""
HIDE = """mutation($id: ID!) {
  minimizeComment(input: {subjectId: $id, classifier: OFF_TOPIC}) { minimizedComment { isMinimized } }
}"""
CREATE = """mutation($repo: ID!, $cat: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {repositoryId: $repo, categoryId: $cat, title: $title, body: $body}) { discussion { url } }
}"""
LOCK = """mutation($id: ID!) { lockLockable(input: {lockableId: $id}) { lockedRecord { locked } } }"""
THREAD_OF = """query($id: ID!) {
  node(id: $id) { ... on DiscussionComment { replyTo { id } } }
}"""
GATE_NOTES = """query($id: ID!) {
  node(id: $id) { ... on Discussion { comments(first: 20) { nodes { body author { login } } } } }
}"""


# ---------------------------------------------------------------- who may post

def in_group(m, group, login):
    return login.lower() in {x.lower() for x in m.get('groups', {}).get(group, [])}


class Author:
    """One author, with the tier they reach worked out at most once (it may cost one search)."""

    def __init__(self, m, api, login, association, bot):
        self.m, self.api = m, api
        self.login, self.association, self.bot = login, association or 'NONE', bot
        self._level, self.prs = None, None

    def merged(self):
        if self.prs is None:
            self.prs = self.api.merged_prs(self.login, self.m['gate']['count_orgs'])
        return self.prs

    def level(self):
        """0 for everyone; i + 1 for the i-th tier. Tiers are tried from the top, and the cheap tests
        (association, groups) come before the search."""
        if self._level is None:
            self._level = 0
            tiers = self.m.get('tiers', [])
            for i in reversed(range(len(tiers))):
                t = tiers[i]
                if self.association in t.get('associations', []) or \
                        any(in_group(self.m, g, self.login) for g in t.get('groups', [])) or \
                        (t.get('merged_prs') and self.merged() >= t['merged_prs']):
                    self._level = i + 1
                    break
        return self._level

    def may(self, rule):
        if rule == EVERYONE:
            return True
        if rule.startswith('group:'):
            return in_group(self.m, rule[6:], self.login)
        return self.level() >= tier_ids(self.m).index(rule) + 1


def problems(m, cat, author, kind, body):
    """Why this author may not post this here: a list of (what, sentence) pairs, where what is 'access'
    (the wrong tier or group, or an agent in a people-only room) or 'signature'. Empty means they may."""
    out = []
    rule = cat.get(kind, EVERYONE)
    if author.bot and cat.get('agents') is False:
        out.append(('access', f'Only people post in **{cat["name"]}**, because a named person answers for what is '
                    'decided there. Agents can read it, and can take part in the open thread for everyone.'))
    elif not author.may(rule):
        verb = 'Starting threads' if kind == 'start' else 'Replying'
        line = f'{verb} in **{cat["name"]}** is open to {describe(m, rule)}.'
        if author.prs is not None:
            line += f' GitHub counts {author.prs} merged pull request{"" if author.prs == 1 else "s"} by @{author.login}.'
        out.append(('access', line))
    gate = m.get('gate', {})
    exempt = gate.get('signature_exempt', [])
    if gate.get('signature') and author.association not in exempt \
            and not any(x.startswith('group:') and in_group(m, x[6:], author.login) for x in exempt) \
            and not re.search(gate['signature'], body or ''):
        out.append(('signature', 'Every post on this board ends with its author\'s sign-off name, and this one does '
                    'not. Edit it to add the sign-off' + (', and a maintainer will show it again.' if kind == 'reply' else '.')))
    return out


# ---------------------------------------------------------------- the event

def safe(text):
    """A title inside a post: no @mention fires and no HTML is read, so a title can't ping or inject."""
    return text.replace('@', '@​').replace('<', '&lt;').replace('\n', ' ')[:200]


def floor_link(api, discussion_id):
    data = api.graphql(GATE_NOTES, {'id': discussion_id})
    for c in (((data or {}).get('node') or {}).get('comments') or {}).get('nodes', []):
        if (c.get('author') or {}).get('login') == GATE_BOT:
            hit = FLOOR_MARK.search(c.get('body') or '')
            if hit:
                return hit.group(1)
    return None


def handle(m, event_name, ev, api, log=print):
    """Act on one webhook event. Returns the list of actions taken, for the log and the tests."""
    done = []
    mode = m.get('gate', {}).get('mode', 'enforce')
    action, d = ev.get('action'), ev.get('discussion') or {}
    if mode == 'off' or action != 'created':
        return done
    if event_name == 'discussion':
        kind, post = 'start', d
    elif event_name == 'discussion_comment':
        kind, post = 'reply', ev.get('comment') or {}
    else:
        return done
    user = post.get('user') or {}
    login = user.get('login', '')
    if login in (GATE_BOT, GATE_BOT + '[bot]'):
        return done
    slug = (d.get('category') or {}).get('slug')
    cats = categories(m)
    cat = cats.get(slug)
    if cat is None:
        log(f'::warning::category {slug!r} is not in .github/forum/board.toml; run the audit')
        return done
    if cat.get('start', EVERYONE) == EVERYONE and cat.get('reply', EVERYONE) == EVERYONE \
            and cat.get('agents') is not False and not m.get('gate', {}).get('signature') \
            and not (kind == 'start' and (cat.get('floor') or cat.get('lock'))):
        return done        # an open category: nothing to check, no search spent

    author = Author(m, api, login, post.get('author_association'), user.get('type') == 'Bot')
    why = problems(m, cat, author, kind, post.get('body'))
    repo = m['repository']
    owner, name = repo.split('/')
    fb = cat.get('fallback')
    fb_url = f'https://github.com/{repo}/discussions/categories/{fb}' if fb else None

    if not why:
        if kind == 'start' and cat.get('floor'):
            meta = api.graphql(CATEGORY_Q, {'owner': owner, 'name': name})['repository']
            fb_id = {c['slug']: c['id'] for c in meta['discussionCategories']['nodes']}.get(fb)
            if fb_id is None:
                log(f'::warning::fallback category {fb!r} does not exist yet; no floor opened')
            else:
                title = d.get('title', '')
                people = ', people only' if cat.get('agents') is False else ''
                body = (f'This is the open floor for **{safe(title)}** in {cat["name"]}: {d.get("html_url")}\n\n'
                        f'Replies there are open to {describe(m, cat.get("reply", EVERYONE))}{people}. Anyone can '
                        'read that thread, and anyone can answer it here. What is said here is part of the record.')
                url = api.graphql(CREATE, {'repo': meta['id'], 'cat': fb_id, 'title': ('Floor: ' + title)[:250],
                                           'body': body})['createDiscussion']['discussion']['url']
                api.graphql(COMMENT, {'id': d['node_id'], 'reply': None, 'body':
                                      f'Anyone can answer this thread on its open floor: {url}\n\n'
                                      f'<!-- forum-gate floor: {url} -->'})
                done.append(('floor', url))
        if kind == 'start' and cat.get('lock'):
            api.graphql(LOCK, {'id': d['node_id']})
            done.append(('lock', d.get('html_url')))
        return done

    enforce = mode == 'enforce'
    access = any(what == 'access' for what, _ in why)
    where = floor_link(api, d['node_id']) if kind == 'reply' else None
    elsewhere = f'the open floor for this thread: {where}' if where else f'**{fb}**: {fb_url}' if fb else None
    lines = [f'@{login}, thank you for posting.', ''] + [f'- {w}' for _, w in why] + ['']
    if not enforce:
        lines.append('The gate is in report mode, so nothing was hidden or moved.'
                     + (f' Please continue on {elsewhere}.' if access and elsewhere else ''))
    elif kind == 'start' and access and fb:
        meta = api.graphql(CATEGORY_Q, {'owner': owner, 'name': name})['repository']
        fb_id = {c['slug']: c['id'] for c in meta['discussionCategories']['nodes']}.get(fb)
        if fb_id:
            api.graphql(MOVE, {'id': d['node_id'], 'cat': fb_id})
            done.append(('move', fb))
            lines.append(f'The forum gate has moved this thread to **{fb}**, where anyone can take part. '
                         'Nothing was deleted.')
        else:
            log(f'::warning::fallback category {fb!r} does not exist yet; the thread stays where it is')
    elif kind == 'reply':
        api.graphql(HIDE, {'id': post['node_id']})
        done.append(('hide', post.get('html_url')))
        lines.append('The forum gate has hidden this reply. It is not deleted: anyone can expand it and read it'
                     + (f', and you can post it on {elsewhere}.' if access and elsewhere else '.'))
    lines += ['', f'The rules and how to reach each tier are in [FORUM.md](https://github.com/{repo}/blob/HEAD/FORUM.md). '
              'To appeal, reply here or in the moderation log; a moderator who did not take the action reviews it.']
    reply_to = None
    if kind == 'reply':
        parent = (api.graphql(THREAD_OF, {'id': post['node_id']}).get('node') or {}).get('replyTo')
        reply_to = (parent or {}).get('id') or post['node_id']
    api.graphql(COMMENT, {'id': d['node_id'], 'reply': reply_to, 'body': '\n'.join(lines)})
    done.append(('reply', login))
    return done


# ---------------------------------------------------------------- the commands

def audit(m, api):
    """The live board against the manifest: what is missing, what differs, and what is extra."""
    owner, name = m['repository'].split('/')
    meta = api.graphql(CATEGORY_Q, {'owner': owner, 'name': name})['repository']
    if not meta['hasDiscussionsEnabled']:
        return [f'Discussions is off on {m["repository"]}']
    live = {c['slug']: c for c in meta['discussionCategories']['nodes']}
    out = []
    for c in m['categories']:
        got = live.get(c['slug'])
        if got is None:
            out.append(f'missing: {c["name"]} `{c["slug"]}`')
            continue
        for k, want, have in (('name', c['name'], got['name']), ('emoji', c['emoji'], got['emoji']),
                              ('description', c['description'], got['description'] or ''),
                              ('answerable', c['format'] == 'qa', got['isAnswerable'])):
            if want != have:
                out.append(f'{c["slug"]}: {k} is {have!r}, the manifest says {want!r}')
    for s in sorted(set(live) - set(categories(m))):
        out.append(f'extra: `{s}` is on the board but not in the manifest')
    return out


def labels(m, api):
    owner, name = m['repository'].split('/')
    have = {x['name'].lower() for x in api.rest('GET', f'/repos/{owner}/{name}/labels?per_page=100')}
    made = []
    for lab in m.get('labels', []):
        if lab['name'].lower() not in have:
            api.rest('POST', f'/repos/{owner}/{name}/labels',
                     {'name': lab['name'], 'color': lab['color'], 'description': lab.get('description', '')})
            made.append(lab['name'])
    return made


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'check'
    m = load()
    if cmd == 'check':
        errs = check()
        for e in errs:
            print('FAIL:', e)
        print(f'forum-gate {VERSION}: {m.get("repository")}: '
              + (f'{len(errs)} problem(s)' if errs else f'{len(m.get("categories", []))} categories, manifest sound'))
        return 1 if errs else 0
    if cmd == 'checklist':
        print(checklist(m))
        return 0
    token = os.environ.get('GH_TOKEN')
    if not token:
        sys.exit('forum-gate: set GH_TOKEN')
    api = GitHub(token, os.environ.get('FORUM_SEARCH_TOKEN'))
    if cmd == 'audit':
        out = audit(m, api)
        print('\n'.join(out) if out else 'The live board matches the manifest.')
        return 1 if out else 0
    if cmd == 'labels':
        print('created: ' + (', '.join(labels(m, api)) or 'nothing, every label exists'))
        return 0
    if cmd == 'event':
        with open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8') as f:
            ev = json.load(f)
        for what, detail in handle(m, os.environ['GITHUB_EVENT_NAME'], ev, api):
            print(f'forum-gate: {what} {detail}')
        return 0
    sys.exit(f'forum-gate: unknown command {cmd!r} (check, checklist, audit, labels, event)')


if __name__ == '__main__':
    sys.exit(main(sys.argv))
