# 星云驿 Project Status

Last updated: 2026-08-25

Frozen handoff stage: `v0.1.0-local.1`; current source and pinned production release: `0.1.6`

## Current-versus-historical Connector presentation (deployed, 2026-08-25)

Authenticated real-page inspection found that `mars` owns **one durable Agent**
(`magent@agentpost.me`) with one current Codex Connector and three replaced Connector records. The
old WorkBuddy/Codex rows were audit history, but 星轨 rendered them beside the current connection,
which made one Agent look like four Agents and made the Human expect a delete button on every row.

Release `e378a7e` / package `0.1.6` separates those concepts without deleting data. “Agent 连接” now
shows current Connectors by default and folds replaced/revoked records under “查看 N 条历史连接记录”.
It explicitly explains that those records are not separate Agents. “我的 Agent” remains the durable
identity list; every real Agent card offers independent reconnect, disconnect, short-name edit, and
`删除 Agent`. Existing Agent IDs, addresses, Inbox, Thread, messages, ACLs, Connector records, and
audit history are unchanged.

The immutable production paths are `/opt/agentpost/releases/e378a7e` and
`/opt/agentpost/venvs/e378a7e`; server, Python SDK, and MCP report `0.1.6`. Schema remains
`0020_pairing_agent_intent`. The public wheel SHA-256 is
`c896e6254fa2e7a00dbcffed0485fa49e87846c6a4d8a1abf66b28dba68e133e`. The verified pre-cutover
backup is `/opt/agentpost/backups/20260825-1749-e378a7e-pre-016/`, with PostgreSQL dump, attachment
archive, protected configuration, previous 0.1.5 wheel, and guarded application-only rollback.
Two earlier incomplete backup directories (`20260825-1746-e378a7e-pre-016` and
`20260825-1747-e378a7e-pre-016`) were preserved and were not used as rollback points.

Local evidence remains **363 passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests
deselected**, plus **10 MCP**, **4 TypeScript Connector**, and **10 focused Human-control** tests;
Ruff/format, JavaScript syntax, wheel isolation, and diff checks pass. Post-cutover checks verified
active services, aligned component versions, unchanged migration head, public health/readiness,
wheel digest, Nginx, backup readability, and a clean fatal-error journal scan. The authenticated
星轨 page showed one current Connector, “查看 3 条历史连接记录”, one real Agent, and the
`删除 Agent` button. No Agent or Connector was deleted during verification.

Current evidence is `connector_history_ux_deployed_https_verified`, not `production_accepted`.
Real-user lifecycle acceptance still requires the Human to connect a genuinely separate WorkBuddy
and verify both Agent cards independently.

## Multi-Agent simultaneous connection and per-Agent control (deployed, 2026-08-25)

Tester `020` exposed a real product defect: after a WorkBuddy pairing, the existing Codex lost its
connection. The storage model already allowed one Human to own many Agents and one current Connector
per Agent; the defect was in 星轨's default approval policy. When the Human owned exactly one Agent,
the browser silently selected that Agent for every new pairing, so the backend correctly treated the
new WorkBuddy Connector as a replacement for the Codex Connector on the same durable Agent.

The deployed source now makes the two intents explicit without asking the Human for technical input:

- “连接新的 Agent” always creates a new independent Agent, even when the Human already owns one or
  many Agents. Each copied code carries an opaque new-Agent intent so two same-host Agents on the
  same device use separate OS-vault profiles instead of restoring one another.
- “连接/重新连接” on an existing Agent card carries that Agent's UUID as a short-lived target
  intent. The approval page verifies current-Human ownership, binds only that Agent, and rejects a
  target mismatch. This is the only path that may replace an existing Agent's current Connector.
- Automatic addresses are readable and globally checked, using Human name, Connector type, and a
  sequence, for example `mars-codex-001@agentpost.me` and `mars-workbuddy-001@agentpost.me`.
  Existing addresses are unchanged.
- 星轨 now reports the count of current connected Agents instead of presenting recent activity as
  the connection count. Every owned Agent card shows its own connected/disconnected state and offers
  connect/reconnect, disconnect, short-name edit, and delete actions.
- Delete is a soft delete: it revokes only that Agent's current Connector and hides the Agent from
  the active dashboard, while retaining the immutable Agent ID/address, ownership, Inbox, Thread,
  ACL, Connector records, and message history for audit continuity.

The production schema head is `0020_pairing_agent_intent`. Release `20afebd` is deployed at
`/opt/agentpost/releases/20afebd` with server, Python SDK, and MCP all reporting `0.1.5`; the public
wheel SHA-256 is `38dc93bdb9de5938b56d5fb95403ce50e0044b7e3b26304fcf7fb07bcf84b1f7`.
The package-boundary regression prevents a future release from advertising a newer server while
shipping older SDK/MCP versions.

Local evidence is **363 passed, 1 explicit sandbox skip, and 5 PostgreSQL tests deselected**, plus
**10 MCP tests** and **4 TypeScript Connector tests**. Ruff/format, JavaScript syntax, skill/plugin
bootstrap parity, Alembic single-head, diff, and PostgreSQL offline SQL generation checks pass.
Before cutover, a disposable real PostgreSQL database completed `0019 -> 0020 -> 0019 -> 0020` and
verified the new UUID intent column and index. After cutover, AgentPost, Nginx, and PostgreSQL were
active; local/public health and readiness reported `0.1.5`; the pinned public wheel hash matched;
星轨 exposed per-Agent connect/reconnect, disconnect, handle edit, and delete controls; and the
service journal was clean.

The verified 0.1.5 pre-cutover backup is
`/opt/agentpost/backups/20260825-1655-20afebd-pre-015/`; it contains the PostgreSQL dump,
attachments, protected environment, systemd/Nginx configuration, the 0.1.4 wheel, checksums, and a
guarded immediate rollback script. A first 0.1.4 cutover exposed a too-short readiness wait and was
forward-recovered without deleting data; the rollback script was corrected to use migration-aware
0.1.4 code before restoring 0.1.3. Package `0.1.5` then superseded 0.1.4 because the latter had
server/SDK/MCP version skew and the immutable 0.1.4 artifact was not overwritten.

Current evidence is `multi_agent_connection_deployed_https_verified`, not
`production_accepted`. Real external-Human experience still requires `020` to verify Codex and
WorkBuddy stay connected simultaneously and `mars` to verify per-card disconnect/reconnect,
handle change, and history-preserving delete.

The current Codex initially hit HTTP 409 because its first short-lived Pairing had already reached
`PAIRING_EXPIRED`; the state machine correctly refused an expired-to-authorized transition. A new
Pairing targeted the same Agent ID, completed one Human webpage authorization, restored the scoped
OS-vault profile, and preserved `magent@agentpost.me` and its history. The original task then resumed
without another technical question. Resolver-first sends for “用户020的 Agent” and “用户ianw的
Agent” each returned a unique real recipient and were delivered with zero attachments:
`msg_b6a4a837574c4b4aadf52d2f068118b8` and
`msg_1cc63d9025774d159b2df15b0a1f7724`. This proves the requested reconnect/resume/send slice, but
delivery does not prove that either recipient has read the message or accepted the release.

## OpenClaw real-CLI compatibility gate (local, 2026-08-25)

The ordinary-user OpenClaw path uses the shared stdio MCP adapter, not the older optional native
HTTP plugin. Production serves `AP-OPENCLAW-V1 https://agentpost.me/connect/openclaw` and pins the
0.1.5 wheel. A temporary, isolated install of the official OpenClaw `2026.7.1-2` package ran on Node
24.19.0 and confirmed that `openclaw mcp set`, `show`, `doctor`, and `probe` use
`mcp.servers` in `~/.openclaw/openclaw.json`. The original real OpenClaw probe launched the
then-production 0.1.3
`agentpost-mcp` binary and discovered all seven AgentPost tools, including
`agentpost_resolve_recipient`. The protocol-only probe used an explicitly fake temporary credential;
no real long-lived key was printed or written outside `/private/tmp`.

The check exposed an acceptance defect: OpenClaw can return exit code zero from `mcp probe` while
reporting a failed server in its JSON diagnostics. The source adapter now performs `mcp set` and a
live JSON `mcp probe`, requires the complete seven-tool set with no diagnostics, and only then
returns `status=configured`. It also reports the correct config path precedence for
`OPENCLAW_CONFIG_PATH`, `OPENCLAW_STATE_DIR`, and `OPENCLAW_HOME`. The local regression is **356
passed, 1 sandbox skip, 5 PostgreSQL tests deselected**, plus **10 MCP tests**; the focused OpenClaw
selection is 43 passed, and Ruff/format/diff checks pass.

This strengthened setup gate is included in the pinned production 0.1.5 wheel, but the real
OpenClaw CLI probe has not been repeated after that cutover.
No Human has yet completed the real OpenClaw paste-code, browser authorization, OS-vault profile,
natural-language send/receive, and restart-persistence flow. The optional native OpenClaw tool
plugin also remains a separate unaccepted path: its current `plugins build/validate` run against
OpenClaw `2026.7.1-2` stopped in the OpenClaw plugin loader before validation. Current evidence is
`openclaw_mcp_host_compatibility_locally_verified`, not `production_accepted`.

## Ianw controlled-test correction (2026-08-25)

The first real `ianw` recipient test failed in Codex even though production stored the active Agent
handle `ianw`, Human display name `Ianw`, and active Codex Connector correctly. The cause was the
sender-side installation: Codex was still running AgentPost 0.1.1 with six MCP tools, while its
personal plugin was still the 0.1.2 skill that used the legacy Directory path. It had not loaded the
0.1.3 `agentpost_resolve_recipient` tool.

At that checkpoint, the test machine ran server, SDK, and MCP 0.1.3 with the seven-tool adapter, and the
personal AgentPost plugin is installed as `0.1.3+codex.20260825045435`. Using the existing OS-vault
identity, read-only production resolver calls for both “给ianw agent发信息” and “给用户Ianw的codex发
信息” returned one verified `ianw` match. No test message was sent. A new Codex task is required to
load the refreshed plugin and MCP tool list.

The skill now treats a missing resolver as an outdated partial MCP, automatically runs the
server-pinned bootstrap with the original operation, and forbids a legacy Directory not-found
answer. The same test also exposed that the public bootstrap's `dataclass(slots=True)` fails under
the macOS system Python used by the copyable prompt. Source and plugin copies are compatible now and
have a system-Python regression test. The corrected bootstrap and aligned seven-tool packages are
now public in 0.1.5, while the current Codex identity still requires its one-time reconnect approval
before an authenticated send can be claimed. This remains a controlled-test correction, not
`production_accepted`.

## Human/handle recipient resolution (deployed, 2026-08-25)

Commits `1abbf56`, `213bc9e`, and `10f4d14` implement the ordinary-user recipient naming layer
without changing the immutable Agent identity. `Agent.id` and canonical `Agent.address` remain the
Inbox, Thread, Delivery, ACL, Connector, and history keys. An optional globally unique `handle` is a
separate mutable alias: 3-32 lowercase ASCII characters, beginning with a letter and containing
letters, digits, or single internal hyphens. Reserved words are rejected; conflicts return short,
deterministic alternatives instead of random identifiers.

`POST /api/v1/directory/resolve` is now the single verified resolution path. It checks full address,
exact handle, exact scoped Agent display name, scoped Human owner plus Agent type/name, and finally
scoped fuzzy contact/organization matches. Full address and handle remain explicit identifiers;
Human-name, display-name, and fuzzy discovery is restricted to the same owner, a shared active
organization, previous correspondence, or an explicit inbound allow rule. The response is exactly
`resolved`, `needs_clarification`, or `not_found`, retains `external_agent_content`, and never
synthesizes `<input>@agentpost.me`. The existing delivery ACL remains authoritative after
resolution.

The Python SDK exposes `resolve_recipient`; the CLI uses it for `--recipient`; MCP now exposes seven
tools including `agentpost_resolve_recipient`; and both installed Skill copies require resolver-first
behavior and friendly one-question disambiguation. Existing `--to` and full-address HTTP sends remain
compatible. 星轨 lets the Human owner set or change a handle during Pairing or from “我的 Agent”.
Agent cards show the handle first, keep the display name visible, and place the immutable technical
address behind “查看底层身份”.

Local evidence: the fast suite reports **352 passed, 1 explicit skip, and 5 PostgreSQL tests
deselected**; the independent package-local MCP suite reports **10 passed**. Ruff,
`git diff --check`, TypeScript Connector tests, and browser JavaScript syntax pass. Integration tests
prove that two handle changes preserve the same Agent ID/address, Message, Thread, Delivery, ACL,
Connector binding, Connector instance, dashboard relationship, and audit trail.

Release `6ada188` is deployed at `/opt/agentpost/releases/6ada188` with package `0.1.3`, runtime
`/opt/agentpost/venvs/6ada188`, and production migration `0019_agent_handles`. An isolated real
PostgreSQL database ran the five opt-in acceptance tests successfully before cutover. The public
wheel SHA-256 is `c157dbfd7dbdfd1697c9c85651455beec30e7679062aa9e9b91cea1fd0956757`; a clean
Python 3.12 environment installed that exact download and reported server, SDK, and MCP version
0.1.3. Production Agent, Message, Delivery, and Attachment counts remained unchanged across the
migration. The authenticated 星轨 page preserved the existing Agent and messages, exposed the
friendly short-name editor and hid the immutable address behind the technical-identity disclosure.

The verified pre-cutover backup and immediate rollback script are under
`/opt/agentpost/backups/20260825-1210-5a5b509-pre-013/`. A fresh Alibaba Cloud snapshot could not be
created because the account had reached its snapshot quota; no older snapshot was deleted, and the
existing provider snapshots remain available. No external tester has yet completed the Zhang
Ziliang/`kcode`, same-name Human, multiple-Codex, not-found, legacy-address, and rename-continuity
cases against production. The current label is `recipient_resolution_deployed_https_verified`, not
`production_accepted`.

## Ordinary-user host selection and cold-start release (2026-08-25)

Commit `8e7f105` is deployed at `https://agentpost.me` as release `0.1.2`. This release supersedes
the rejected host-neutral sentence below. The authenticated 星轨 “连接新的 Agent” dialog now asks
the Human to choose only Codex, WorkBuddy, or OpenClaw and then presents one complete block to paste
into that Agent's ordinary chat. It does not ask for an operating system, command, URL, package
version, profile, Agent address, Pairing ID, API key, or other technical parameter.

Each pasted block contains a host-specific short code and public Agent-facing contract:
`AP-CODEX-V1 https://agentpost.me/connect/codex`, `AP-WORKBUDDY-V1
https://agentpost.me/connect/workbuddy`, or `AP-OPENCLAW-V1
https://agentpost.me/connect/openclaw`. The Agent identifies the operating system, downloads the
same-origin bootstrap, verifies its published SHA-256, installs the pinned Connector into an
isolated runtime, opens one short-lived 星轨 authorization page, stores the credential only in the
operating-system vault, registers its own MCP host, and returns to the original chat.

Production evidence: AgentPost, Nginx, and PostgreSQL remained active after the cutover; local and
public health/readiness passed; all three public connection contracts passed; the public bootstrap
digest is `bf94338e5e54842982ebe13d538e9fd59c43576df87078dff33af06678a2f6c4`; and the pinned
0.1.2 wheel digest is `29ab87057c214b283401732982b2fe85d620085e6ad98b04a306e49a466fcc99`.
The authenticated real page was exercised through all three selections and returned the expected
single paste block for each host. A no-AgentPost/no-Codex-config isolated macOS environment fetched
the public bootstrap, installed 0.1.2, and reached exactly one short-lived 星轨 authorization URL.
That test pairing was intentionally stopped before approval so it would not replace the Human's
current sole Agent Connector.

The local regression is 327 passed and six explicit skips, Ruff passes, JavaScript syntax passes,
the clean wheel contains the cold-start bootstrap and all three host adapters, and the personal
Codex plugin is installed and enabled as `0.1.2+codex.20260825022025`. The production webpage is now
ready for controlled new-computer/new-Human testing. Complete approval-and-return on a tester's own
account, plus real WorkBuddy/OpenClaw host execution and Windows/Linux devices, remain acceptance
evidence to collect; they must not be inferred from the macOS cold-start or adapter tests.

## Post-handoff ordinary-user onboarding correction (2026-08-25)

The prior `natural_language_web_experience_ready` label was rejected by the Human and remains
withdrawn. Release `c7c7313` now corrects the actual production web path: 星轨 “连接新的 Agent”
shows one host-neutral sentence, “请连接我的星云驿。如果还没有连接，请帮我完成安装并打开授权
页面；连接好后回到这里告诉我。” The user copies it into an ordinary Agent chat. Host selection,
operating-system selection, installation commands, connection commands, profiles, addresses, and
long-lived credentials are absent from the default web path. The authenticated production page and
its copy-button result were observed in Chrome. Manual CLI material remains an operator fallback.

The implicit Codex skill now recognizes connection-only intent and can internally run the pinned
0.1.1 bootstrap, pair through one 星轨 page, and register the local MCP without asking the Human to
choose Codex or type a command. The personal Codex marketplace has the validated AgentPost plugin
installed and enabled as `0.1.1+codex.20260825013544`. A new Codex task is still required to load it
and observe a complete first-use install/pair/return cycle. WorkBuddy/OpenClaw/Windows/Linux do not
yet have equivalent native pickup. Current evidence status is
`ordinary_user_uniform_prompt_web_ready_codex_plugin_installed`, not end-user acceptance.

## Post-handoff natural-language onboarding implementation (2026-08-24)

Commits `30f8bc5` through `4b7eb68` implement the first Codex path against the agreed final
acceptance contract. Release `0.1.1` is deployed at `https://agentpost.me`; the server exposes its
immutable Connector version, HTTPS wheel URL, and SHA-256, and the Codex setup gate is enabled for
macOS only. Windows and Linux remain closed until their own real-device acceptance runs.

The repository now contains an implicitly invocable AgentPost messaging skill and a validated
repository-local Codex plugin under `plugins/agentpost`. A request such as “把这份报告发给张三的
Agent” preserves the original send as the goal. If the Connector is absent, the bootstrap installs
the server-declared wheel into the dedicated runtime with a hash-pinned direct requirement, starts
one short-lived Human Pairing, configures Codex, and delegates the original send in the same process.
It never asks the user for a server, profile, package version, Agent address, or long-lived key.
The plugin is installed in the current Human's personal marketplace; clean-user distribution and
external publication remain pending.

Natural recipient resolution now sends automatically for one Directory match and returns one
structured clarification containing all safe candidates for zero or multiple matches. The resumed
send supports local attachments and reports business acceptance separately from delivery state.
For the sender identity, 星轨 automatically creates a server-generated Agent identity when the
Human owns none, automatically uses the sole owned Agent when exactly one exists, and presents one
combined choice only when several exist. Pairing ID, one-time code, address, and capability fields
are not user inputs on the normal verification-URL path. Existing explicit Pairing API fields remain
compatible for administrative and legacy clients.

### Final acceptance contract ledger

| Acceptance item | Current evidence | Remaining gate |
| --- | --- | --- |
| One natural-language request starts first use | live uniform prompt, working copy button, and installed personal Codex plugin | run a new/clean real Codex task through the complete return cycle |
| At most one system install confirmation | one bootstrap execution and one pinned runtime install path | plugin distribution and clean-desktop observation |
| At most one web authorization | one Pairing verification URL, one reauthentication/decision transaction; production 0.1.1 metadata and 星轨 UI verified | observe the complete first-use return in Codex |
| No technical parameters or long-lived key | live default web path contains no host/OS choice or commands; skill/bootstrap/vault tests pass | user-observation acceptance |
| Unambiguous recipient/Agent is not queried | one Directory result and zero/one owned-Agent branches are automatic | real multi-account fixture |
| Ambiguity is asked once | one structured recipient clarification or one combined 星轨 Agent choice | real multiple-Agent fixture |
| Original task resumes after authorization | composite pair/configure/search/upload/send CLI test passes | real browser-return send with attachment |
| Reuse enters write approval directly | connected text flow uses MCP `writes`; attachment flow reuses runtime/profile | real second-request Codex UI acceptance |

The current full local regression reports 320 passed and six explicit skips: one expected sandbox
loopback case plus five opt-in PostgreSQL tests; the package-local MCP suite adds ten passing tests. The deployment-day
focused skill/config/onboarding/control-plane selection adds 39 passing tests. Ruff lint/format,
plugin validation, skill validation, browser JavaScript syntax, a clean-wheel `0.1.1` install, and an
isolated real Codex MCP registration pass. The published wheel SHA-256 is
`908558e6c9c83401f5b2ca0ed0da645721d06789ed803b82c21be97b0c7b16b8`.

Production serves 0.1.1 from release `c7c7313`; health/readiness, the pinned-wheel digest,
authenticated 星轨 rendering, existing Agent view, the one-sentence connection dialog, and its copy
result pass. The complete real first-use return and connected reuse send remain unobserved.
WorkBuddy/OpenClaw and Windows/Linux remain separate native host/device gates. `PROJECT_HANDOFF.md`
remains the frozen `v0.1.0-local.1` takeover record.

## Post-handoff M24 progress (2026-08-24)

Commit `c417326` adds the first host-setup orchestration slice. After installing the `mcp` and
`connector` extras, `agentpost-connect setup codex` now restores an existing vault profile or runs
the existing Human Pairing flow, reports heartbeat, registers the packaged stdio MCP through the
Codex CLI, and reapplies `default_tools_approval_mode = "writes"`. The operation is idempotent,
preserves unrelated Codex config, and stores only the server and OS-vault profile reference; it does
not copy, print, or write the long-lived Agent credential to Codex config.

Three setup unit tests and the expanded five CLI tests pass. The full local fast selection reports
310 passed, one expected loopback sandbox skip, and five deselected PostgreSQL tests; Ruff lint and
format pass, and the package-local MCP selection reports ten passed. A fresh isolated `CODEX_HOME`
was then configured with the real Codex CLI, which reported the stdio server enabled with `writes`
approval and redacted its environment values. This is local implementation evidence only: the
pinned production wheel and the production 星轨 guide have not yet been updated.

A source-built `0.1.0` candidate wheel with SHA-256
`611097964446e12ca3a149cdd9289688bea6535c10c41a32b3c12ede7fe48c63` was installed with both
extras into a clean Python 3.12.13 environment under `/private/tmp`. The installed distribution
reported AgentPost 0.1.0, MCP 2.0.0, and keyring 25.7.0; its `agentpost-connect` help exposed the new
`setup` command, and its packaged `agentpost-mcp` was registered through a second isolated real
Codex CLI configuration with redacted environment values and `writes` approval. This temporary
artifact is candidate evidence, not the pinned public download.

Commit `0786c71` stages the corresponding 星轨 release gate. The public auth configuration now
exposes an operator-controlled, validated list of `mac`, `windows`, and/or `linux` Codex setup
platforms. The list is empty by default, so current production instructions remain unchanged. Only
an explicitly enabled platform receives the `mcp,connector` install extra, `setup codex` command,
and native-tool explanation; other platforms and hosts retain the generic Connector path. The gate
passed 24 focused config/control-plane tests, JavaScript syntax validation, Ruff, and the same full
310-fast-test plus ten-MCP-test regression.

Commit `abd1d74` adds an exclusive Connector-profile identity source to the local stdio MCP.
`AGENTPOST_PROFILE` now selects the already-paired credential by exact server and profile from the
operating-system vault. The existing explicit `AGENTPOST_API_KEY` mode remains available for
server/CI use, but configuring both sources or neither source fails closed. There is no plaintext
credential-file fallback, and credentials remain absent from tool parameters and representations.

The slice passed Ruff lint/format, the unchanged 306-fast-test local regression with one sandbox
loopback skip and five deselected PostgreSQL tests, and ten package-local MCP tests. A sandbox-outside
read-only probe loaded profile `codex:MacBook-Air-2.local` from macOS Keychain without displaying the
key. A packaged `0.1.0` wheel was installed into the dedicated `~/.agentpost/runtime`, its MCP 2.x
optional dependency was installed, and a real stdio handshake discovered all six AgentPost tools.

AgentPost is now enabled in the shared Codex MCP configuration with non-secret server/profile values
and `default_tools_approval_mode = "writes"`. A fresh ephemeral Codex CLI task discovered and invoked
`agentpost_list_inbox(status=unread, limit=1)` from natural language, returned zero items with
`external_agent_content`, and performed no read/send/reply/ACK operation. This establishes
Connector-aware identity, registration, tool discovery, and one read-only natural-language call. It
does **not** yet accept the complete M24 write flow: send, explicit read, ACK, reply, Directory, Codex
desktop restart persistence, and error-redaction behavior still require end-to-end acceptance.

## Current state

This repository started as an empty directory. There was no existing application,
package manifest, test suite, database model, or Git history to reuse.

The MVP implementation is locally runnable as a protocol-first modular monolith:

- FastAPI HTTP service
- SQLAlchemy 2.x persistence layer
- PostgreSQL as the production source of truth
- Alembic migrations
- local filesystem attachment adapter with an S3-compatible boundary
- framework-neutral REST/JSON protocol
- Python SDK, optional OpenClaw/MCP adapters, and an A2A compatibility mapping
- 星轨 Human identity, Agent ownership/role grants, scoped observation API, and
  same-origin product website with revocable short-lived browser sessions and
  organization-scoped visibility, plus a CSRF/step-up-protected approval queue
- Human-authorized Agent Pairing, one-current-Connector bindings, migration,
  automatic credential claim/rotation/revocation, heartbeat, and durable Python
  and TypeScript Connector runtimes
- official `agentpost-connect` CLI for browser Pairing, operating-system vault
  credentials, send/inbox/read/ACK/reply, rotation, and durable polling
- a legacy novice-oriented 星轨 connection guide plus a normal verification-URL
  path that auto-resolves the Agent identity and hides Pairing/address fields
- an implicit Codex skill and repository-local plugin that preserve a natural
  send request across hash-pinned setup, Pairing, recipient lookup, and send
- email/password Human self-service, TOTP MFA, account recovery, Human-key
  rotation, organization invitations/self-governance, and verified domains
- first-party OAuth Device Authorization with scoped rotating tokens and an
  optional OAuth-protected Streamable HTTP Remote MCP service
- Alibaba Cloud deployment at `https://agentpost.me`, with verified DNS, TLS,
  HTTP redirect, public health/readiness, 星轨 rendering, and PostgreSQL-backed
  offline message delivery across an AgentPost restart

## Verified local environment

| Capability | Status | Evidence / boundary |
| --- | --- | --- |
| Git | available | Git 2.50.1; repository initialized on 2026-08-12 |
| Python | available | bundled Python 3.12.13 |
| `uv` | available | `/Users/mars113/.local/bin/uv` |
| Node.js | partially available | bundled Node 24.14.0; below OpenClaw's declared Node 24 minimum of 24.15.0 |
| npm / OpenClaw host | unavailable | plugin host build/validate cannot run in this environment |
| Docker / Docker Compose | unavailable | command is not installed in the current host environment |
| PostgreSQL server/client | unavailable | no local `postgres` or `psql` command discovered |

Docker Compose and PostgreSQL assets are implemented. Fast tests run against the
same repository interfaces using SQLite, while a separately marked PostgreSQL
integration suite remains the authoritative persistence check.
Until it has run on a machine with Docker/PostgreSQL, that acceptance item remains
**not locally verified** and must not be reported as production acceptance.

## Milestone ledger

| Milestone | Scope | Status |
| --- | --- | --- |
| 0 | repository audit, status, architecture, plan | complete |
| 1 | FastAPI, PostgreSQL, Compose, health/readiness, Alembic, basic tests | complete* |
| 2 | Agent identity, registration, API keys, authentication, lookup | complete |
| 3 | persistent message/inbox APIs and offline delivery | complete |
| 4 | message lifecycle, explicit read and acknowledgement | complete |
| 5 | replies and thread history | complete |
| 6 | attachment upload/download, integrity and authorization | complete |
| 7 | address/capability directory | complete |
| 8 | inbound allow/block policy | complete |
| 9 | Python SDK | complete |
| 10 | offline/restart E2E, concurrency, security, and demo | complete* |
| 11 | OpenClaw integration | complete* |
| 12 | MCP adapter | complete |
| 13 | A2A compatibility mapping and low-risk adapter surface | complete* |
| 14 | 星云驿 naming and 星轨 read-only Human control plane | complete* |
| 15 | 星轨 short-lived browser sessions and server-side revocation | complete* |
| 16 | 星轨 organizations, memberships, and organization-scoped Agent visibility | complete* |
| 17 | 星轨 browser CSRF, one-time action confirmation, and Human action audit | complete* |
| 18 | Agent-created, Human-decided approval queue and 星轨 approval UI | complete* |
| 19 | Human-authorized Agent Pairing, Connector identity, claim, and revocation | complete* |
| 20 | Human self-service authentication, MFA, recovery, key lifecycle, and organization governance | complete* |
| 21 | Connector migration, heartbeat, credential lifecycle, Python/TypeScript runtimes, and secure-store boundary | complete* |
| 22 | first-party Device OAuth and OAuth-protected Remote MCP | complete* |
| 23 | verified-domain enterprise OIDC login and explicit account linking | complete* |

## Human-friendly Agent connection evidence

Commit `b7d51b0` was the earlier production guide baseline at `https://agentpost.me`. The 星轨 Agent connection
surface now guides a nontechnical Human through three visible steps: choose the
tool, connect on the local computer, and return to 星轨 for identity confirmation.
It has distinct Codex, WorkBuddy, OpenClaw, and generic-tool choices and generates
macOS, Windows, or Linux instructions without exposing a long-lived Agent key.
The existing secure Pairing approval, new-Agent/existing-Agent migration,
ownership check, address selection, password/MFA reauthentication, and automatic
Connector credential claim remain unchanged behind the guide.

Local validation passed 305 fast tests with one expected sandbox-only loopback
skip and five explicitly deselected external/PostgreSQL tests. Fifteen targeted
Human control-plane tests and eight MCP adapter tests passed; JavaScript syntax,
HTML ID uniqueness, and `git diff --check` also passed. On Alibaba Cloud, the
three UI assets matched local SHA-256 values, the release and virtualenv were
switched to `b7d51b0`, and AgentPost, Nginx, PostgreSQL, local health, and local
readiness passed. A logged-in production browser verified the guide, tool/OS
switching, Windows preview notice, and manual Pairing fallback without submitting
a Pairing or exposing credentials.

This earlier release established UI and deployment acceptance, not a real ordinary-user Connector
installation. At that stage Codex used the generic Connector and native natural-language invocation
was still pending; the post-handoff M24 section above records the later Codex MCP integration.
WorkBuddy and OpenClaw still use the generic Connector path, and Windows remains explicitly marked
as awaiting physical-device validation.

The first real Codex Pairing attempt exposed a Human-facing 422 caused by the UI
accepting values that the `local_agent_id` protocol schema rejects while hiding
the safe validation details. Release `dda639e` was deployed with a fixed managed-
domain suffix, same-domain full-address normalization, pre-confirmation input
checks, Chinese/ASCII capability separators, and field-specific Chinese schema
errors. The regression also proves that a schema-rejected decision does not
consume its one-time Human confirmation. A fresh end-user command subsequently
completed real Codex Pairing: the Connector claimed its credential into the macOS
credential vault and reported active/healthy heartbeat state without displaying
the long-lived key. At the time of that Pairing, AgentPost was not registered in
Codex's MCP configuration; commit `abd1d74` and the post-handoff evidence above
supersede that specific local-integration gap.

## Decisions already fixed

1. The server stores messages; agents need not be simultaneously online.
2. PostgreSQL, not realtime connections or a queue, is the durable source of truth.
3. Local delivery is atomic with inbox persistence. The API returns an acceptance
   receipt; a committed local message is already `delivered`, never merely held in
   volatile memory.
4. `read` and `ack` are explicit commands. `GET` never changes message state.
5. Authentication determines the sender. A request cannot choose an arbitrary
   `sender_agent_id`.
6. Messages and attachments are untrusted external inputs. Adapters must preserve
   that trust label and must not elevate message content into system instructions.
7. Idempotency is scoped to `(sender_agent_id, idempotency_key)` and payload
   mismatch on key reuse is a conflict.
8. OpenClaw, MCP, A2A, realtime transports, and future federation remain adapters;
   none is a core runtime dependency.
9. 星轨 Human identity is separate from Agent and Admin credentials. Human views
   are authorization-scoped, and `ACK` never means a task completed.
10. An organization is a server-side authorization scope, not a UI filter. One
    Agent can belong to one organization in the current model; direct grants and
    organization-derived visibility remain independent.
11. A Human control decision uses Human identity, session-bound CSRF, and when
    sensitive a target-bound one-time confirmation. It never impersonates an
    Agent or executes Agent business work implicitly.
12. Approval state is independent from Delivery and task state. `approved` records
    authorization with `execution_effect=none`; the requesting Agent must poll and
    continue under its own identity and policy.
13. A tool host is a replaceable Connector, not an Agent identity. One Human may
    own many independent Agents; one Agent has one current Connector. Replacing or
    revoking a Connector preserves Address, Inbox, ACL, Thread, and history.
14. Human email/password, MFA, recovery, browser sessions, Human API keys, and
    enterprise identity-provider sessions are distinct credentials. No one
    credential is silently promoted into another trust domain.
15. The first Remote MCP authorization profile is a first-party Device
    Authorization flow. Its completion does not imply generic third-party OAuth
    Authorization Code, PKCE, dynamic client registration, or host compatibility.
16. Enterprise OIDC trust requires both an operator-approved Issuer and a verified
    organization email domain. Existing local accounts are never silently merged
    solely because an IdP returns the same email address.

## Milestone 23 enterprise OIDC evidence

Organization owners can configure and disable an OIDC provider only after the
organization has a verified DNS domain and only when the issuer appears in the
deployment operator's allowlist. Discovery, authorization, token, and JWKS
endpoints must remain on the approved issuer host; client secrets and PKCE
verifiers are encrypted at rest. Login uses Authorization Code + PKCE with
one-time HMAC-digested state, a nonce verified inside a signed ID token, strict
issuer/audience/expiry checks, and an exact verified-email-domain match.

A first-time enterprise identity can create a Human account and organization
`member` membership. If the email already belongs to a local account, callback
returns `oidc_account_link_required`; the existing Human must initiate a
password/MFA-protected link from an authenticated 星轨 session. SSO sessions record
`auth_method=enterprise_oidc`, and only trusted IdP `amr` values mark the local
session as MFA-authenticated. Disabling the provider blocks new login starts but
does not silently delete Human accounts or historical audit records.

Four integration tests cover signed-token auto-provisioning, organization
membership/session creation, state replay rejection, encrypted client-secret
storage, explicit existing-account linking, CSRF/password reauthentication,
verified-domain and issuer-allowlist gates, provider disable, and feature-off
surface hiding. Migration 0017 passed fresh upgrade, schema check, downgrade to
0016, re-upgrade, and a second check against SQLite. The full non-PostgreSQL
regression now reports 292 passed, one expected loopback sandbox skip, and four
deselected PostgreSQL tests; MCP and both Node harness selections also pass.

## Milestones 20–22 onboarding and open-access evidence

Human access no longer depends on an Admin minting a one-time `hum_` key. When
explicitly enabled, a Human can verify an email address, register a password,
sign in, recover the account, enable replay-protected TOTP with one-use recovery
codes, and rotate/revoke Human API keys. Production configuration requires SMTP,
HTTPS, and non-development secrets. Organizations can be created and governed by
their owners/admins; invitation acceptance, role change, member removal,
self-exit, last-owner protection, and DNS TXT domain verification are audited.

Pairing can now bind a new Connector to an existing owned Agent as well as create
a new Agent. Replacing a Connector atomically revokes the old connector-bound
credential while preserving the logical Agent, Address, Inbox, ACLs, Threads, and
history. Heartbeat and status are advisory. The Python runtime persists its
cursor, supports OS keyring storage when the optional dependency is installed,
and recovers from transient polling failures. The TypeScript runtime exposes the
same lifecycle through a host-injected `CredentialStore`; it deliberately has no
plaintext fallback.

The first-party Remote MCP profile implements OAuth server/protected-resource
metadata, Device Authorization, scoped opaque access tokens, rotating refresh
tokens with family replay revocation, Connector-bound token revocation, and a
separate stateless Streamable HTTP MCP service exposing exactly the six existing
messaging tools. It never accepts a long-lived Agent API key as a model tool
argument. This profile is locally verified, but generic Authorization Code +
PKCE/client registration and real Codex/Claude/Manus/WorkBuddy/MiniMax host
acceptance remain separate future gates.

Latest locally runnable regression for these increments: 286 fast tests passed,
with one expected loopback sandbox skip and four explicitly deselected PostgreSQL
tests. The MCP package selection passed eight tests and the TypeScript Connector
Node harness passed four. Ruff lint/format, migration 0016 upgrade/check/
downgrade/re-upgrade, and `git diff --check` passed. Docker and PostgreSQL were
not available, so Compose/Remote MCP process startup and PostgreSQL concurrency
remain environment-unverified.

## Milestone 19 Agent onboarding evidence

The first zero-configuration onboarding slice is implemented. An unconfigured
Connector can create a short-lived Pairing and poll with a high-entropy device
code. A logged-in Human previews external Connector metadata in 星轨, verifies the
one-time user code, reauthenticates with the matching Human key, and approves or
denies under CSRF, action-bound confirmation, and Human idempotency controls.

Approval atomically creates a new Agent, unique managed Address, `AgentOwnership`,
Connector instance, and single current Connector binding. The Connector claims a
deterministically derived Agent credential over its private device channel; the
database stores only its normal HMAC digest, and the browser never receives the
credential. Repeated claim after response loss returns the same key. Human
revocation removes the current binding and revokes the connector-bound key while
leaving Agent identity and durable mail untouched.

星轨 now has an “Agent 连接” section and safe step-up dialogs for Pairing and
revocation. One account can display multiple independent Agents and historical
Connectors. The Python SDK adds `AgentPost.begin_pairing()` and
`AgentPost.connect()` so a local Connector can open the verification URL, wait at
the advertised interval, and return an authenticated client without Human key
copying.

Six new service integration tests cover pending/slow-down/approved/replayed claim,
wrong code, Human isolation, address-conflict rollback, denial, expiry, disabled
surface, connector-bound credential, application restart, offline Inbox
persistence, last-seen update, and revoke/401 behavior. Two SDK tests cover the
Human-facing instruction boundary and authenticated connection. Migration 0011
passed fresh upgrade, schema check, downgrade to 0010, re-upgrade, and a second
schema check against SQLite.

Latest locally runnable regression: 263 passed, one expected loopback sandbox
skip, and four explicitly deselected PostgreSQL tests. The optional MCP suite and
OpenClaw Node harness each add four passing tests. Ruff lint, whole-repository
format check, JavaScript syntax check, and `git diff --check` pass. Real PostgreSQL
execution remains a separate required gate.

## 星轨 Human control-plane evidence

The first Human control-plane slice is implemented at `/orbit` and
`/api/v1/orbit`. Admin-only bootstrap APIs create a Human identity, return a
one-time `hum_` key, and grant/revoke owner, operator, viewer, or auditor access to
an Agent. PostgreSQL models enforce one owner per Agent and explicit collaborator
grants. Human keys use a separate HMAC pepper.

The browser now sends the `hum_` key only to create a random short-lived `hss_`
session, clears the key input, and continues with an HttpOnly, SameSite cookie.
Only the session HMAC digest is stored. Sessions have a configurable default
12-hour lifetime, use `Secure` in production, survive refresh, and are revoked
server-side on sign-out. Bearer Human keys remain available for programmatic
read-only clients.

Organizations, Human membership roles (`owner`, `admin`, `member`, `auditor`),
and single-organization Agent assignments are now durable server-side records.
Organization owners/admins project to read-only operator visibility, members to
viewer visibility, and auditors remain body-redacted. Direct ownership/grants are
merged without being overwritten, so membership removal revokes only derived
access. 星轨 renders these relationships in the new “组织星图” section.

The Human write-security foundation is now durable. Browser sessions own a
separate `csrf_` value stored only as an HMAC digest; login returns it under
`no-store`, session refresh rotates it, and stale tokens fail immediately.
Sensitive actions require a five-minute, single-use `hcf_` confirmation bound to
Human, session, intent, and target. Human security events use a dedicated audit
record with server-derived actor and request context.

The first narrow Human write is now implemented: an authenticated Agent creates
an idempotent approval request, polls or cancels only its own request, and an
authorized owner/operator can approve or reject it from 星轨. Organization
owner/admin membership projects to operator authority; viewers cannot decide and
auditors receive redacted Agent content. The decision transaction rechecks role
and state, consumes the confirmation once, persists one decision and Human audit,
and never creates a message or performs the requested action. The Python SDK
exposes Agent-side create/list/get/cancel without Human decision credentials.

Six integration tests prove branding/security headers and no browser key
persistence; Human/Agent credential separation; owner-only communication
visibility; unrelated Agent isolation; auditor body redaction; grant revocation;
session creation/digest storage/revocation/expiry; production Secure-cookie
behavior; and the critical distinction that an ACKed task remains `pending` until
an explicit `result` changes its work state. The 0007 migration passed upgrade,
schema check, downgrade to 0006, re-upgrade, and a second schema check against a
fresh database. Three organization integration tests additionally cover Admin
isolation, canonical and unique organization identities, the single-organization
Agent invariant, membership-derived visibility, auditor redaction, immediate
revocation, direct-grant preservation, and audit events. The 0008 migration also
passed upgrade, schema check, downgrade to 0007, re-upgrade, and a second check.
The 0009 migration passed fresh upgrade, schema check, downgrade to 0008,
re-upgrade, and a second schema check against SQLite. Migration 0010 adds the
durable approval request/decision records and passed upgrade, schema check,
downgrade to 0009, re-upgrade, and a second check. The Milestone 18 fast regression
reports 253 passed, one expected loopback-sandbox skip, and three explicitly
deselected PostgreSQL tests; the MCP package suite adds four passing tests. Ruff
check/format and the dependency-free browser script syntax check pass.

This is a locally verified control-plane and self-service authentication slice,
not a production-accepted public identity service. It has not been exercised
against PostgreSQL in this environment. Plaintext HTTP must not receive Human,
Connector, OAuth, or Agent credentials. Email registration, MFA, recovery, Human
key rotation, delegated organization administration, invitations, self-exit, and
DNS domain proof and an allowlisted verified-domain enterprise OIDC profile are
implemented. SCIM provisioning, arbitrary IdP lifecycle automation, cross-method
account merge, nested organization units, and production abuse controls remain
open.
Approval action execution, delegation, pause/resume, and retention workers also
remain closed.

## Final local acceptance snapshot

### Local handoff stage `v0.1.0-local.1` (2026-08-24)

The current local stage was rechecked from clean `main` before handoff. Ruff lint
and format checks passed across 206 Python files. The fast suite reported 306
passed, one expected sandbox-only loopback skip, and five deselected PostgreSQL
tests; the package-local MCP suite reported eight passed. The TypeScript Connector
and OpenClaw Node harnesses each passed four tests. The 12-step real-process demo
passed with offline send, AgentPost restart, later retrieval, explicit read/ACK,
reply, and Alice receiving the reply. Python compilation, dependency compatibility,
lock resolution, and `git diff --check` passed; wheel and sdist
`agentpost-0.1.0` artifacts built successfully.

The five marked PostgreSQL tests were collected but not executed locally because
this Mac has no Docker or PostgreSQL runtime. The stage is therefore a local
code/documentation recovery point, not a new cloud release or production
acceptance claim. The authoritative takeover summary is `PROJECT_HANDOFF.md`.

The Human approval increment completed on 2026-08-17 with seven dedicated queue
tests, including concurrent Agent idempotency, role/redaction/non-enumeration,
CSRF and reauthentication, confirmation target/intent binding, cancellation,
expiry, schema limits, zero implicit messages/actions, and organization-derived
operator authority. The Python SDK approval contract adds create/list/get/cancel
and uncertain-transport idempotency coverage. PostgreSQL execution and public
HTTPS/browser acceptance remain separate gates.

The final repository checks completed on 2026-08-12 with these results:

- `make lint`: Ruff lint and format checks passed across 119 Python files.
- default full suite: 224 passed and four environment skips. Three skips are the
  guarded PostgreSQL acceptance cases; the fourth is the loopback E2E inside the
  restricted sandbox.
- the loopback E2E was then run with local-port permission and passed; `make demo`
  also completed all 12 real-Uvicorn restart steps.
- the MCP adapter's package-local suite passed four tests; the combined MCP,
  OpenClaw, and observability contract selection passed 22 tests.
- the zero-dependency OpenClaw Node client harness passed all four tests.
- Alembic completed upgrade-to-head, schema check, downgrade-to-base,
  re-upgrade-to-head, and a second schema check against a fresh file database.
- a fresh offline sdist and wheel build passed. The wheel contains the server,
  Admin assets, Python SDK, and MCP adapter; direct wheel import smoke checks
  passed.
- README Bash blocks passed `bash -n`, both Python blocks compiled, the envelope
  JSON parsed, the lockfile resolved, and `git diff --check` passed.

This is **local verified**, not production accepted. Docker/PostgreSQL commands
and a supported OpenClaw host remain unavailable on this machine.

## Definition of Done audit

`[x]` means implemented and exercised locally; `[~]` means the implementation and
acceptance asset exist but the required external runtime was unavailable.

- [x] Alice and Bob have unique Agent identities and canonical addresses.
- [x] API-key authentication binds the sender and rejects forged identities.
- [x] Alice can send while Bob has no running client; Bob later retrieves unread
  mail, marks it read, ACKs it, and replies.
- [x] Alice sees Bob's ACK projection, and both participants can retrieve complete
  thread history.
- [x] Attachments, capability Directory, inbound ACLs, and sender-scoped
  idempotency work through the API and automated tests.
- [x] The Python SDK supports send, Inbox, get/read/ACK/reply, Directory, and
  attachment operations.
- [x] The OpenClaw adapter implements basic send/inbox/read/reply/ACK/search over
  the public protocol; static and Node harness tests pass.
- [x] The optional MCP adapter exposes the corresponding six stdio tools.
- [x] Human email registration/login, TOTP MFA, recovery, key rotation,
  organization invitations/governance, and domain verification are locally
  exercised behind explicit feature flags.
- [x] Pairing can create or reuse an owned Agent, replace/revoke its Connector,
  rotate credentials, report heartbeat, and run through Python or TypeScript
  Connector SDKs without a plaintext credential-store fallback.
- [x] The first-party OAuth Device Authorization profile and scoped Remote MCP
  resource are implemented and locally tested.
- [x] Verified-domain enterprise OIDC Authorization Code + PKCE login and explicit
  existing-account linking are locally exercised.
- [~] SCIM and generic MCP Authorization Code + PKCE/client discovery are not
  implemented and must not be advertised.
- [x] `README.md`, `ARCHITECTURE.md`, `PROTOCOL.md`, `SECURITY.md`, Roadmap, ADRs,
  JSON Schema, deterministic examples, and `make demo` are present and verified.
- [~] PostgreSQL durability, restart, idempotency, row-lock, and 100-Agent tests
  are implemented in `tests/postgres` but not executed here because neither
  Docker nor PostgreSQL is installed.
- [~] Docker Compose one-command API/PostgreSQL startup and persistent volumes are
  implemented but not executed on this host.
- [~] All locally runnable automated tests pass; the four PostgreSQL cases must
  pass with zero skips before a production-database acceptance claim.

## Milestone evidence trail

`*` Milestone 1 fast-test evidence: 7 tests passed, Ruff passed, and the Alembic
baseline ran through the SQLite adapter. Docker Compose and PostgreSQL execution
remain not locally verified because this host has neither command installed.

Milestone 3 evidence: 60 fast tests passed, including application recreation on a
file-backed database, sender forgery rejection, sender-scoped idempotency,
participant isolation, cursor integrity, equal-timestamp pagination, and explicit
`external_agent_content` labelling. Real PostgreSQL restart remains a later marked
acceptance target.

Milestone 6 evidence: 133 fast tests passed. The 15 attachment-specific security
tests cover actual-byte limits, SHA256, unsafe filenames, temporary-file cleanup,
single-use sender-owned binding, participant-only download, atomic rollback,
task/result attachments, and persistence across complete application recreation.
Alembic upgrade/check/downgrade/upgrade passed against SQLite; PostgreSQL execution
remains explicitly unverified on this host.

Milestone 8 evidence: 151 fast tests passed, including 18 independent ACL tests.
The suite covers public/allowlist/contacts-only/private policies, canonical Agent
and domain rules, block precedence, send/reply re-authorization, historical mail
visibility, idempotent replay after a policy change, denial rollback, and audit
records. SQLite migration round-trips pass; PostgreSQL row-lock concurrency remains
explicitly unverified on this host.

Milestone 9 evidence: 29 SDK contract tests passed using HTTP mock transports.
The single distribution exposes `from agentpost import AgentPost`, while the SDK
implementation depends only on public HTTP/JSON protocol types. Offline sdist and
wheel builds, isolated wheel installation, deterministic example compilation, and
all example `--help` smoke checks passed.

Milestone 10 evidence: the real-process `make demo` completed all 12 Alice/Bob
steps, including terminating Uvicorn and restarting it against the same durable
database. Fast acceptance covers two application restarts with task/result
attachments, 100 concurrent Agents without lost delivery, 32-way idempotency,
concurrent read/ACK, authorization isolation, forged state, malformed JSON, and
log-secret canaries. The PostgreSQL suite and isolated Compose manifest exist and
collect safely, but their four tests are **not locally executed** because this
host has no Docker or PostgreSQL command. That remaining boundary is why the
milestone carries an asterisk rather than a production acceptance claim.

Milestone 11 evidence: the TypeScript ESM native tool plugin exposes exactly six
strict TypeBox tools and imports only the OpenClaw tool-plugin SDK plus the public
AgentPost HTTP protocol. Seven independent contract/security checks and four
zero-dependency Node client tests pass; the full fast suite reports 200 passed and
four environment skips. The adapter fixes the server URL and credential in admin
configuration, propagates cancellation and idempotency keys, performs no hidden
retry, preserves `external_agent_content`, and sanitizes errors. A real
`openclaw plugins build/validate` remains **not locally executed** because npm,
OpenClaw, and TypeBox are unavailable and the bundled Node 24.14.0 is outside the
plugin's declared supported ranges; this is why the milestone carries an asterisk
rather than a host-compatibility acceptance claim.

Milestone 12 evidence: the optional `agentpost_mcp` package is locked to the
official Python MCP SDK 2.0.0 and exposes exactly six stdio tools over the public
Python SDK. Thirteen adapter tests pass, including a real in-process MCP Client;
a real stdio subprocess lists all six tools without protocol noise. The wheel and
sdist include the adapter and `agentpost-mcp` entry point. Calls use an independent
SDK client, preserve opaque cursors and explicit idempotency keys, perform no
hidden retry, and return sanitized structured errors. Inbox, message, and
directory results are labeled `external_agent_content`; server-internal forward-
compatible fields are filtered without interpreting or rewriting opaque business
content. The full fast suite reports 210 passed and four expected environment
skips.

Milestone 13 evidence: `docs/A2A_MAPPING.md` defines a normative A2A 1.0
compatibility boundary and a machine-readable contract registry; six contract
tests pass. The mapping keeps mailbox Delivery and A2A Task state permanently
separate (`ACK` has no Task effect), requires restart-safe principal-scoped task
bindings, preserves Inbox durability, treats Cards/Parts/Artifacts as untrusted,
and forbids advertising streaming, push, cancellation, or verified skills before
implementation. `integrations/a2a/` is intentionally only a reserved adapter
surface: no A2A runtime endpoint or conformance claim is shipped, which is why
the milestone carries an asterisk.

Admin/debug evidence: an optional `/admin` console and five read-only operational
endpoints are hidden unless a 32–512 character Admin token is configured. Four
integration tests cover disabled/wrong-token generic 404 behavior, safe Agent,
Message, Thread, Delivery, and Audit projections, absence of body/key/storage
secrets, and security headers. The console creates test Agents through the
existing registration boundary, reads an Agent Inbox, and sends idempotent test
messages; credentials stay in password inputs/page memory and external data is
rendered only as text. A real wheel build includes all HTML/CSS/JS assets.

### Connector CLI evidence (2026-08-24)

The first Human-testable Connector command is packaged as `agentpost-connect`.
It can initiate browser Pairing or restore an existing identity from the operating-
system credential vault, and exposes explicit connect/status/send/inbox/read/ACK/
reply/rotate/worker operations without printing a long-lived `agt_` credential.
The Inbox command is metadata-only; read and ACK remain explicit. The deterministic
Worker treats bodies as untrusted data, advances its durable cursor only after its
handler succeeds, and uses the runtime's transient-failure backoff.

Four CLI tests and the existing seven onboarding/runtime tests pass. The full local
fast selection reports 305 passed, one expected loopback sandbox skip, and five
deselected PostgreSQL tests. The separate MCP selection reports eight passed and
the TypeScript Connector harness reports four passed. Ruff lint/format and wheel
entry-point inspection pass; the wheel contains both the CLI module and its console
script metadata. Real OS-keychain/browser pairing remains a production experience
gate until Human email authentication and Pairing are safely enabled.

## Alibaba Cloud deployment evidence

On 2026-08-13, the committed service was installed on a dedicated Alibaba Cloud
Light Application Server in Hangzhou. A provider snapshot named
`agentpost-baseline-20260813` was completed before mutation. The active origin
uses Ubuntu 24.04, PostgreSQL 16, a Python 3.12 virtual environment, systemd,
Nginx, a private filesystem attachment directory, and server-only generated
production secrets. AgentPost, Nginx, and PostgreSQL all reported `active` after
deployment, and `/health` and `/ready` passed both on the origin and through the
server's public HTTP endpoint.

The first PostgreSQL send exposed an ORM flush-order defect that SQLite's default
foreign-key behavior had hidden. The transaction rolled back cleanly. Commit
`01c97a1` stages the durable message and delivery before the sender-scoped
idempotency record, retains a single database transaction, and adds a regression
test with immediate foreign-key enforcement. The resulting local suite passed
227 tests with one environment-only loopback skip and three PostgreSQL cases
deselected.

The initial cloud acceptance passed against real PostgreSQL: Alice sent while no Bob
client was running; the delivery was persisted; the AgentPost service restarted;
Bob found the unread message, marked it read, ACKed it, and replied; Alice found
the reply; and the thread contained exactly two messages. At that stage this
established `deployed_origin_verified`; the later HTTPS stage supersedes that
label. Operational paths, verification, and rollback are recorded in
`docs/ALIYUN_DEPLOYMENT.md`.

### Current-stage Alibaba Cloud update (2026-08-19)

The current Human/Connector/OAuth/OIDC code is now deployed to the same Hangzhou
origin as release `9f39342`. A fresh PostgreSQL dump, attachment archive, and
provider snapshot `agentpost-pre-8f3bfd0-20260819` were completed before the
cutover. The live database reached Alembic revision `0017_enterprise_oidc`, and
AgentPost, Nginx, and PostgreSQL all remained `active` after the final restart.

The first cutover safely exposed a PostgreSQL-only migration defect: Alembic's
32-character revision column could not store
`0013_organization_self_governance`. PostgreSQL transactional DDL retained
revision `0005_access_control`, the old release was restored, and health checks
passed before the migration was changed. Commit `9f39342` widens that column to
128 and adds a PostgreSQL acceptance assertion. The retry preserved the original
four Agents, two Messages, and two Deliveries exactly.

A real cloud E2E then passed across an AgentPost restart: Alice sent while Bob
had no client; Bob later retrieved, read, and ACKed the durable Inbox message;
Bob replied; Alice found the reply and ACK receipt; and the thread contained two
messages. Public-IP `/health`, `/ready`, and `/orbit` returned HTTP 200. The
application and PostgreSQL continue to listen only on loopback behind Nginx.

At the end of this 2026-08-19 stage the origin was still plaintext HTTP, so Human
self-service/open registration, pairing, Remote MCP OAuth, and enterprise OIDC
remained explicitly disabled.

### HTTPS deployment update (2026-08-24)

After the user-controlled ICP filing was approved, a single root A record was
added for `agentpost.me` to `112.124.33.54` and independently resolved through
the server resolver and Alibaba Public DNS. Before HTTPS mutation, a PostgreSQL
dump, attachment archive, protected environment backup, Nginx backup, and provider
snapshot `agentpost-pre-https-20260824` were completed.

Certbot 2.9.0 issued and deployed a Let's Encrypt certificate whose SAN is exactly
`agentpost.me`, valid through 2026-11-22 01:18:42 UTC. HTTP now redirects to
HTTPS, the renewal dry run passed, and the public application base is
`https://agentpost.me`. AgentPost, Nginx, and PostgreSQL remained active; public
HTTPS `/health`, `/ready`, and `/orbit` passed, and Chrome rendered the 星云驿/
星轨 shell without entering credentials.

A fresh cloud E2E through the HTTPS hostname also passed: Alice sent while Bob
had no client, AgentPost restarted, Bob retrieved the persisted unread message,
marked it read, ACKed it, and replied; Alice observed the ACK and reply; the
thread contained exactly two messages. The current evidence label is
`deployed_https_verified`, not `production_accepted`.

HTTPS removed the plaintext-origin blocker but did not automatically accept the
identity and abuse-control dependencies. Human self-service/open registration,
pairing, Remote MCP OAuth, and enterprise OIDC remain explicitly disabled.

### Controlled-experience release update (2026-08-24)

Commits `fa37448`, `51e3336`, and `67593b8` are deployed as release `67593b8`.
The production database reached `0018_rate_limit_buckets`; encrypted SMTP modes,
durable Human/Pairing rate limits, and the zero-credential Connector CLI are in
the running code while their feature gates remain controlled. The root-only
pre-cutover backup is `/opt/agentpost/backups/20260824-0300-67593b8/`.

All five real-PostgreSQL acceptance tests passed in an isolated database. After
cutover, all three services and HTTPS health/readiness passed, and a fresh offline
send survived an AgentPost restart before explicit read, ACK, reply, and two-message
Thread verification. The pinned Connector wheel is publicly downloadable over
HTTPS and a clean virtual environment installed its `connector` extra, imported
the OS-keyring dependency, and executed its console entry point. Chrome rendered
the production 星轨 shell after the release.

Alibaba Cloud DirectMail is active with a verified sender, SMTP/TLS configuration
is installed, and a server-side SMTP authentication check passed without
exposing the credential. Human self-service and Pairing are enabled. Verified-
email open registration was enabled on 2026-08-24 after a protected environment
backup; the public authentication configuration, health/readiness endpoints,
and 星轨 registration UI passed after restart. Remote MCP OAuth and enterprise
OIDC remain off. A real recipient-mailbox round trip and two-Human experience
have not yet been accepted.

## Immediate next action

Prepare a new immutable release candidate (expected next package version `0.1.3`) and run the real
PostgreSQL migration/acceptance suite for `0019_agent_handles`. Before any Alibaba Cloud mutation,
perform the documented read-only preflight and database/attachment/configuration backups, then seek
explicit deployment authorization. After a controlled cutover, verify public API/SDK/CLI/MCP/Skill
and authenticated 星轨 behavior, including the seven-tool MCP list.

Only after deployment should a separate Human/Agent fixture exercise the production cases: “给张子
良的 Codex 发一段星云驿开发进度”, “给 kcode 发消息”, same-name Humans, multiple Codex Agents,
not-found handle behavior, old full-address compatibility, and post-rename history/ACL/Connector
continuity. Keep write-tool approval, `external_agent_content`, idempotency, and sanitized failures.
WorkBuddy/OpenClaw execution, Windows/Linux, Remote MCP, and enterprise OIDC remain separate gates.
Do not label local tests or deployment health as `production_accepted`.
