# Merge SOP

A pull request is merged when a maintainer who did not write it approves it.

## Scope

This rule applies to every repository in aska-digital, Foundation-0, and Proven-Commons.
Maintainers are repository collaborators with current write, maintain or admin authority.

This SOP covers pull requests to main.

## Rule

Merge a pull request to main when all of these hold:

- The pull request is open and is not a draft.
- Its latest review from a maintainer is APPROVE.
- The approving maintainer is not the pull request author.
- The approval is on the current head.
- The pull request merges cleanly into main.
- No required check is failing.
- No note in the pull request says an owner decision or a maintainer decision is still required.

An author's own approval does not count. GitHub rejects an approval where the reviewer login matches the author login.

## Merge step

- Recheck the list above on the current head immediately before merging.
- Merge with a merge commit, unless the repository uses a different method by default.
- After merging, check that the pull request shows closed and merged.

## Holds

Do not merge when any item in the rule fails.

- A dirty pull request needs a rebase first.
- A failing check needs a fix or a recorded maintainer decision first.
- A draft needs to be marked ready first.
- An approval on an old head needs a fresh approval on the new head.
- A pull request stacked on an unmerged branch waits until that branch lands on main.
