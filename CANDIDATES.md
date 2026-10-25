# Candidate list

This file is the permanent record of targets for Proven Commons. It holds
every target in one place: what it is, how it scored, where its repo and
plan live, who is working on it, and what state it is in.

The list changes as work moves. A target moves through these states:
proposed, repo created, claimed, in progress, shipped, maintained. When a
target ships, move its row to Shipped and keep its links. Do not delete
shipped rows. When a new candidate is identified, add it to Proposed with
its score, slice, claim, and oracle, before any repo is created.

This file integrates the earlier list in mission issue 12 in full. All
eight targets from that issue appear below, with their scores and slices,
plus the Base32 note folded into the codec row. Issue 12 stays as history.
This file is the living list from here on. Do not maintain a second living
list in issue comments. Update this file when a status changes.

## Scoring

Score each candidate 0 to 3 on each point, total out of 18, as the founding
brief sets out.

- Harm if it fails: money moved, access granted, data exposed, safety affected.
- Reach: how much other software depends on it.
- Specification size: a short public specification scores high. A large or
  disputed one scores low.
- Oracle: an original implementation and test suite exist to compare against.
- Slice: a useful part can be cut out and proved on its own.
- Upstream stance: the maintainers will read a submission and give feedback.

Scores for the mission issue 12 targets come from that issue. Scores for
the new candidates in Proposed come from the proposal dated 2026-10-25 and
await org confirmation.

## Shipped

| Target | Score | Repo | State |
| --- | --- | --- | --- |
| Tar extractor (ustar) | Pilot, not scored in issue 12 | [tar](https://github.com/Proven-Commons/tar) | Pilot complete. Proved rule: no file in an archive can be written outside the destination folder. Bar audit still open in mission issue 1, so do not call it verified until that audit closes. |

## In progress

| Target | Score | Repo | Plan | Claimed by | State |
| --- | --- | --- | --- | --- | --- |
| Codec: hex, Base64, CRC-32 | Academy material, not scored in issue 12 | [codec](https://github.com/Proven-Commons/codec) | [codec#1](https://github.com/Proven-Commons/codec/issues/1) | Claude (import), hyd-nawab (Base32) | Import in codec PR 1. Base32 in codec PR 2, stacked on PR 1. Base32 does not get its own repo. |
| ZIP archive reader | 15 | [zip](https://github.com/Proven-Commons/zip) | [zip#1](https://github.com/Proven-Commons/zip/issues/1) | hyd-nawab | Stored entries only, with a proved path gate. Draft PR 2 states 3,058 checks, 0 failures, seed 20261025. |
| JSON parser and printer (RFC 8259) | 16 | [json](https://github.com/Proven-Commons/json) | [json#1](https://github.com/Proven-Commons/json/issues/1) | hyd-nawab | First slice in progress. Round trip is the main claim. |
| RFC 3339 timestamp parser | 16 | [rfc](https://github.com/Proven-Commons/rfc) | [rfc#1](https://github.com/Proven-Commons/rfc/issues/1) | Claude | First slice in PR 2, ready for review. CI green, awaiting a spec reviewer. |
| Protobuf wire format codec | 15 | [protobuf](https://github.com/Proven-Commons/protobuf) | [protobuf#1](https://github.com/Proven-Commons/protobuf/issues/1) | Claude | First slice in PR 2, ready for review, after the RFC 3339 slice is up for review. Wire layer only. |
| WebSocket frame parser (RFC 6455, section 5) | 13 | [websocket](https://github.com/Proven-Commons/websocket) | [websocket#1](https://github.com/Proven-Commons/websocket/issues/1) | amp-cayde | First slice in draft PR 2. Round trip proved, 720 checks, 0 failures, seed 20261025. Longer length forms than needed are turned away. |
| CBOR decoder (RFC 8949) | 13 | [cbor](https://github.com/Proven-Commons/cbor) | [cbor#1](https://github.com/Proven-Commons/cbor/issues/1) | ins-ember | Definite length items first. Scaffold and specification file planned as the first draft PR. |
| UTF-8 codec | 16 | [utf](https://github.com/Proven-Commons/utf) | [utf#1](https://github.com/Proven-Commons/utf/issues/1) | Claude | Claimed 2026-10-25. Org answer is yes: build the standalone codec. Additions to the plan: exact acceptance, Unicode Table 3-7, and Lean core as a test oracle. |

## Repo created, work not started

| Target | Score | Repo | Plan | State |
| --- | --- | --- | --- | --- |
| SemVer parser and precedence (SemVer 2.0.0) | 15 | [semver](https://github.com/Proven-Commons/semver) | [semver#1](https://github.com/Proven-Commons/semver/issues/1) | Plan names hyd-nawab for the first work. No claim comment has landed yet, so confirm the claim before starting. |

## Planned, no repo yet (Wave 1)

From the founding brief, months 4 to 9, one squad each. No scores published
for these three yet.

- Policy engine in the style of AWS Cedar. Claims: a satisfied forbid gives
  a deny, no satisfied permit gives a deny, and policy order does not change
  the decision.
- SQLite file reader. Slice: 100-byte header, page header, and records.
  Claims: the parser returns an error instead of reading outside the file,
  and a record it reads stays inside its page.
- Redis protocol parser and small key-value store. Claims: reading what the
  printer wrote gives the same command back, a get after a set returns the
  set value, and a get after a delete returns nothing.

## Proposed, no repo yet

Proposed 2026-10-25 by amp-sai, agent for Ahraz Arifuddin. None of these
duplicates Wave 1, mission issue 12, tar, or codec. Org owners create a repo
only after confirming the score and slice.

| Target | Score | Slice | Main claim | Oracle |
| --- | --- | --- | --- | --- |
| TOML 1.0 parser | 16 | Parse a TOML document into tables, arrays, strings, integers, floats, booleans, and datetimes. No printer in the first slice. | Parsing a document and reading a key back gives the value the document states, and a document outside the grammar is rejected. | Python tomllib, Rust toml crate, TOML test suite |
| IP address and CIDR parser | 16 | Parse IPv4 and IPv6 addresses and CIDR prefixes. No DNS lookup. | An address is inside a prefix exactly when its masked bits match the prefix bits. An address with an extra part, or a prefix length past the address size, is rejected. | Python ipaddress, Rust std IpAddr, RFC 4291 and RFC 4632 examples |
| HTTP/1.1 header parser | 15 | Parse a request line and headers only. No body, no chunked transfer, no server. | A header block is accepted exactly when it matches RFC 9112 framing rules. Duplicate Content-Length, a bare carriage return, and an obsolete folded line are rejected. | Python http.client in strict mode, httpbis test cases |
| MessagePack decoder | 15 | Decode MessagePack items with definite lengths: integers, strings, binary, arrays, and maps. No extension types in the first slice. | Decoding an encoding returns the same item, and the decoder returns an error instead of reading past the end of its input. | Python msgpack, official MessagePack test vectors |
| UUID parser | 15 | Parse the canonical text form in RFC 9562 and print it back. No generation in the first slice. | Print then parse returns the same UUID. A string with the wrong version or variant field, or a misplaced hyphen, is rejected. | Python uuid, Rust uuid, RFC 9562 examples |
| DNS wire message parser | 14 | Parse a DNS message header, questions, and records from RFC 1035 bytes, with compression pointers limited to earlier offsets in the same message. | The decoder never reads past the end of the message. A pointer loop, or a pointer forward in the message, is rejected. | Python dnspython, dig output for the same messages |
| Bencode parser | 13 | Parse integers, byte strings, lists, and dictionaries, with dictionary keys in sorted order. | Decoding an encoding returns the same value, and a dictionary with unsorted keys is rejected. | Python bencode libraries, torrent files in the wild |

Kept on record, not proposed now: ELF header parser, scored 11. Its spec is
large and a first slice would still leave most of the format outside the
proof. Revisit it once the binary-format repos have a shared scaffold.

## How this list is maintained

- Claim rule: take work by leaving a comment on the plan issue that names
  who is working on it, before starting. Update this file in the same change
  where the claim, repo creation, draft PR, merge, or shipped state lands,
  or in a follow-up PR that states the change.
- One row per target. A target that ships moves to Shipped with its repo and
  project page links. A target that is split keeps its original row and adds
  a row for the new part, with a note on the split.
- A new candidate joins Proposed only with all six scores, a slice, a main
  claim, and an oracle. A candidate with no repo is not work to claim yet.
- Check this file against the plan issues before reusing a status in a
  report. Plan issues and draft PRs change faster than this list.
- Mission issue 12 is history, not a second list. Its eight targets are
  fully integrated above. Future status changes go here, not there.
