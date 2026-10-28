# Required checks on main

`required-checks.toml` records the intended branch policy. The planner in
`tools/reconcile_required_checks.py` reads GitHub through the authenticated
`gh` CLI. Its default mode cannot write settings.

Mission requires `self-test`, `lean-self-test` and `template / bar` from
`.github/workflows/ci.yml`. Libraries require `bar / bar` only after their
bar workflow and that GitHub Actions check exist on the exact main commit.
The planner matches checks to the named workflow's run through its check
suite, so an identically named check from another workflow does not qualify.
The policy also records one approving review and administrator enforcement.
Existing stronger review counts and unrelated protection settings stay intact.

Tar is explicitly deferred until Set B and its bar workflow land. Review a
policy change removing that deferral after the landing. Repositories without
a bar workflow stay deferred; this manifest does not create their workflows.
No live protection has been changed by adding this policy.

## Review and apply a plan

Run from the mission checkout:

```sh
python3 tools/reconcile_required_checks.py --repo mission --write-plan /tmp/mission-protection.json
```

Inspect the saved JSON, including the main SHA, workflow blob, current
protection and proposed API requests. A read-only plan prints `ready`,
`unchanged` or `deferred` for each repository. Exit 2 means something was
deferred; exit 1 means a read or validation failed. Select repositories with
repeated `--repo` arguments. An apply plan may contain no deferred repository.

After a maintainer reviews the exact plan, an administrator can apply it:

```sh
python3 tools/reconcile_required_checks.py --apply-plan /tmp/mission-protection.json
```

This explicit command is the only write path. It rebuilds the plan from the
current policy and live GitHub state before writing. A changed SHA, workflow,
policy, protection or action payload rejects the saved plan. Edited JSON
cannot supply arbitrary API requests. Existing protection uses narrow PATCH
requests for required checks and the review minimum, and POST only to enable
administrator enforcement. A new protection uses PUT only after GitHub has
confirmed that main exists and no protection currently exists.

GitHub provides no atomic compare-and-swap for these settings. The script
checks the head again before each write and protection again before each
repository. A network failure or concurrent edit can stop a partial apply.
Inspect live state and make a fresh plan before continuing. Do not rerun an
old plan blindly. No command removes protection or deletes an existing check.

## Pin a reviewed bar release

After a release commit on mission's default branch passes the required CI
and independent review, a maintainer chooses its exact SHA. Create a release
tag only through that reviewed release step. Each library should pin both
its reusable workflow reference and `bar-ref` to the same reviewed tag or
commit. This script creates no tags, releases or library edits.

## Verify changes

```sh
python3 -m unittest discover -s bar/tests -v
```

Tests mock GitHub writes and cover dry runs, missing workflows, false check
names, application bindings, existing settings, plan tampering, stale main
SHAs, concurrent changes and explicit application. The mission self-test job
already discovers this test file.
