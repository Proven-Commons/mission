# Reviews

A review record is the written result of attacking a project: factory step 5, done by someone trying to show the work is wrong. Each record names the repo and commit it looked at, the version of the bar it measured against, and the tools it used. It gives a status for each bar item and a list of findings. Each finding has a command that reproduces it, the output seen, and a proposed fix. Evidence files sit next to the record and run against the named commit.

A review record is not a spec approval. Bar item 1 needs a person who did not write the specification to approve it. A record written by an AI agent, or by the author, can find problems. It cannot approve.

Finding a problem is a success to report, not a failure to hide (brief, "Risks and the plan for each").

## Records

- [tar/2026-10-24-bar-audit.md](tar/2026-10-24-bar-audit.md): the tar pilot at `7517a86`. Not yet verified: the headline theorem states less than its claim, two statements on the page are false, and four of the six bar items are not fully met.
