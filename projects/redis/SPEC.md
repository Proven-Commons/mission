# Specification: RESP2 parser and small key-value store

Status: draft for review. The verified bar needs a reviewer who did not write
this specification to approve it. Until that happens, this project must not be
called verified.

Each rule names the Lean definition or theorem that states it.

## 1. Wire values (RESP2)

Source: the Redis serialization protocol, RESP2 part
(https://redis.io/docs/latest/develop/reference/protocol-spec/). Lean: `Resp.Value`, `Resp.encode`.

| Kind | Bytes | Rule |
| --- | --- | --- |
| simple string | `+` line `\r\n` | the line holds no CR and no LF |
| error | `-` line `\r\n` | the line holds no CR and no LF |
| integer | `:` number `\r\n` | signed 64-bit: from -2^63 to 2^63 - 1 |
| bulk string | `$` length `\r\n` bytes `\r\n` | any bytes; the length is the byte count |
| null bulk string | `$-1\r\n` | |
| array | `*` count `\r\n` values | count values follow, each any kind, nested to any depth |
| null array | `*-1\r\n` | |

The well-formed values are those meeting the rules above (`Resp.Value.WF`).

Numbers are written in canonical decimal: digits only, no `+`, no leading
zero except for `0` itself, and `-` only in front of a non-zero integer
(`Resp.encNat`, `Resp.encInt`). Lengths are `-1` or a canonical natural number
(`Resp.parseLen`).

## 2. Parser requirements

The parser (`Resp.decode`) reads one value from the front of a byte string and
returns the value and the bytes after it, or fails.

- **P1 Total.** It returns a result for every input. It never crashes and never
  loops. (It is a total Lean function; the build checks this.)
- **P2 Round trip.** For every well-formed value `v` and every byte string
  `rest`, `decode (encode v ++ rest) = some (v, rest)`. (`Resp.decode_encode`)
- **P3 Exactness.** If `decode bs = some (v, rest)`, then `v` is well formed and
  `bs = encode v ++ rest`. The parser accepts no other spelling of a value: no
  leading zeros, no `+5`, no `-0`, no bare CR or LF in a line, no missing CR LF
  after a bulk payload, no RESP3 types. (`Resp.decode_sound`)
- **P4 No over-read.** The bytes left over are a suffix of the input.
  (`Resp.decode_suffix`)
- **P5 Unique printing.** Two different well-formed values never print to the
  same bytes. (`Resp.encode_injective`)

## 3. Store requirements

The store maps byte-string keys to byte-string values (`Resp.Store`).

- **S1** After `set k v`, `get k` returns `v`. (`Store.get_set_self`)
- **S2** `set k v` leaves `get k'` unchanged for every `k' ≠ k`. (`Store.get_set_other`)
- **S3** After `del k`, `get k` returns nothing. (`Store.get_del_self`)
- **S4** `del k` leaves `get k'` unchanged for every `k' ≠ k`. (`Store.get_del_other`)
- **S5** No key is stored twice. (`Store.keys_set_nodup`)

## 4. Commands

A request is a RESP array of bulk strings: the command name and its arguments.
Names are matched without regard to ASCII case. `Resp.exec` runs one command.

| Command | Reply |
| --- | --- |
| `PING` | `+PONG` |
| `PING msg` | bulk `msg` |
| `ECHO msg` | bulk `msg` |
| `SET key value` | `+OK` |
| `SET key value extra...` | `-ERR syntax error` (options such as `NX` and `EX` are not supported) |
| `GET key` | bulk value, or `$-1` if absent |
| `DEL key...` | integer: keys removed (a key named twice counts once) |
| `EXISTS key...` | integer: keys present (a key named twice counts twice) |
| `APPEND key value` | integer: new length; a missing key starts empty |
| `STRLEN key` | integer: length, 0 if absent |
| wrong argument count | `-ERR wrong number of arguments for '<name>' command`, name in lower case |
| any other name | `-ERR unknown command '<name>', with args beginning with: <args>` in Redis 7.0 form |

An empty request (`*0\r\n`) gets no reply.

Required properties:

- **C1** A `GET k` after `SET k v` replies with bulk `v`. (`Resp.get_after_set`)
- **C2** A `SET k v` leaves the `GET` reply for every other key unchanged. (`Resp.get_after_set_other`)
- **C3** A `GET k` after `DEL k` replies `$-1`. (`Resp.get_after_del`)
- **C4** The server reads back exactly the request a client printed.
  (`Resp.parseRequest_encodeRequest`)
- **C5** On a byte stream of printed requests, the server answers each one in
  order exactly as running the commands one by one would, and reads every byte.
  (`Resp.serve_encodeAll`)
- **C6** Reply bytes match Redis 7.0 for every command in the table above.
  This is tested, not proved (see `tests/TEST-RESULTS.md`).

## 5. Out of scope

RESP3, inline commands, key expiry, other data types, persistence,
replication, transactions, pub/sub, `SET` options, and any Redis command not in
the table. Real Redis commands outside the table get the unknown command error
here, which differs from Redis.
