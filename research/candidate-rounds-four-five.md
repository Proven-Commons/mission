# Candidate scores: rounds four and five

This records the two published assessments of each candidate from [mission issue 19](https://github.com/Proven-Commons/mission/issues/19). Scores are estimates for choosing work, not claims that a library is correct or verified. A higher specification score means a smaller, clearer specification.

The six axes are harm, reach, specification size, available test oracle, useful slice size and upstream interest. Each runs from 0 to 3, for a total of 18. `Sheet` is the first assessment; `Total` is the second. Disagreements remain visible rather than being replaced by a single unexplained number.

## Round four

| Target | Harm | Reach | Spec | Oracle | Slice | Upstream | Total | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JWS compact | 3 | 3 | 2 | 3 | 3 | 2 | 16 | 16 |
| MQTT 5.0 framing | 2 | 2 | 2 | 3 | 3 | 2 | 14 | 16 |
| NTP packet | 2 | 3 | 2 | 3 | 3 | 2 | 15 | 16 |
| DHCPv4 message | 3 | 3 | 3 | 2 | 3 | 1 | 15 | 15 |
| TLS ClientHello | 2 | 3 | 2 | 3 | 3 | 2 | 15 | 15 |
| XML safe subset | 3 | 3 | 2 | 3 | 2 | 2 | 15 | 14 |
| INI | 2 | 3 | 1 | 2 | 3 | 1 | 12 | 11 |

[Second assessment and reasons](https://github.com/Proven-Commons/mission/issues/19#issuecomment-6418822706).

The six format targets now have repositories: [jws](https://github.com/Proven-Commons/jws), [mqtt](https://github.com/Proven-Commons/mqtt), [ntp](https://github.com/Proven-Commons/ntp), [dhcpv4](https://github.com/Proven-Commons/dhcpv4), [clienthello](https://github.com/Proven-Commons/clienthello) and [xml](https://github.com/Proven-Commons/xml). Their plan issues and PRs are the current work records. INI remains a research proposal; no repository is requested here.

The second assessment corrects the NTP scope to include RFC 7822 extension framing, trailing authentication bytes and zero timestamps as unknown. It also revises several cited failure cases. This page does not repeat the original security citations: the linked assessments preserve the claims and the corrections together.

## Round five

| Target | Harm | Reach | Spec | Oracle | Slice | Upstream | Total | Sheet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Regular expressions, Thompson NFA engine | 2 | 3 | 2 | 2 | 3 | 2 | 14 | 15 |
| SSH wire types and public key blobs | 3 | 2 | 3 | 3 | 3 | 1 | 15 | 15 |
| ELF64 header and section table reader | 2 | 2 | 3 | 2 | 3 | 2 | 14 | 14 |
| Binary property list reader (bplist00) | 2 | 2 | 2 | 3 | 3 | 2 | 14 | 14 |
| JSON Pointer and JSON Patch | 1 | 2 | 3 | 3 | 3 | 2 | 14 | 14 |
| BSON reader and printer | 1 | 2 | 3 | 2 | 3 | 2 | 13 | 13 |
| Cron expressions with next fire time | 1 | 3 | 2 | 2 | 3 | 2 | 13 | 13 |

[First assessment](https://github.com/Proven-Commons/mission/issues/19#issuecomment-6420742101); [second assessment and reasons](https://github.com/Proven-Commons/mission/issues/19#issuecomment-6426417423).

[SSH](https://github.com/Proven-Commons/ssh) now has a repository and a merged first slice. The other six rows remain research proposals. JSON Pointer and Patch would first be considered as additions to the existing JSON library; publication of a score does not authorise a new repository or promise an implementation.

## Earlier proposals and prior work

Rounds [one](https://github.com/Proven-Commons/mission/issues/12) and [two](https://github.com/Proven-Commons/mission/issues/15) feed the candidate list in PR #16 and its update in PR #21. Those PRs still need their current-main integration and status corrections; this page does not replace their list.

The [WebAssembly reassessment](https://github.com/Proven-Commons/mission/issues/19#issuecomment-6436747917) is separate from rounds four and five. It distinguishes framing from full module validation and corrects the earlier prior-work summary. It remains research: no WebAssembly repository or novelty claim is approved by this page.
