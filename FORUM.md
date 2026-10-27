# Proven Commons' internal board

**Status: proposed on 26 October 2026, for the programme to adopt in a public issue on this repository.** Until
it is adopted, the rooms, tiers and seats below are proposals.

Proven Commons has two boards, both public, both under the
[forum standard](https://github.com/Proven-Commons/.github/blob/main/FORUM-STANDARD.md):

- **The main board** is [the organisation's Discussions](https://github.com/orgs/Proven-Commons/discussions):
  the academy, library proposals, specification review, challenges to claims, upstream work and questions.
  [Its FORUM.md](https://github.com/Proven-Commons/.github/blob/main/FORUM.md) has the rules and conduct for
  both boards, the moderation log, and which repositories have boards.
- **The internal board** is [Discussions on this repository](https://github.com/Proven-Commons/mission/discussions):
  the programme itself, its targets, its structure, its money, the verified bar, and its decisions. This file
  describes it.

## Open to read, open to speak, some rooms kept for each level

Anyone can read every thread on this board. Anyone with a GitHub account can start a thread and reply in the
**open rooms**, which are most of the board. They include the verified bar itself: anyone may propose a change
to it.

A few rooms keep their discussion to the people at each level of the
[academy ladder](FOUNDING-BRIEF.md#the-academy), because the ladder is how this programme already measures
trust: *graduation at each level is merged work that a computer checked*. Every gated room has the **Floor**
as its open counterpart:

- A thread opened in a gated room by someone who can't start one there **moves to the Floor**, intact.
- A reply in a gated room from someone who can't reply there is **hidden, not deleted**. Anyone can still expand
  it and read it, and the gate links the Floor.
- Every Stewards thread gets **its own floor thread** the moment it is opened, so anyone can answer it.

The forum gate (`.github/forum/gate.py`, run by `.github/workflows/forum.yml`) does this, and says what it did in
a reply in the thread. The rules it enforces are [.github/forum/board.toml](.github/forum/board.toml).

## Tiers

| Tier | Who reaches it | Rooms it opens |
|---|---|---|
| Everyone | anyone with a GitHub account, including Level 0 Readers | the open rooms, the Floor, replies to Progress notes |
| Apprentice (Level 1) | one merged pull request in any Proven-Commons repository (Level 1's exit test is code merged into a public project), or organisation membership or collaborator access | Workshop; posting Progress notes |
| Verifier (Level 2) | fifteen merged pull requests in Proven-Commons, or the verifiers group (owns a module that passed the bar with a separate reviewer) | Review desk |
| Spec Lead and Mentor (Level 3) | the spec-leads group | Mentors; replies in Stewards |
| Steward | the stewards group: the director and the head of verification | Stewards |

Each tier also opens every room below it. The first two open automatically, on counts anyone can check. The
upper levels are opened by name, because Level 2 and Level 3 are earned by passing the bar and by reviewing,
which a count of merges doesn't measure. The groups are changed only by pull request, approved by an owner, and
the check in CI fails if a seat is not named below.

**The Stewards room is for people.** A post from a GitHub app is hidden there, whatever its tier, because a person
owns every decision taken there. Agents read it and take part on its floor threads.

## Rooms

| Section | Category | Format | Slug | Start a thread | Reply | What it is for |
|---|---|---|---|---|---|---|
| Orientation | Announcements | Announcement | `announcements` | maintainers | everyone | News about the programme from its stewards. |
| | Floor | Open-ended | `floor` | everyone | everyone | Anything about how Proven Commons is run, and the open answer to every gated room. |
| | Decisions | Announcement | `decisions` | maintainers | everyone | One thread per decision, with its reasons and the issue or pull request that carries it out. Has a form. |
| Open rooms | Direction | Open-ended | `direction` | everyone | everyone | Targets, waves and priorities. |
| | Structure | Open-ended | `structure` | everyone | everyone | Squads, roles, the academy ladder, the playbook. |
| | Verified bar | Open-ended | `verified-bar` | everyone | everyone | A change to the bar. The head of verification approves it. Has a form. |
| | Proposals | Open-ended | `proposals` | everyone | everyone | A written proposal for a decision. Has a form. |
| | Funding | Open-ended | `funding` | everyone | everyone | Grants, sponsors, costs, and the split between public and paid work. |
| | Progress notes | Open-ended | `progress-notes` | Apprentice | everyone | Each squad's weekly note: what was specified, proved, and failed. Has a form. |
| | Retros | Open-ended | `retros` | everyone | everyone | Time, cost, what went wrong, what changes. |
| | Polls | Poll | `polls` | everyone | everyone | A poll informs a decision; it doesn't make one. |
| Apprentices | Workshop | Open-ended | `workshop` | Apprentice | Apprentice | Who owns which module, pairing, unblocking each other. |
| Verifiers | Review desk | Open-ended | `review-desk` | Verifier | Verifier | Reviewer assignment and specification approvals. Nobody approves a specification they wrote. |
| Spec leads and mentors | Mentors | Open-ended | `mentors` | Spec Lead | Spec Lead | Cohorts, curriculum, the mentor roster, graduate records. |
| Stewards | Stewards | Open-ended | `stewards` | Steward | Spec Lead | Leadership threads, in public. People only. Each thread has a floor thread. |

## Who holds which seat

- **Stewards** (`stewards`): @ahrazzle, until the director and the head of verification are named
  ([FOUNDING-BRIEF.md](FOUNDING-BRIEF.md#decisions-needed-now), decision 2). Naming them is a pull request to
  `.github/forum/board.toml` and this file.
- **Spec Leads and Mentors** (`spec-leads`): none yet.
- **Verifiers** (`verifiers`): none yet. A verifier is added when a module they own passes the bar with a
  separate reviewer.
- **Moderators:** listed on the [main board's FORUM.md](https://github.com/Proven-Commons/.github/blob/main/FORUM.md#who-holds-which-role).

## Setup checklist

After the main board is set up ([its checklist](https://github.com/Proven-Commons/.github/blob/main/FORUM.md#setup)):

- [ ] Settings → General → Features → Discussions.
- [ ] `python3 .github/forum/gate.py checklist`, and make each section and category it lists. Delete the defaults
      it does not list (keep Announcements and Polls).
- [ ] `GH_TOKEN=… python3 .github/forum/gate.py audit` until it reports a match.
- [ ] Reported content on (Settings → Moderation options), and the moderators team given Triage.
- [ ] For the first two weeks, `mode = "report"` in `.github/forum/board.toml`; then `"enforce"`.
- [ ] Announce the board in Announcements, linking this file, and pin the thread.
