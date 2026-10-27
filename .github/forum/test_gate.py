#!/usr/bin/env python3
"""Forum gate tests (no network): the manifest checks, the tiers, and every action the gate takes on a new
thread or reply, against a fake GitHub that records each call. The last test checks this repository's own
board, so a change to board.toml, a form or FORUM.md that breaks the board fails here too.

    python3 .github/forum/test_gate.py
"""
import copy
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('gate', os.path.join(HERE, 'gate.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
fails = []


def check(cond, what):
    print(('PASS: ' if cond else 'FAIL: ') + what)
    if not cond:
        fails.append(what)


BOARD = {
    'version': 1, 'board': 'internal', 'repository': 'Example-Org/core', 'public': True, 'name': 'Example house',
    'gate': {'mode': 'enforce', 'count_orgs': ['Example-Org']},
    'groups': {'council': ['Alice'], 'mods': []},
    'tiers': [
        {'id': 'contributor', 'name': 'Contributor', 'merged_prs': 1, 'associations': ['MEMBER']},
        {'id': 'core', 'name': 'Core', 'merged_prs': 10},
        {'id': 'council', 'name': 'Council', 'groups': ['council']},
    ],
    'categories': [
        {'slug': 'floor', 'name': 'Floor', 'emoji': ':microphone:', 'format': 'open', 'section': 'Open',
         'description': 'Anyone.'},
        {'slug': 'direction', 'name': 'Direction', 'emoji': ':compass:', 'format': 'open', 'section': 'Open',
         'description': 'Where we go.', 'form': True},
        {'slug': 'workshop', 'name': 'Workshop', 'emoji': ':hammer:', 'format': 'open', 'section': 'Gated',
         'description': 'Contributors.', 'start': 'contributor', 'reply': 'contributor', 'fallback': 'floor'},
        {'slug': 'core', 'name': 'Core room', 'emoji': ':bricks:', 'format': 'open', 'section': 'Gated',
         'description': 'Core.', 'start': 'core', 'reply': 'core', 'fallback': 'floor'},
        {'slug': 'council', 'name': 'Council', 'emoji': ':classical_building:', 'format': 'open', 'section': 'Gated',
         'description': 'Council.', 'start': 'council', 'reply': 'council', 'fallback': 'floor', 'floor': True,
         'agents': False},
    ],
}
LIVE = [{'id': f'CAT_{c["slug"]}', 'slug': c['slug'], 'name': c['name'], 'emoji': c['emoji'],
         'description': c['description'], 'isAnswerable': False} for c in BOARD['categories']]


class Fake:
    """Records every call; answers searches from a table of merged pull requests per login."""

    def __init__(self, prs=None, notes=None, parent=None):
        self.calls, self.searches = [], []
        self.prs, self.notes, self.parent = prs or {}, notes or [], parent

    def merged_prs(self, login, orgs):
        self.searches.append((login, tuple(orgs)))
        return self.prs.get(login, 0)

    def graphql(self, query, v):
        name = next(k for k in ('CATEGORY_Q', 'MOVE', 'COMMENT', 'HIDE', 'CREATE', 'LOCK', 'THREAD_OF', 'GATE_NOTES')
                    if getattr(gate, k) == query)
        self.calls.append((name, v))
        if name == 'CATEGORY_Q':
            return {'repository': {'id': 'REPO', 'hasDiscussionsEnabled': True, 'discussionCategories': {'nodes': LIVE}}}
        if name == 'CREATE':
            return {'createDiscussion': {'discussion': {'url': 'https://github.com/Example-Org/core/discussions/99'}}}
        if name == 'THREAD_OF':
            return {'node': {'replyTo': {'id': self.parent} if self.parent else None}}
        if name == 'GATE_NOTES':
            return {'node': {'comments': {'nodes': self.notes}}}
        return {}

    def named(self, name):
        return [v for n, v in self.calls if n == name]


def thread_event(slug, login, assoc='NONE', bot=False, body='Hello', title='A question'):
    return {'action': 'created', 'discussion': {
        'node_id': 'D1', 'title': title, 'html_url': 'https://github.com/Example-Org/core/discussions/1',
        'category': {'slug': slug}, 'body': body, 'author_association': assoc,
        'user': {'login': login, 'type': 'Bot' if bot else 'User'}}}


def reply_event(slug, login, assoc='NONE', bot=False, body='A reply'):
    ev = thread_event(slug, 'Alice', 'MEMBER')
    ev['comment'] = {'node_id': 'C9', 'html_url': 'https://github.com/Example-Org/core/discussions/1#c9', 'body': body,
                     'author_association': assoc, 'user': {'login': login, 'type': 'Bot' if bot else 'User'}}
    return ev


quiet = lambda *_: None


def run(board, name, ev, api):
    return gate.handle(board, name, ev, api, log=quiet)


# 1. the manifest
check(gate.validate(BOARD) == [], 'a sound manifest has no errors')
bad = copy.deepcopy(BOARD)
bad['categories'][2]['fallback'] = 'core'
check(any('must be a different open category' in e for e in gate.validate(bad)), 'a gated fallback is refused')
bad = copy.deepcopy(BOARD)
del bad['categories'][3]['fallback']
check(any('needs a fallback' in e for e in gate.validate(bad)), 'a gated category without a fallback is refused')
bad = copy.deepcopy(BOARD)
bad['categories'][2]['reply'] = 'contributors'
check(any("'contributors' is not" in e for e in gate.validate(bad)), 'an unknown tier is refused')
bad = copy.deepcopy(BOARD)
bad['tiers'][2]['groups'] = ['counsel']
check(any("'counsel' is not defined" in e for e in gate.validate(bad)), 'a misspelt group is refused')
bad = copy.deepcopy(BOARD)
bad['categories'] += [dict(BOARD['categories'][0], slug=f'x{i}', name=f'X{i}') for i in range(21)]
check(any('at most 25' in e for e in gate.validate(bad)), 'more than 25 categories is refused')
bad = copy.deepcopy(BOARD)
bad['categories'][0]['emoji'] = '🎙️'
check(any('shortcode' in e for e in gate.validate(bad)), 'an emoji that is not a shortcode is refused')
bad = copy.deepcopy(BOARD)
bad['gate']['count_orgs'] = []
check(any('count_orgs must name' in e for e in gate.validate(bad)), 'a merged-PR tier needs organisations to count in')

# 2. the tiers
api = Fake(prs={'bob': 3})
a = gate.Author(BOARD, api, 'bob', 'NONE', False)
check(a.level() == 1 and a.may('contributor') and not a.may('core') and len(api.searches) == 1,
      '3 merged PRs reach Contributor, not Core, for one search')
api = Fake(prs={'carol': 12})
check(gate.Author(BOARD, api, 'carol', 'NONE', False).level() == 2, '12 merged PRs reach Core')
api = Fake()
a = gate.Author(BOARD, api, 'alice', 'NONE', False)
check(a.level() == 3 and api.searches == [], 'a council member (any case) reaches the top tier with no search')
check(a.may('core') and a.may('contributor'), 'a higher tier may post wherever a lower one may')
api = Fake()
check(gate.Author(BOARD, api, 'dan', 'MEMBER', False).level() == 1, 'an organisation member is a Contributor')
check(not gate.Author(BOARD, Fake(), 'erin', 'MEMBER', False).may('group:council'), 'a group room is for its members only')
check(gate.describe(BOARD, 'contributor') == 'Contributor (1 merged pull request in Example-Org, or organisation member, or a higher tier)'
      and gate.describe(BOARD, 'council') == 'Council (a seat in the council group)',
      'a tier is described in words: its threshold, its organisations, its groups')

# 3. the gate
api = Fake()
check(run(BOARD, 'discussion', thread_event('direction', 'zed'), api) == [] and api.calls == [] and api.searches == [],
      'an open category: no calls and no search')

api = Fake(prs={'zed': 0})
done = run(BOARD, 'discussion', thread_event('workshop', 'zed'), api)
check(('move', 'floor') in done and api.named('MOVE')[0]['cat'] == 'CAT_floor', 'a thread from someone below the tier moves to the floor')
body = api.named('COMMENT')[0]['body']
check('@zed' in body and 'Contributor' in body and 'GitHub counts 0 merged pull requests' in body and 'Nothing was deleted' in body,
      'the reply says why, with the count, and that nothing was deleted')

api = Fake(prs={'zed': 0}, parent='C1', notes=[{'author': {'login': 'github-actions'},
                                               'body': 'x <!-- forum-gate floor: https://github.com/Example-Org/core/discussions/7 -->'}])
done = run(BOARD, 'discussion_comment', reply_event('council', 'zed'), api)
check(('hide', 'https://github.com/Example-Org/core/discussions/1#c9') in done and api.named('HIDE')[0]['id'] == 'C9',
      'a reply from someone below the tier is hidden (minimised), not deleted')
c = api.named('COMMENT')[0]
check(c['reply'] == 'C1' and 'discussions/7' in c['body'], 'the explanation answers in the same thread and links its floor')

api = Fake(notes=[{'author': {'login': 'zed'}, 'body': '<!-- forum-gate floor: https://evil.example/x -->'}])
run(BOARD, 'discussion_comment', reply_event('council', 'zed'), api)
check('evil.example' not in api.named('COMMENT')[0]['body'], 'a floor marker written by anyone but the gate is ignored')

api = Fake()
done = run(BOARD, 'discussion', thread_event('council', 'alice', title='Budget @everyone <b>'), api)
check(done and done[0][0] == 'floor', 'a council member opening a thread gets a floor for everyone')
create = api.named('CREATE')[0]
check(create['cat'] == 'CAT_floor' and create['title'] == 'Floor: Budget @everyone <b>' and '@​everyone' in create['body']
      and '<b>' not in create['body'], 'the floor is in the fallback, and the title cannot ping or inject')
check('<!-- forum-gate floor: https://github.com/Example-Org/core/discussions/99 -->' in api.named('COMMENT')[0]['body'],
      'the gated thread links its floor with a marker the gate can find again')

api = Fake()
done = run(BOARD, 'discussion_comment', reply_event('council', 'Alice', bot=True), api)
check(('hide', 'https://github.com/Example-Org/core/discussions/1#c9') in done and 'Only people post' in api.named('COMMENT')[0]['body'],
      'an agent in a people-only room is hidden, whatever its tier')

api = Fake()
check(run(BOARD, 'discussion_comment', reply_event('council', 'github-actions[bot]', bot=True), api) == [],
      "the gate never acts on the gate's own posts")

report = copy.deepcopy(BOARD)
report['gate']['mode'] = 'report'
api = Fake(prs={'zed': 0})
done = run(report, 'discussion_comment', reply_event('core', 'zed'), api)
check(api.named('HIDE') == [] and api.named('MOVE') == [] and 'report mode' in api.named('COMMENT')[0]['body'],
      'report mode replies and changes nothing')

off = copy.deepcopy(BOARD)
off['gate']['mode'] = 'off'
check(run(off, 'discussion', thread_event('core', 'zed'), Fake()) == [], 'mode off does nothing')

signed = copy.deepcopy(BOARD)
signed['gate'].update(signature=r'(?m)^[-—]\s*(protean|sparky)-[A-Za-z0-9]+\s*$', signature_exempt=['OWNER', 'group:council'])
api = Fake()
done = run(signed, 'discussion_comment', reply_event('direction', 'zed'), api)
check(('hide', 'https://github.com/Example-Org/core/discussions/1#c9') in done and 'sign-off' in api.named('COMMENT')[0]['body'],
      'on a signed board an unsigned reply is hidden until it is signed')
api = Fake()
check(run(signed, 'discussion_comment', reply_event('direction', 'zed', body='Done.\n— protean-orda'), api) == [],
      'a signed reply passes')
api = Fake()
check(run(signed, 'discussion_comment', reply_event('direction', 'boss', assoc='OWNER'), api) == [],
      'an exempt association need not sign')
api = Fake()
check(run(signed, 'discussion_comment', reply_event('direction', 'alice', assoc='MEMBER'), api) == [],
      'a member of an exempt group need not sign')
bad = copy.deepcopy(signed)
bad['gate']['signature_exempt'] = ['group:nobody']
check(any('signature_exempt' in e for e in gate.validate(bad)), 'an exemption for an unknown group is refused')
api = Fake()
done = run(signed, 'discussion', thread_event('direction', 'zed'), api)
check(api.named('MOVE') == [] and ('reply', 'zed') in done, 'an unsigned thread is asked to sign, not moved')

# 4. the offline check: forms, FORUM.md, and public seats
root = tempfile.mkdtemp(prefix='forum-gate-')
os.makedirs(os.path.join(root, '.github', 'DISCUSSION_TEMPLATE'))
with open(os.path.join(root, '.github', 'DISCUSSION_TEMPLATE', 'direction.yml'), 'w') as f:
    f.write('body:\n  - type: textarea\n    id: what\n    attributes:\n      label: What\n')
doc = ' '.join(f'`{c["slug"]}`' for c in BOARD['categories']) + ' Council: @Alice.'
with open(os.path.join(root, 'FORUM.md'), 'w') as f:
    f.write(doc)
check(gate.check(root, BOARD) == [], 'forms, FORUM.md and the public seats agree')
with open(os.path.join(root, '.github', 'DISCUSSION_TEMPLATE', 'workshop.yml'), 'w') as f:
    f.write('body:\n  - type: input\n    id: a\n  - type: input\n    id: a\n')
errs = gate.check(root, BOARD)
check(any('workshop.yml: category workshop does not say form = true' in e for e in errs)
      and any('an id is used twice' in e for e in errs), 'a stray form and a repeated field id are caught')
with open(os.path.join(root, '.github', 'DISCUSSION_TEMPLATE', 'workshop.yml'), 'w') as f:
    f.write('body:\n  - type: dropdown\n    id: a\n    attributes:\n      label: Agreed: so far\n      options:\n        - yes\n        - "no"\n')
errs = gate.check(root, BOARD)
check(any('line 5: quote this value' in e for e in errs) and any('line 7: quote this option' in e for e in errs)
      and not any('line 8' in e for e in errs), 'a value holding ": " and a bare yes option are caught')
os.remove(os.path.join(root, '.github', 'DISCUSSION_TEMPLATE', 'workshop.yml'))
with open(os.path.join(root, 'FORUM.md'), 'w') as f:
    f.write(doc.replace('@Alice', 'Alice').replace('`core`', 'core'))
errs = gate.check(root, BOARD)
check(any('does not name @Alice' in e for e in errs) and any('`core`' in e for e in errs),
      'FORUM.md must list every category and name every seat on a public board')

# 5. this repository's own board
if os.path.exists(gate.MANIFEST):
    errs = gate.check()
    for e in errs:
        print('   ', e)
    check(errs == [], f'this repository\'s board ({gate.load().get("repository")}) passes the check')

print(f'\n{"FAILED: " + str(len(fails)) if fails else "all passed"}')
sys.exit(1 if fails else 0)
