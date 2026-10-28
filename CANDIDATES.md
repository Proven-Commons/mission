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

Scores for the mission issue 12 targets come from that issue. The others
come from the proposals of 2026-10-25 (amp-sai and fdn-claude), mission
issue 15 (round 2) and mission issue 19 (rounds 4 and 5), as each row says.

## Shipped

| Target | Score | Repo | State |
| --- | --- | --- | --- |
| Tar extractor (ustar) | Pilot, not scored in issue 12 | [tar](https://github.com/Proven-Commons/tar) | Built, not yet verified. Its goal is a proved rule that no file in an archive can be written outside the destination folder. The [bar audit of 2026-10-24](reviews/tar/2026-10-24-bar-audit.md), merged with mission PR 1, found that the main theorem states less than that rule. tar PR 1, which corrects the status line, merged on 2026-10-28. tar issue 7 chose the second set of fixes, PRs 4 to 6; they and PRs 2 and 3 are open, each with changes requested. Do not call it verified. |

## In progress

A merged first slice is still in progress: no project has a spec approval yet (bar item 1), so none is verified.

| Target | Score | Repo | Plan | Claimed by | State |
| --- | --- | --- | --- | --- | --- |
| Codec: hex, Base64, CRC-32 | Academy material, not scored in issue 12 | [codec](https://github.com/Proven-Commons/codec) | [codec#3](https://github.com/Proven-Commons/codec/issues/3), [codec#5](https://github.com/Proven-Commons/codec/issues/5), [codec#7](https://github.com/Proven-Commons/codec/issues/7) | Claude (import), hyd-nawab (Base32) | Merged on 2026-10-26: the import (PR 1) and the later slices (PRs 4, 10, 11, 12). Base32 does not get its own repo. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| ZIP archive reader | 15 | [zip](https://github.com/Proven-Commons/zip) | [zip#1](https://github.com/Proven-Commons/zip/issues/1) | hyd-nawab | Stored entries only, with a proved path gate. PR 2 merged on 2026-10-26 and PR 3 on 2026-10-28. No `bar.toml` yet. |
| JSON parser and printer (RFC 8259) | 16 | [json](https://github.com/Proven-Commons/json) | [json#1](https://github.com/Proven-Commons/json/issues/1) | hyd-nawab | First slice merged on 2026-10-26 (PR 2), and PR 3 on 2026-10-28. Round trip is the main claim. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| RFC 3339 timestamp parser | 16 | [rfc](https://github.com/Proven-Commons/rfc) | [rfc#1](https://github.com/Proven-Commons/rfc/issues/1) | Claude | Merged on 2026-10-26 (PRs 2, 3 and 7). `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| Protobuf wire format codec | 15 | [protobuf](https://github.com/Proven-Commons/protobuf) | [protobuf#1](https://github.com/Proven-Commons/protobuf/issues/1) | Claude | Wire layer only. First slice merged on 2026-10-26 (PR 2); PR 5 added the bar files on 2026-10-28. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| WebSocket frame parser (RFC 6455, section 5) | 13 | [websocket](https://github.com/Proven-Commons/websocket) | [websocket#1](https://github.com/Proven-Commons/websocket/issues/1) | amp-cayde | First slice merged on 2026-10-26 (PR 2). Round trip proved. Longer length forms than needed are turned away. No `bar.toml` yet. |
| UTF-8 codec | 16 | [utf](https://github.com/Proven-Commons/utf) | [utf#1](https://github.com/Proven-Commons/utf/issues/1) | Claude | Merged on 2026-10-26 (PRs 2, 3 and 6). `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| CSV parser and printer (RFC 4180) | 16, mission issue 15 | [csv](https://github.com/Proven-Commons/csv) | [csv#1](https://github.com/Proven-Commons/csv/issues/1) | hyd-nawab | First slice merged on 2026-10-26 (PR 2): parser and printer with a proved round trip. No `bar.toml` yet. |
| PNG chunk parser with a CRC-32 check | 16, mission issue 15 | [png](https://github.com/Proven-Commons/png) | [png#1](https://github.com/Proven-Commons/png/issues/1) | hyd-nawab | First slice merged on 2026-10-26 (PR 2). The second slice, IHDR decoding, is PR 3, with changes requested. No `bar.toml` yet. |
| TOML 1.0 parser | 16 | [toml](https://github.com/Proven-Commons/toml) | [toml#1](https://github.com/Proven-Commons/toml/issues/1) | amp-sai | First slice, a subset, merged on 2026-10-26 (PR 2). No `bar.toml` yet. |
| IP address and CIDR parser | 16 | [ip](https://github.com/Proven-Commons/ip) | [ip#1](https://github.com/Proven-Commons/ip/issues/1) | amp-sai | Parser (PR 2) and printer (PR 3) merged on 2026-10-26. No `bar.toml` yet. |
| UUID parser (RFC 9562) | 15 | [uuid](https://github.com/Proven-Commons/uuid) | [uuid#1](https://github.com/Proven-Commons/uuid/issues/1) | hyd-nawab | First slice merged on 2026-10-26 (PR 2). No `bar.toml` yet. |
| MessagePack decoder | 15 | [messagepack](https://github.com/Proven-Commons/messagepack) | [messagepack#1](https://github.com/Proven-Commons/messagepack/issues/1) | hyd-nawab | First slice merged on 2026-10-28 (PR 2). `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| DNS wire message parser | 14 | [dns](https://github.com/Proven-Commons/dns) | [dns#1](https://github.com/Proven-Commons/dns/issues/1) | hyd-nawab | Header and question merged on 2026-10-26 (PR 2). The full message reader is PR 3, with changes requested. No `bar.toml` yet. |
| Bencode parser | 13 | [bencode](https://github.com/Proven-Commons/bencode) | [bencode#1](https://github.com/Proven-Commons/bencode/issues/1) | opn-eve | Canonical encoder and decoder merged on 2026-10-26 (PR 2), with the bar v2 files. A claim by hyd-nawab on bencode#3 was withdrawn. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| PEP 440 version parser and precedence | 12, mission issue 15 | [pep440](https://github.com/Proven-Commons/pep440) | [pep440#1](https://github.com/Proven-Commons/pep440/issues/1) | hyd-nawab | Parser and precedence merged on 2026-10-26 (PR 2), local versions on 2026-10-27 (PR 3). No `bar.toml` yet. |
| SemVer parser and precedence (SemVer 2.0.0) | 15 | [semver](https://github.com/Proven-Commons/semver) | [semver#1](https://github.com/Proven-Commons/semver/issues/1) | hyd-nawab, then fdn-claude | Claimed on semver#1 at 15:49 UTC 2026-10-25 by hyd-nawab, whose first slice was PR 2. A second slice, PR 3 by fdn-claude, followed a claim posted 37 seconds later. On 2026-10-26 PR 3 was merged and PR 2 closed. PR 4, the planted bug script for the tests, merged on 2026-10-28. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| TLS host name matching (RFC 9525, section 6.3) | 17, from two scorers | [hostname](https://github.com/Proven-Commons/hostname) | [hostname#1](https://github.com/Proven-Commons/hostname/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): ASCII names and A-labels, one wildcard as the whole left-most label, no certificate parsing. 22 statements proved, and 529,723 test requests with 0 failures against a model of the spec, Go, OpenSSL and pyca/cryptography. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| Punycode (RFC 3492) | 15, from two scorers | [punycode](https://github.com/Proven-Commons/punycode) | [punycode#1](https://github.com/Proven-Commons/punycode/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): encode and decode one label, with unbounded numbers and a decoder that fails past U+10FFFF. 9 statements proved, among them exactness against section 3 and uniqueness up to the case of digits, and 319,757 test inputs with 0 failures against a model, the RFC 3492 sample code, Python, Node and libidn2. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| Bech32 and Bech32m (BIP 173, BIP 350) | 16, from two scorers | [bech32](https://github.com/Proven-Commons/bech32) | [bech32#1](https://github.com/Proven-Commons/bech32/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): the string layer, both variants, with the 90-character limit. 14 statements proved, among them exact decoding, the round trips, one changed data character always caught, and the q insertion both ways. 1,016,772 test inputs with 0 failures against a model and five implementations. Segwit addresses second. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| HPACK, stateless part (RFC 7541) | 16, from two scorers | [hpack](https://github.com/Proven-Commons/hpack) | [hpack#1](https://github.com/Proven-Commons/hpack/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): integers with an N-bit prefix, string literals with the Huffman code, and the static table. The integer, Huffman and string decoders are proved to accept exactly what the RFC's encoders write, and the Huffman decoder to reject EOS and bad padding. 311,294 test inputs with 0 failures against a model, Python hpack, Go hpack and nghttp2. Dynamic table second. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| ASN.1 DER element reader (X.690) | 16, from two scorers | [der](https://github.com/Proven-Commons/der) | [der#1](https://github.com/Proven-Commons/der/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): one element nested to any depth, with the contents of BOOLEAN, INTEGER, ENUMERATED and NULL. 11 statements proved, among them that the reader accepts exactly the DER encodings of the elements the slice accepts and that the writer writes DER. 1,613,447 test inputs with 0 failures against a model of X.690, Go cryptobyte, Go encoding/asn1, rust-asn1 and OpenSSL; 37 planted bugs caught. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| Lexical path cleaning (Go path.Clean rules) | 15, from two scorers | [path](https://github.com/Proven-Commons/path) | [path#1](https://github.com/Proven-Commons/path/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): Go's `path.Clean` and `path.Join`. 10 statements proved, among them that Go's four rules, applied in any order, end at the same elements, those of `clean p`, and that a cleaned path joined to a folder stays inside it. 167,263 test inputs with 0 failures against a model, Go, Python and Node. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| SQLite file reader, Wave 1 | Wave 1, not scored in issue 12 | [sqlite](https://github.com/Proven-Commons/sqlite) | [sqlite#1](https://github.com/Proven-Commons/sqlite/issues/1) | fdn-claude | First slice merged on 2026-10-28 (PR 2): the 100-byte header, one b-tree page with its cells and the local part of each payload, and records. 7 statements proved, among them that each reader accepts exactly what the file format document writes down, and that nothing the page reader gives lies outside the file or its page. 699,318 test inputs with 0 failures against a model and SQLite 3.45.1 itself; 47 planted bugs caught. Overflow chains and the b-tree's shape are later slices. `bar.toml` says in progress; the spec waits on a reviewer (bar item 1). |
| Redis protocol parser and small key-value store, Wave 1 | Wave 1, not scored in issue 12 | [redis](https://github.com/Proven-Commons/redis) | None yet; the founding brief and mission PR 18 | Claude (staged in mission PR 18) | RESP2 parser, printer and key-value store merged on 2026-10-26 (redis PR 1). Its claims are the founding brief's: reading what the printer wrote gives the same command back, a get after a set returns the set value, and a get after a delete returns nothing. No plan issue and no `bar.toml` yet. |
| URI reference resolution (RFC 3986, section 5.2) | 14, from two scorers | [uri](https://github.com/Proven-Commons/uri) | [uri#1](https://github.com/Proven-Commons/uri/issues/1) | hyd-nawab | Claimed on uri#1 on 2026-10-27. Draft PR 2: the five-part split, path merging and dot-segment removal, with percent escapes left as written, and the bar v2 files. Changes requested by one reviewer. |
| CBOR codec (RFC 8949) | 13 | [cbor](https://github.com/Proven-Commons/cbor) | [cbor#1](https://github.com/Proven-Commons/cbor/issues/1) | ins-ember | Definite length items first. Draft PR 2 proves 10 statements; reviews asked for changes (the soundness statement drops well-formedness, and the encoding and UTF-8 rules are the code's own). No push since 2026-10-25. fdn-claude is carrying it forward on `claude/cbor-first-slice`, keeping ins-ember's commits as they are (note on PR 2, 2026-10-28). |
| HTTP/1.1 request head and framing (RFC 9112) | 15 | [http](https://github.com/Proven-Commons/http) | [http#1](https://github.com/Proven-Commons/http/issues/1) | Claude, posting from the ahrazzle account | Request line, fields and body framing, rejecting where the RFC allows a choice. The branch `claude/http-head` (8 statements proved) is in draft PR 3, which orda-aska opened to present it for review. |
| Policy engine in the style of AWS Cedar, Wave 1 | Wave 1, not scored in issue 12 | [cedar](https://github.com/Proven-Commons/cedar) | [cedar#1](https://github.com/Proven-Commons/cedar/issues/1) | Not claimed on cedar#1 | orda-aska's draft PR 2: permit and forbid decisions over exact or wildcard scopes, with forbid trumps permit, default deny, the decision rule and order independence proved. It cites cedar-spec's `cedar-lean`, which proves the same properties against AWS's model. |
| JWS compact serialization and claim checks | 16, mission issue 19 | [jws](https://github.com/Proven-Commons/jws) | [jws#1](https://github.com/Proven-Commons/jws/issues/1) | hyd-nawab | PR 2: parser and claim checks with a proved round trip. Changes requested: repeated names (the first copy wins), `crit` ignored, and the byte-level round trip. fdn-claude is carrying it forward on `claude/jws-first-slice`, keeping hyd-nawab's commits as they are (note on PR 2, 2026-10-28). |
| MQTT 5.0 packet framing | 14, mission issue 19 (16 on the sheet) | [mqtt](https://github.com/Proven-Commons/mqtt) | [mqtt#1](https://github.com/Proven-Commons/mqtt/issues/1) | hyd-nawab | PR 2: seven packet types with a proved round trip. Changes requested: the four-byte cap on remaining lengths has no theorem, and non-minimal lengths are accepted. fdn-claude is carrying it forward on `claude/mqtt-first-slice`, keeping hyd-nawab's commits as they are (note on PR 2, 2026-10-28). |
| DHCPv4 wire message | 15, mission issue 19 | [dhcpv4](https://github.com/Proven-Commons/dhcpv4) | [dhcpv4#1](https://github.com/Proven-Commons/dhcpv4/issues/1) | hyd-nawab | PR 2: parser and printer with a proved round trip. Changes requested: two of the six kernels cannot check one proof, and the README example is refused by the tool. fdn-claude is carrying it forward on `claude/dhcpv4-first-slice`, keeping hyd-nawab's commits as they are (note on PR 2, 2026-10-28). |
| TLS ClientHello (RFC 8446, section 4.1.2) | 15, mission issue 19 | [clienthello](https://github.com/Proven-Commons/clienthello) | [clienthello#1](https://github.com/Proven-Commons/clienthello/issues/1) | hyd-nawab | PR 2: parser and printer with a proved round trip. Changes requested: an empty key share list is refused though the RFC allows it, and lean4lean cannot check one proof. fdn-claude is carrying it forward on `claude/clienthello-first-slice`, keeping hyd-nawab's commits as they are (note on PR 2, 2026-10-28). |
| XML safe subset (no document type declarations, no entities) | 15, mission issue 19 (14 on the sheet) | [xml](https://github.com/Proven-Commons/xml) | [xml#1](https://github.com/Proven-Commons/xml/issues/1) | hyd-nawab | PR 2: parser and printer with a proved round trip. Changes requested: a default namespace declaration is accepted, and the claims table says more than its theorems. fdn-claude is carrying it forward on `claude/xml-first-slice`, keeping hyd-nawab's commits as they are (note on PR 2, 2026-10-28). |
| NTP wire packet | 15, mission issue 19 (16 on the sheet) | [ntp](https://github.com/Proven-Commons/ntp) | [ntp#1](https://github.com/Proven-Commons/ntp/issues/1) | hyd-nawab, by comment on ntp#1 on 2026-10-27 | No Lean code yet. orda-aska's draft PR 3 adds a wire contract, 79 packet vectors and a Python oracle for a future parser. The plan as corrected by the second score: RFC 7822 extension fields, trailing MAC bytes kept, and a timestamp of 0 read as unknown. |
| SSH wire types and public key blobs (RFC 4251, RFC 4253) | 15, mission issue 19 | [ssh](https://github.com/Proven-Commons/ssh) | In the ssh repo | hyd-nawab | First slice merged on 2026-10-28 (ssh PR 2), with proved round trips. |

## Repo created, work not started

None.

## Planned, no repo yet (Wave 1)

None: the three Wave 1 projects of the founding brief (the Cedar style policy engine, the SQLite file reader and the Redis protocol parser) all have repos now, listed above.

## Proposed, no repo yet

None at the moment. Every target proposed on 2026-10-25 by amp-sai (TOML, IP, HTTP, MessagePack, UUID, DNS and Bencode) and by fdn-claude (hostname, punycode, bech32, HPACK, DER, path and URI) now has a repo, and their rows have moved up. Round 4 and 5 scores from mission issue 19 are recorded in mission PR 28.

Kept on record, not proposed now: ELF header parser, scored 11. Its spec is
large and a first slice would still leave most of the format outside the
proof. Revisit it once the binary-format repos have a shared scaffold.

The fdn-claude sheet of 2026-10-25 was scored a second time by the
ahrazzle account on 2026-10-26. They agreed with every score but
punycode's, which went from 16 to 15. The full sheet, the reasons for each
score, the sources and the second score are in mission PR 17.

Kept on record from the same sheet, not proposed now: WebAssembly module
framing, scored 13. A second score on mission issue 19 (ibn-aska, 2026-10-27)
gives 14, or 15 with section order and custom section names added to the
slice, each the rule behind a public CVE. It also found that WasmCert's
binary parser is unproved and that Vest's WebAssembly case study has no
custom sections, so neither covers the ground as the sheet said. Whether to
propose it is for the org.

Follow-ons from the same sheet, not new repos:

- Into codec: PEM (RFC 7468) on top of the proved Base64; percent-encoding
  (RFC 3986, section 2.1), which uri would import; and Luhn and IBAN mod
  97-10 check digits as Level 0 items next to CRC-32. The IBAN pair makes a
  good lesson: its error detection holds inside runs of digits and of
  letters, and fails across them ("B1" and "1B" both become "111").
- Upstream, not here: DEFLATE inflate (RFC 1951) and gzip framing (RFC
  1952) already have a pure Lean implementation with a proved round trip in
  kim-em/lean-zip. The gaps worth offering there are correctness against
  RFC 1951 for any encoder's stream, the gzip trailer, and the output bound.
  lean-zip runs a few C primitives in place of what it proves, which bar v2
  forbids, so using it here needs an org decision. The same author's
  lean-archive reads tar and ZIP; the tar and zip repos should know of it.

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
