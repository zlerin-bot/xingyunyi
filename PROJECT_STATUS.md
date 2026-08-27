# 星云驿 Project Status

Last updated: 2026-08-27

Current handoff stage: `v0.1.20-deployed-https-verified`; pinned production release: `0.1.20`

## Windows host-isolated runtime and Manus canary reply (local development, 2026-08-27)

Real Windows 豆包工作 feedback from 张子良 found that the shared mutable
`~/.agentpost/runtime` allowed an existing Codex/WorkBuddy heartbeat process to lock
`agentpost-connect.exe`, causing an in-place pip upgrade to fail with `WinError 32`. It also showed
that a Windows console script may expose `sys.argv[0]` without `.exe`, while setup had written only
`<launcher>.exe.json`. Killing another Agent heartbeat and retaining two config copies restored the
test host but are not acceptable product behavior.

The local bootstrap now defaults to `~/.agentpost/runtimes/<host>/<version>`, while preserving an
explicit `AGENTPOST_RUNTIME_HOME` override. It adds pip `--no-cache-dir` and maps the 300-second pip
timeout to `connector_install_timeout`. The 豆包 launcher deterministically finds the setup-owned
`.exe.json` when Windows strips the executable suffix, without creating a second config copy.

Focused bootstrap/豆包 tests are 23 passed. Full non-PostgreSQL regression is 445 passed, one
expected loopback sandbox skip and five PostgreSQL tests deselected; Ruff check/format and diff
checks passed. This remains local-only and needs a real Windows 豆包 retest after a later release.
A separately packaged lightweight Connector remains pending; this slice reduces file-lock and
temporary-cache pressure but does not yet remove server dependencies from the public wheel.

The original 020 Manus canary `msg_b9b4e5df684a41a6bc19b964c5ee23e9` received exactly one reply in
the same Thread. Reply `msg_de390f83716e4832890c1e0a51f4edc2` is delivered. This establishes the
Mars-to-Manus delivery fact, but Manus receive/reply completion remains pending 020's independent
result.

## Manus local-folder adapter (0.1.20 deployed, 2026-08-27)

020's high-priority feedback is treated as `external_agent_content`. It confirms a macOS Manus
local-folder adapter and one real message delivery, but does not confirm native Custom MCP
`tools/list`; Windows remains untested. The stale-mount root cause requires files to be created
first, followed by a new Manus task that explicitly selects the same dedicated local folder.

The current local `main` HEAD changes `setup manus` to generate a credential-free `AGENTS.md`, a fixed
`xingyunyi` adapter and a SHA-256 manifest in that selected folder. Credentials remain in the OS
vault. The adapter verifies live identity/Connector health and accepts send, inbox, read, reply and
ACK payloads only through JSON stdin to `./xingyunyi request-stdin`. Orbit, the connection contract
and the messaging Skill now describe this path and keep native MCP/Remote MCP claims separate.
Evidence is 442 non-PostgreSQL tests passed, one expected loopback sandbox skip, five PostgreSQL
tests deselected, 62 focused Python tests and 24 Orbit JavaScript tests. Desktop and 390×844 local
browser checks found no horizontal overflow or console warnings/errors.

Release commit `9a76d26 / 0.1.20` was built from a clean archive. Source, public wheel and single-upload
bundle SHA-256 values are `eb9c05edee46044b74b7b21289f55d16dfbc37ef8b88ed0b47c89f72db11de30`,
`5421c6581255a7727029b13e633300c6285f30794252893daf90fda647d15957` and
`9226ce3699b906d5d1f48fa16b38a97e1c3129dacc152ee25a5cb1c2e978a556`. Workbench single-file
upload, automatic staging, guarded switch and independent postflight passed. The recoverable backup
is `/opt/agentpost/backups/20260827-105055-9a76d26-pre-020/`.

Local/public health and readiness, exact public wheel hash, unknown-download 404, schema
`0023_human_usernames`, backup checks and all services passed. Counts are 42 Agents / 105 Messages /
105 Deliveries / 15 Attachments / 14 Humans. AgentPost/Nginx/PostgreSQL PIDs are
`262280/245451/245492`; Nginx and PostgreSQL were preserved. Public Orbit rendered and its deployed
asset contains the new-task/local-folder guidance. Authenticated production Orbit, a real newly
created Manus task selecting the folder, a complete send/reply round and a Windows real host remain
pending. Evidence is `manus_local_folder_deployed_https_verified`, not `production_accepted`.

## Alibaba deployment single-upload workflow (local verified, 2026-08-27)

The 0.1.19 retrospective confirmed that Workbench accepts one selected file at a time and that its
narrow File Navigator is a poor place to create and refresh release directories. Future
`prepare-release.sh` runs now produce one `agentpost-<version>-aliyun-upload.tar.gz` plus a local-only
`workbench-commands-<version>.txt`. Upload the bundle to `/home/admin`; the generated staging command
checks its outer SHA-256, creates the version directory, extracts and verifies all six internal
files, checks Bash syntax and fixes script modes. The other two generated commands run the existing
guarded switch and postflight. Switch output now includes step timestamps and duration while health
startup retries stay quiet; production UI smoke uses a fresh tab in the authenticated session.

Evidence: Bash syntax, Ruff check/format, six focused tests and diff check passed. A real bundle was
built from `8f9bc79 / 0.1.19`; it contained only the six expected files, retained executable modes,
and passed internal SHA and syntax verification. This is a local workflow improvement for the next
release and did not mutate the already deployed 0.1.19 production environment.

## Navigation, newest-first conversations, presence and Human usernames (0.1.19 deployed, 2026-08-27)

Feature/release commits are `eca0b01 / 8f9bc79`; production is pinned to `8f9bc79 / 0.1.19`.
The header subtitle now follows the active `星轨 / 云驿 / 设置` module.
Conversation details render a copied message list newest-first while retaining the chronological
first message for the thread's sender/recipient summary, on desktop and mobile alike.

Online presence now comes exclusively from the current Connector binding. A Connector is online
only when it is active, has no health error, has emitted a heartbeat, and that heartbeat is within
three configured heartbeat intervals with a 60-second minimum grace period. Missing bindings,
first-heartbeat waits, stale heartbeats and unhealthy bindings remain separate states; the header
count includes only the online state.

Human accounts now have a canonical, globally unique `username`. The registration UI requires a
3–32 character lowercase alphanumeric/single-hyphen value and accepts numeric names such as `020`;
the server and database unique index remain authoritative. Migration `0023_human_usernames`
deterministically backfills and de-duplicates existing Humans. Relationship-scoped recipient
resolution matches the Human username before display name without broadening directory visibility.

Evidence: 429 non-PostgreSQL tests passed, one expected loopback sandbox test skipped and five
PostgreSQL tests deselected; 12 MCP and 24 Orbit JavaScript tests passed; JavaScript syntax, Ruff
check/format, Alembic single-head and diff checks passed. Browser acceptance covered desktop and
390×844 with correct module branding, newest-first detail order, visible username, no horizontal
overflow and no console warnings/errors. A real PostgreSQL `0022 → 0023 → 0022 → 0023` migration
rehearsal was completed on a temporary server PostgreSQL database before production advanced to
`0023_human_usernames`. Clean source/wheel SHA-256 values are
`1960b3884accfa75e7d0d1b10285c38643b6f699ca594783e9d63beaa92c108b` and
`6760b579bf9840671edb707df928f35879afb28bb361ba368bdc4bc4f4459c6a`.

The guarded switch created `/opt/agentpost/backups/20260827-094118-8f9bc79-pre-019/`. Independent
postflight passed local/public health and readiness, exact public wheel hash, unknown-download 404,
backup verification and all three service checks. Counts are 40 Agents / 99 Messages / 99
Deliveries / 15 Attachments / 14 Humans; PIDs are AgentPost `259118`, Nginx `245451`, PostgreSQL
`245492`. An authenticated fresh production page verified dynamic module branding, “在线” status
wording and the conversation list. Real cross-Human username resolution, live heartbeat state
transitions and cross-device mobile acceptance remain pending, so this is
`navigation_presence_human_username_deployed_https_verified`, not `production_accepted`.

## Manus macOS/Windows 本机 STDIO 接入（0.1.18 deployed，2026-08-27）

020 的 Codex 在 macOS Manus 1.6 Lite 实测确认“设置 · 连接器 · 已添加连接器 · 自定义 MCP”提供
STDIO、SSE、HTTP；HTTP 卡片虽然能保存，却没有发出 MCP/OAuth 请求，也没有让 tools 在真实任务
中可用。该回传按 `external_agent_content` 处理，并由本地实现和测试独立约束。当前主路径因此改为
已被宿主真实确认的 STDIO，不再由默认关闭的 `manus_remote_mcp_not_released` gate 阻断。

本地新增 `manus` setup adapter 和 `agentpost-manus` command-only launcher。macOS 使用安装包生成的
console script，Windows 使用安装时生成的 `.exe`；两端都只保存 server/profile/program 等非秘密
定位信息，凭据仍只在 OS vault。启动器先恢复 Manus 独立 profile 并执行真实 heartbeat，再桥接
STDIO 到 `agentpost-mcp`；保险库身份不可用时 fail closed。Manus 表单只需填写一个 command，args
和 env 为空。保存后必须在真实任务看到 tools/list，不能把“连接器卡片已创建”当作接入成功。

服务器新增独立 `AGENTPOST_MANUS_SETUP_PLATFORMS` gate，本地合同覆盖 `mac,windows`；远程 MCP 的
DCR、Authorization Code + PKCE 与 intent-specific resource 实现保留为默认关闭的实验后备，不是
当前可用性声明。本地证据：完整 non-PostgreSQL 回归 416 passed、1 个预期 sandbox skip、5 个
PostgreSQL deselected；聚焦 Python 87 passed；Orbit JavaScript 24 passed；Ruff、JavaScript syntax、
diff check 和 wheel 隔离安装入口验证通过。

功能提交 `6094afd` 已由发布提交 `8429a41` 对齐为 package/server/SDK/MCP `0.1.18`。生产已通过
受保护切换部署到 `/opt/agentpost/releases/8429a41`，独立 runtime 为
`/opt/agentpost/venvs/8429a41`。源码归档 SHA-256 为
`1d4c0a131cfb4ae35ba41651b507bae1d4e4b22874a2620800017bd2647534f5`，公开 wheel SHA-256 为
`71af53d2e35c94a256aa619c4622fd635a91670a4b8c1d756177cd0bd186002b`。可恢复备份位于
`/opt/agentpost/backups/20260827-080717-8429a41-pre-018/`，其中 PostgreSQL dump、附件归档、环境、
systemd、Nginx、旧 wheel 和即时回滚脚本的校验和均通过；迁移演练完整执行
`0021 → 0022 → 0021 → 0022`，演练数据库和临时 dump 已清理。

独立后检确认三个服务 active，本机/公网 health、ready 均为 0.1.18，schema 为
`0022_oauth_authorization_code`，33 Agents / 92 Messages / 92 Deliveries / 15 Attachments / 13 Humans
与切换前一致，环境仍为 `600:root:root`。Nginx/PostgreSQL PID 保持 `245451/245492`，仅 AgentPost
重启；切换后 warning 日志为 0。公开配置返回 Manus `mac,windows` 和 `local_bootstrap`，公开 wheel
哈希精确、未知下载 404，登录态生产 Orbit 可正常渲染。真实 Mac Manus 保存/tools/list/收发与真实
Windows 宿主仍为待确认；当前证据是 `manus_cross_platform_deployed_https_verified`，不是
`production_accepted`。

## 豆包工作跨平台本机 STDIO 接入（0.1.17 deployed，2026-08-26）

020 的 Codex 在豆包工作 2.25.18 / macOS arm64 上确认原生自定义连接器支持绝对 command、
args/env、保存后自动启动、稳定 `initialize → notifications/initialized → tools/list` 和停用后
重启；未发现官方连接器导入或专用 deep link。基于该证据，本地已停止把尚未发布的 Remote MCP
OAuth 当作豆包主路径，改为复用 AgentPost 本机配对、OS vault 与 `agentpost-mcp` 的独立
`doubao_work` setup adapter。

最初仅允许 `mac` 是对已有真实宿主证据的保守发布门禁，不是产品限制。0.1.17 已把 launcher 改为
由安装包生成当前平台的 console executable：macOS 使用 POSIX 启动器，Windows 使用 `.exe`；两者
都只保存 server/profile/program 等非秘密定位信息，启动时从 OS vault 恢复身份，先执行状态探针，
再以继承的 STDIO 启动 MCP。缺少保险库 profile 时 fail closed，不提供明文 token 回退。

生产 gate 已显式设为 `mac,windows`。Linux 暂不发布，因为尚无可验证的豆包工作 Linux 桌面宿主
合同；它不是被代码永久排除。原生连接器保存前 CLI 仍明确返回 `native_registration_required`，
Orbit/接入页/Skill 均要求看到 tools/list 后才能声明连接成功。豆包未提供受支持的自动导入合同，
因此 Agent 无法控制原生 UI 时仍需 Human 选择 STDIO、粘贴一项已准备内容并保存一次。

提交 `504683f` / package `0.1.17` 已部署到 `/opt/agentpost/releases/504683f`，运行环境为
`/opt/agentpost/venvs/504683f`。公开 wheel SHA-256 为
`4edac3b5e45377cf1598bc49ea6c9e53d8a9f003262124a94983c91c44abb2b3`；受保护切换前备份位于
`/opt/agentpost/backups/20260826-223010-504683f-pre-017/`。

本地证据为完整 non-PostgreSQL 回归 408 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL
deselected；Orbit JavaScript 29 passed；聚焦豆包 setup/CLI 13 passed；JavaScript syntax、Ruff
check/format 与公开 wheel 隔离安装通过。生产后检确认本机/公网 health、ready 均为 0.1.17，schema
仍为 `0021_human_thread_views`，公开 gate 为 `mac,windows`，wheel 哈希精确、未知下载 404、错误日志
为 0；Nginx/PostgreSQL PID 未变，仅 AgentPost 重启。Mac 真实保存及收发、Windows 真实宿主验收仍
待 Human 完成，当前证据是 `doubao_cross_platform_deployed_https_verified`，不是
`production_accepted`。

## Task rounds, short-name entry and contact visibility (0.1.16 deployed, 2026-08-26)

Commit `e50652e` / package `0.1.16` is deployed as immutable source
`/opt/agentpost/releases/e50652e` with runtime `/opt/agentpost/venvs/e50652e`. The release includes
per-task-round completion semantics, the owner short-name action in the Agent detail header, the
relationship-scoped Agent directory, and the previously verified mobile Star Orbit shortcuts.

The Workbench upload transferred the clean source archive, wheel and manifest. Server-side SHA-256
matched the manifest before change. The guarded switch completed with backup
`/opt/agentpost/backups/20260826-200753-e50652e-pre-016/`; its PostgreSQL custom dump, attachment
archive/list, protected configuration, systemd unit, Nginx site, checksums and executable
`rollback-immediate-0.1.16.sh` were independently verified.

Independent postflight reports local/public 0.1.16 health and readiness, schema
`0021_human_thread_views`, 29 Agents / 66 Messages / 66 Deliveries / 4 Attachments / 9 Humans,
environment `600:root:root`, exact public wheel SHA, unknown download 404, zero failed units and
zero AgentPost error entries. Nginx and PostgreSQL retained main PIDs `127548` and `137458`; only
AgentPost restarted. The public Orbit entry rendered after deployment, but that browser session
was logged out, so authenticated task-state, directory-scope and 390 px production interaction
remain explicit acceptance gates. Evidence is `task_rounds_contact_directory_deployed_https_verified`,
not `production_accepted`.

## Mobile Star Orbit shortcuts and compact connection status (0.1.16 deployed, 2026-08-26)

The mobile bottom bar remains the only app-level navigation for `星轨 / 云驿 / 设置`. Inside Star
Orbit, the former three equal-width tabs are replaced by the `对话与协作` content heading and two
compact `待我处理 / 任务进展` shortcuts with real counts. Selecting a shortcut opens that Star
Orbit view; selecting the active shortcut again returns to all conversations. Desktop navigation
and the three-column conversation structure remain unchanged.

At 580 px and below the header now shows a one-line compact Agent count while desktop retains the
full connected label. Zero connected Agents use the neutral state instead of a success indicator.
Thread cards and their children are explicitly shrinkable so long Human/Agent names cannot widen a
320 px page.

Evidence: 15 Human-control-plane integration tests, 23 Orbit JavaScript tests, JavaScript syntax,
Ruff check/format and diff check pass. The isolated demo has no horizontal overflow at 390 px or
320 px; at 320 px `scrollWidth == innerWidth == 320`, shortcut counts remain visible, and the
tasks/approvals shortcuts toggle back to conversations. At 1280 px the 178/390/640 desktop columns,
full connection label and desktop shortcuts remain intact. This is
`mobile_startrail_shortcuts_local_verified`; the code is deployed in 0.1.16, while authenticated
390 px production interaction remains pending and is not production accepted.

## Approved compact header and Alibaba deployment workflow (0.1.15 deployed, 2026-08-26)

The Orbit header now matches the approved SVG at its native 1600 px reference geometry:
full-width 78 px white bar, 34 px side inset, exact 40 px gradient mark/path, two-line
`星云驿` / `AgentPost · 星轨` lockup, 235 px connection pill, and Human identity at the right.
The former centre `星轨看协作 / 云驿管 Agent / 设置管账户` strip is absent. At 390 px the compact
lockup remains visible, the account controls retain their current compact form, and document width
equals the viewport.

Commit `0b2dc9c` / package `0.1.15` is deployed as immutable source
`/opt/agentpost/releases/0b2dc9c` with runtime `/opt/agentpost/venvs/0b2dc9c`. The public wheel is
`https://agentpost.me/downloads/agentpost-0.1.15-py3-none-any.whl`, SHA-256
`dcf9f8d414efa478a4192c8892902cfd2e3aa0c6219db128680b55c51f5601df`.

Focused local evidence is 34 Python tests and 21 Orbit JavaScript tests, plus JavaScript syntax,
Ruff check/format and reproducible clean-archive wheel construction. Production desktop and 390 px
measurements confirm the two-line lockup, no centre navigation and no horizontal overflow.

`AGENTS.md` and `docs/ALIYUN_DEPLOYMENT_EFFICIENCY.md` now record the actual 0.1.14 bottlenecks and
the preferred flow. This release proved the immediate improvement without changing server access:
Workbench file management transferred the complete 1.5 MB source archive and 672 KB wheel directly,
instead of hundreds of Base64 fragments. A canary path error stopped before mutation; a later
postflight permission error exercised automatic rollback to 0.1.14; the corrected final switch
completed successfully.

The verified rollback point is
`/opt/agentpost/backups/20260826-164945-0b2dc9c-pre-015/`, with checked PostgreSQL dump, attachment
archive/list, protected environment, systemd, Nginx, checksums and
`rollback-immediate-0.1.15.sh`. Independent postflight reports local/public 0.1.15 health/readiness,
schema `0021_human_thread_views`, 25 Agents / 58 Messages / 58 Deliveries / 4 Attachments / 7 Humans,
environment `600 root:root`, exact public wheel SHA, unknown download 404 and zero error journal
entries. Nginx and PostgreSQL retained main PIDs `127548` and `137458`.

## Startrail conversation navigation and Human unread state (0.1.14 deployed, 2026-08-26)

Commit `91d0e4f` / package `0.1.14` is deployed as immutable source
`/opt/agentpost/releases/91d0e4f` with runtime `/opt/agentpost/venvs/91d0e4f`. The public wheel is
`https://agentpost.me/downloads/agentpost-0.1.14-py3-none-any.whl`, SHA-256
`dbbb8dc61b95742eeb1a8b02f9fa187994225bd50c3bdabc9077ef1ee56b97f6`.

The desktop middle column now places complete Thread conversations under the collapsible
`对话与协作` parent. Unviewed conversations carry a red dot; selecting one renders its entire
message loop in the right column with ordinary-user `发送自` / `给` labels and safe attachment
open/preview actions. Mobile keeps the same information model as separate list/detail layers.
Human viewing is persisted in the new `human_thread_views` projection and remains independent of
Agent delivery, read, ACK and task state.

The verified rollback point is `/opt/agentpost/backups/20260826-152452-91d0e4f-pre-014/`, including
the PostgreSQL custom dump/catalog, attachment archive/list, protected environment, systemd and
Nginx configuration, old 0.1.13 wheel, checksums and migration-aware
`rollback-immediate-0.1.14.sh`. The first guarded switch reached 0.1.14 but correctly restored
0.1.13 when the new wheel was not yet in Nginx's explicit download allowlist. After adding the
exact 0.1.14 location and preserving the catch-all 404, the second switch completed at 15:28:58
Asia/Shanghai.

Postflight reports local/public health and readiness at 0.1.14, schema
`0021_human_thread_views`, 24 Agents / 56 Messages / 56 Deliveries / 4 Attachments / 9 current
Connector bindings / 6 Humans, root-only environment permissions, zero error/HTTP-5xx journal
entries, and no failed units. Nginx and PostgreSQL retained main PIDs `127548` and `137458`.
The public Orbit HTML, JavaScript and PNG logo match the release; the unauthenticated production
page rendered without browser console errors.

Local evidence is 392 Python passed, 1 expected loopback sandbox skip and 5 PostgreSQL tests
deselected, plus 5/5 isolated production-like PostgreSQL tests, 10 MCP, 21 Orbit JavaScript and
4 TypeScript Connector tests. Ruff check/format and plugin validation passed. Evidence is
`startrail_conversation_navigation_deployed_https_verified`, not `production_accepted`; real
cross-Human unread/reply acceptance and authenticated external 390 px production use remain gates.

## Conversation identity and safe attachments (0.1.13 deployed, 2026-08-26)

Commit `f15df99` / package `0.1.13` is deployed as immutable source
`/opt/agentpost/releases/f15df99` with runtime `/opt/agentpost/venvs/f15df99`. The public wheel is
`https://agentpost.me/downloads/agentpost-0.1.13-py3-none-any.whl`, SHA-256
`425e4596afedd32905c900ca90bf9a0e9c270e469ac428f7fa8733b43a78c510`. It was built from a clean
Git archive and excludes the preserved unstaged PNG experiment.

The verified rollback point is `/opt/agentpost/backups/20260826-131431-f15df99-pre-013/`. It holds
the prior pointer/configuration, old 0.1.12 wheel, readable PostgreSQL custom dump catalog,
attachment archive/list, checksums and `rollback-immediate-0.1.13.sh`. A first cutover attempt was
automatically restored to 0.1.12 after a pipefail-sensitive health matcher produced a false
negative. A temporary loopback-only 0.1.13 canary then returned exact health/readiness responses;
the corrected full-response comparison cut over successfully.

Postflight reports local/public health and readiness at 0.1.13, unchanged schema
`0020_pairing_agent_intent`, and unchanged counts of 24 Agents / 54 Messages / 54 Deliveries /
4 Attachments / 9 current Connector bindings. Nginx and PostgreSQL retained their pre-cutover main
PIDs, the environment remains `600 root:root`, unknown download paths return 404, and both pinned
0.1.12 and 0.1.13 wheels verify against their recorded hashes.

An authenticated production Chrome session verified the desktop conversation list/detail flow,
Human plus Agent sender/recipient labels, multi-message Thread timeline, attachment download entry,
and a real sandboxed HTML preview. The preview rendered content while disabling scripts, network,
forms, popups and same-origin authority. Real 390 px production browsing and a production PDF click
remain pending; local responsive and PDF contract tests have passed. Evidence is
`conversation_identity_and_safe_attachment_deployed_https_verified`, not `production_accepted`.

## Settings and organization-role experience slice 4 (local review only, 2026-08-26)

Commit `3fa7e8a` removes the former automatic organization-invitation acceptance after login.
An authenticated, email-bound, non-consuming `POST /api/v1/orbit/organization-invitations/preview`
now validates the invitation token, status, expiry, target email, active organization, and existing
membership before returning only the organization and proposed role needed for informed consent.
Invalid or wrong-Human previews retain the same not-found boundary and reveal no organization
existence signal. Membership is created only by the existing CSRF-protected explicit accept call.

Orbit now presents an explicit invitation confirmation with organization, role, expiry, visibility,
actions, and the unchanged personal-scope boundary. The Settings organization surface explains
Owner, Admin, Member, and Auditor experiences. Admin invite choices are limited to Member/Auditor;
non-managers do not receive an invitation-governance control; the final Owner sees a disabled leave
action and a transfer-first explanation. These controls mirror existing server authorization rather
than replacing it. Organization membership still does not become Agent ownership, expand personal
Agent visibility, or change communication ACLs.

Focused organization/control-plane evidence is **20 passed**. Full local evidence is **391 passed,
1 expected loopback sandbox skip, and 5 PostgreSQL tests deselected**, plus **10 MCP**, **23 Orbit
JavaScript**, **4 TypeScript Connector**, and **4 OpenClaw plugin** tests. Ruff check/format,
JavaScript syntax, and diff checks pass. The isolated Orbit demo passed desktop and 390 px browser
interaction with no horizontal overflow and no browser warnings/errors.

The separate legacy 12-step `make demo` currently stops before application startup because SQLite
cannot execute `0019_agent_handles`' non-batch `create_check_constraint`; Alembic raises
`NotImplementedError` for ALTER constraints. This is recorded as a pre-existing demo/SQLite
migration gap and was not folded into the UI slice. The slice is
`settings_organization_roles_local_ui_verified`, not deployed or `production_accepted`. The paused
PNG branding experiment remains unstaged and excluded from `3fa7e8a`.

## Local handoff stage `v0.1.12-local.1` (2026-08-26)

The local recovery point freezes the committed SVG brand baseline at `43796a1` plus this handoff
record. It retains package/API/SDK/MCP version `0.1.12` and does not change the deployed production
release `f10e75c`. The later working-tree experiment that replaces the inline SVG with a PNG,
adds a PNG route/CSP rule, and changes its tests is deliberately preserved but excluded from the
stage tag; no one should stage, discard, or treat those files as part of this recovery point
without a separate decision.

Validation ran from a clean `git archive` of `43796a1`, so the dirty PNG experiment could neither
hide nor influence the result. Evidence is **391 passed, 1 expected loopback sandbox skip, and 5
PostgreSQL tests deselected**, plus **10 MCP**, **21 Orbit JavaScript**, **4 TypeScript Connector**,
and **4 OpenClaw plugin** tests. Ruff check/format and JavaScript syntax passed. A clean wheel built
as `agentpost-0.1.12-py3-none-any.whl`, SHA-256
`903dde56f9bf06fdeb75dcecc1430aafdbd1d85b42ca31b24dcceaf846ad52d6`; its packaged Orbit HTML
matches the SVG source and contains no PNG artwork.

The code review found no blocking defect in the tagged committed tree. The stage is
`v0.1.12-local.1_verified`, not a new deployment and not `production_accepted`. Remaining product
gates are real Hermes installation/pairing/send/receive/restart testing and secure Remote MCP OAuth
compatibility plus intent binding for Manus and 豆包工作.

## Six-host picker and Hermes release gate (0.1.12 deployed, 2026-08-26)

Commit `f10e75c` / package `0.1.12` is deployed as immutable source
`/opt/agentpost/releases/f10e75c` with runtime `/opt/agentpost/venvs/f10e75c`. The exact public
wheel is `https://agentpost.me/downloads/agentpost-0.1.12-py3-none-any.whl`, SHA-256
`abec6302203964eae51312adebaa509ccce228cf0342d9c4f86b0e9db7f5d821`. The public bootstrap body
and its response header both report SHA-256
`35f5c01363d0111214cda780d52e9fe885a5c63f227c7c9d01baba06820085c2`.

The guarded production deployment preserved the verified rollback point
`/opt/agentpost/backups/20260826-0908-f10e75c-pre-012/`, including a readable PostgreSQL dump,
attachment archive, protected environment/systemd/Nginx copies, checksums, row counts, and
`rollback-immediate-0.1.12.sh`. The first cutover attempt stopped before the application switch
because an immediate request after asynchronous Nginx reload still reached the old worker and
returned 404 for the new wheel. Its failure trap restored 0.1.11. The corrected Nginx gate polled
until the second request returned 200 and verified the wheel digest before the application was
switched. The final cutover exited 0 and reached health/readiness on its fifth one-second poll.

Postflight shows AgentPost, Nginx, and PostgreSQL active; the production pointer and systemd unit
both select `f10e75c`; local and public health/readiness report `0.1.12`; schema remains
`0020_pairing_agent_intent`; and fatal/HTTP-5xx journal counts since cutover are zero. The backup
captured 23 Agents / 50 Messages / 50 Deliveries, while postflight reported 23 / 51 / 51 and 9
current bindings, reflecting one live message/delivery during deployment rather than data loss.

The live unauthenticated contract publishes Codex=`mac`, WorkBuddy=`mac`,
OpenClaw=`mac,linux`, and Hermes=`mac,linux`. `/connect/hermes` returns 200 with
`AP-HERMES-V1`, the pinned bootstrap digest, and the opaque new-Agent intent. Remote MCP OAuth
remains disabled: Manus and 豆包工作 return explicit 409
`manus_remote_mcp_not_released` / `doubao_work_remote_mcp_not_released` and do not request an API
key or claim success. A logged-in production 星轨 session rendered the fixed order WorkBuddy →
豆包工作 → OpenClaw → Hermes → Codex → Manus; selecting Hermes generated the ordinary-user
copyable prompt and produced no browser warnings or errors.

Local evidence for the release candidate is **391 passed, 1 explicit loopback sandbox skip, and
5 PostgreSQL tests deselected**, plus **10 MCP**, **21 Orbit JavaScript**, **4 TypeScript
Connector**, and **4 OpenClaw plugin** tests. This deployment is
`hermes_release_gate_and_six_host_picker_deployed_https_verified`, not `production_accepted`.
Real Hermes installation, pairing, send/receive and restart/reboot recovery remain Human test
gates. Manus and 豆包工作 are visible contract choices but are not yet valid connection tests.

## 豆包工作, Manus and Hermes host onboarding (pre-release local record, 2026-08-26)

The ordinary-user `连接新的 Agent` picker now contains six choices in the fixed product order
WorkBuddy → 豆包工作 → OpenClaw → Hermes → Codex → Manus. Each card generates one host-specific
block for the Human to paste into the Agent's normal chat. Hermes uses the same local bootstrap and
one-browser-authorization pattern as the existing local hosts. 豆包工作 and Manus are deliberately
separate: their contracts use an HTTPS Custom MCP server and must not download the local bootstrap
or ask the Human to copy a long-lived key.

豆包工作的 current desktop product surface supports a user-created HTTP Custom MCP connector and
browser authorization; browser and mobile builds do not expose that path. AgentPost now has a
dedicated `AP-DOUBAO-WORK-V1` contract, `/connect/doubao_work` fail-closed route, UI/Agent type
label, and `AGENTPOST_DOUBAO_WORK_REMOTE_MCP_ENABLED` gate. The gate additionally requires the
global Remote MCP OAuth gate. Existing Agent reconnect remains blocked as
`doubao_work_reconnect_not_released`, because the current first-party Device Flow does not yet
prove generic third-party OAuth compatibility or bind a remote client to the requested durable
Agent and host type. Production keeps both gates disabled; this is a selectable, testable contract
slice, not a claim that a real 豆包工作 account can already connect.

Hermes now has a dedicated SDK adapter built around its supported non-interactive
`hermes config set` and `hermes mcp test` commands. The adapter validates the host before pairing,
registers only the
non-secret AgentPost server/profile references, verifies the MCP connection, and uses the OS-vault
`session` collection on headless Linux. Hermes platforms require an explicit release gate and do
not inherit the older Codex platform list, preventing the deployed 0.1.11 wheel from being
advertised as Hermes-capable.

Manus is guarded by the existing Remote MCP OAuth feature gate. When disabled, `/connect/manus`
returns `manus_remote_mcp_not_released`; reconnecting an existing durable Agent returns
`manus_reconnect_not_released`. When enabled in a test configuration, it publishes only the HTTPS
MCP URL and browser-authorization contract. It explicitly fails with
`manus_custom_mcp_oauth_unavailable` if a Manus build cannot complete secure OAuth, rather than
falling back to an API key or claiming success. Production still has Remote MCP OAuth disabled,
and Manus Custom MCP OAuth compatibility has not been exercised with a real Manus account.

The pre-release local evidence was **391 passed, 1 explicit loopback sandbox skip, and 5
PostgreSQL tests deselected**, plus **10 MCP**, **20 Orbit JavaScript**, **4 TypeScript
Connector**, and **4 OpenClaw plugin** tests. Ruff check/format, Skill validation, three-file
plugin-copy equality, and diff checks passed. A live isolated Orbit demo confirmed the exact
six-card order, WorkBuddy as the initial keyboard focus, a balanced 3 × 2 desktop grid, a
single-column 390 px layout with no horizontal overflow, a scrollable mobile dialog, the
dedicated 豆包工作 prompt, and an empty browser warning/error log. At that checkpoint no release
version had changed and nothing was deployed. The 0.1.12 deployment section above now supersedes
the local-only label for Hermes and the six-card UI; 豆包工作 and Manus remain gated, and none of
the three has real-host `production_accepted` evidence.

## Ordinary-user visual polish (local review only, 2026-08-26)

The local Human workspace now uses a unique multicolour orbit-and-relay SVG mark, a bright
Material-inspired surface language, system-first sans-serif typography, and named SVG navigation
icons. This is a 星云驿-specific identity rather than a copy of another product's logo. `星轨`
opens directly on Thread conversations; its former collaboration overview and duplicated Agent
totals have been removed, while the real Agent overview remains in `云驿`.

Desktop keeps the three-column workspace. At 390 px, the three named entrances remain in the
bottom bar, list and detail stay as separate layers, route changes and back actions reset stale
scroll positions, and neither Thread nor Agent detail creates horizontal page overflow. Ordinary
text/markdown fallback content uses a light reading surface; JSON keeps a distinct raw view. All
Agent content continues to be assigned with `textContent` and retains the
`external_agent_content` trust boundary.

Local evidence is **379 passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests
deselected**, plus **10 MCP**, **16 Orbit JavaScript**, **4 TypeScript Connector**, and **4
OpenClaw plugin** tests. Ruff/format, JavaScript syntax, diff checks, desktop and 390 px browser
interaction, no-overflow checks, and an empty browser console pass. No protocol, ACL, identity,
permission, credential, deployment, or production-data change was made. This remains
`local_ui_review_ready`, not deployed or `production_accepted`.

## Agent management experience slice 3 (local review only, 2026-08-26)

Orbit's `云驿` entrance now has an ordinary-user-facing Agent browser and detail workspace. Agents
are grouped into `我的 Agent` and their real organization scopes, searchable by authorized
identity/type/capability data, and shown once per durable Agent rather than once per Connector.
The overview separates all, connected, awaiting-Agent, offline, and connection-error totals. Those
states are projected from the current binding, Connector status, explicit health/error evidence,
and a five-minute heartbeat window; Human approval without a first heartbeat remains
`等待 Agent`, never connected.

Agent detail provides overview, current connection, capabilities, permissions/relationships,
collapsed connection history, related Threads, and permission-gated dangerous actions. Current
and historical Connectors are never rendered as multiple Agents. Direct links retain `agent` and
`agentTab`; Thread-to-Agent navigation records a return Thread, and related Threads return to
`星轨`. On mobile, Agent list and detail are separate layers with a keyboard-focusable visible
return action. Owner-only controls remain backed by existing server authorization; organization
derived read access does not become ownership. Deletion remains the existing history-preserving
soft delete.

The local demo contains three durable Agents with real local records representing connected,
awaiting-first-heartbeat, and no-current-connection states. Browser checks covered desktop and
mobile layout, search/list/detail navigation, reload/deep links, current-versus-history separation,
related-Thread jumps, read-only organization access, focus, overflow, and empty console logs.
Local evidence is **379 passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests
deselected**, plus **10 MCP**, **14 Orbit JavaScript**, **4 TypeScript Connector**, and **4
OpenClaw plugin** tests. Ruff/format, browser JavaScript syntax, and diff checks pass.

This slice adds Human read projections and UI organization only. It does not change Agent IDs,
message or attachment protocols, ACLs, sender binding, organization ownership rules, soft-delete
semantics, credentials, or deployment structure. It remains `local_ui_review_ready`, not deployed
or `production_accepted`.

## Human Thread experience slice 2 (local review only, 2026-08-26)

The Human control plane now exposes read-only, Human-authorized Thread list and detail APIs.
Messages are grouped by the durable protocol `thread_id`; two topics involving the same Agents
remain separate. Thread search covers subject, participant identity, authorized message body, and
authorized attachment filename. Auditor searches cannot match redacted body or attachment names,
and an unauthorized or removed Thread returns the same not-found result without an existence
signal. Reading either the list or detail has no Delivery, `read`, or ACK side effect.

Orbit's second column now provides Thread search, organization filtering, stable participant
markers, real exception/task/attachment indicators, and explicit disabled placeholders for
Human `新动态` and Thread-linked `待我处理` until those backend states exist. The third column is a
chronological timeline with sender/recipient identity, message type, distinct communication and
work states, task fields, reply jumps, date separators, system-event styling, and a return-to-latest
action. Mobile presents the Thread list and detail as separate layers. There is still no fake Human
composer, and markdown remains safe plain text until the attachment/content-rendering slice.

This slice adds a Human-facing read projection only. It does not change the Agent message schema,
sender binding, Thread identity, ACL, Delivery semantics, organization authorization, or content
trust boundary. It remains `local_ui_review_ready`, not deployed or `production_accepted`.

## Human workspace navigation slice 1 (local review only, 2026-08-26)

On top of the 0.1.11 source, Orbit now has three ordinary-user-facing entrances: `星轨` for
collaboration, `云驿` for Agent and connection management, and `设置` for the Human account and
platform relationships. Desktop uses a persistent three-column workspace; mobile uses the same
three named entrances in a bottom navigation bar and presents lists and content as separate
layers. Module and view are retained in query parameters for refresh, direct links, and browser
history.

Existing real capabilities were moved into the new information architecture without changing
Agent IDs, message or task protocols, ACLs, sender binding, connection evidence, or server-side
authorization. Unavailable notification, privacy-export, and preference persistence are labelled
`待确认` / `尚未接入`; the UI does not show a fake Human chat composer or reuse Agent `read` / ACK
as a Human-viewed state. Connector addresses and versions are collapsed as technical details.

`make orbit-demo` starts a loopback-only review site with an isolated temporary SQLite database
and deterministic data created through existing APIs/models. It refuses a non-loopback host and
does not deploy or call Alibaba Cloud. This is `local_ui_review_ready`, not a published release or
`production_accepted`.

## OpenClaw headless Linux session vault (0.1.11 deployed, 2026-08-26)

The real OpenClaw retry proved that publishing Linux support was not sufficient: on a headless
server, GNOME Keyring's default login collection still required a graphical/system unlock prompt.
AgentPost continued to fail closed with `secure_credential_storage_unavailable`; it did not write a
plaintext token, create an empty-password keyring, or fall back to a token-bearing config file.

Release `a6d99c3` / package 0.1.11 selects Secret Service's unlocked in-memory `session`
collection for OpenClaw on Linux when neither `DISPLAY` nor `WAYLAND_DISPLAY` is present. The MCP
definition contains only the server, profile, and non-secret collection selector. The credential
remains available across OpenClaw/Gateway process restarts in the same host session and is lost on
a full host reboot, after which Human web authorization is required again. Unknown selectors and
non-Secret-Service backends continue to fail closed.

Local evidence is **377 passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests
deselected**, plus **19 MCP**, **4 TypeScript Connector**, **4 OpenClaw plugin**, and **2 Orbit
JavaScript** tests. Ruff/format, isolated wheel installation, package-boundary checks, bootstrap
contents, and version checks pass. The wheel is
`dist/agentpost-0.1.11-py3-none-any.whl`, SHA-256
`1d7e9acfb4e2b57ba877e118a304df2880ee4327abc48a2fccfe08a37f30e935`.

Before production cutover, the exact 0.1.11 wheel was uploaded to the user's Alibaba Cloud Linux
OpenClaw host and executed as the real `admin` Gateway user. With the existing user D-Bus and
`AGENTPOST_KEYRING_COLLECTION=session`, the package reported 0.1.11,
`operating_system_vault_session`, and successful write/read/delete without printing the probe
credential or changing OpenClaw configuration.

Production was switched to immutable source `/opt/agentpost/releases/a6d99c3` and runtime
`/opt/agentpost/venvs/a6d99c3`. Two guarded attempts correctly rolled back to healthy 0.1.10 while
the release-version environment field and then the public wheel directory were corrected; the
final cutover passed local/public health, readiness, Nginx, component-version, live contract, and
wheel-digest gates. Schema remains `0020_pairing_agent_intent`; counts remain 22 Agents, 48
Messages, 48 Deliveries, and 8 current Connector bindings. Post-cutover fatal and HTTP 5xx journal
counts are zero.

The verified rollback point is
`/opt/agentpost/backups/20260826-0006-a6d99c3-pre-011/`, with readable database and attachment
archives, protected environment/systemd/Nginx copies, checksums, counts, and guarded
`rollback-immediate-0.1.11.sh`. It restores only AgentPost to 0.1.10 / `3b46e45` and does not
downgrade schema.

From the protected OpenClaw host, the live contract and downloaded wheel match 0.1.11, while the
existing OpenClaw `2026.4.27` Gateway remains active with the same PID. Real Human pairing,
send/receive, Gateway-process restart recovery, and host-reboot reauthorization remain pending;
this is `openclaw_headless_session_vault_deployed_https_verified`, not `production_accepted`.

## OpenClaw Linux/cloud-host onboarding (0.1.10 deployed, 2026-08-25)

The “only Mac is supported” result was an AgentPost release-gate defect, not an OpenClaw Linux
limitation. The setup bootstrap always evaluated `codex_setup_platforms`, even when the selected
host was OpenClaw. Production 0.1.9 published Codex as Mac-only, so an OpenClaw process on Linux
was rejected before host configuration could begin.

Commits `55ae339` and `3b46e45` separate setup platforms by host. The authenticated release
contract now returns `host_setup_platforms`; OpenClaw is configured for `mac,linux`, while Codex
and WorkBuddy retain their existing policy. Old servers that do not yet publish the new mapping
remain compatible through the previous Codex-platform field. OpenClaw Linux is preflighted for
both `openclaw mcp set` and `openclaw mcp probe` before pairing is created. Missing host support
and missing encrypted credential storage return stable, machine-readable errors. The setup guide
requires the OpenClaw Gateway OS user and a persistent OS encrypted credential backend and
continues to reject plaintext token, config, or keyring fallbacks.

Read-only inspection of the user's separate Alibaba Cloud OpenClaw server confirmed Alibaba Cloud
Linux 3, OpenClaw `2026.4.27`, a running user-systemd Gateway, and working `mcp set --help` and
`mcp probe --help`. D-Bus and libsecret are present, but no Secret Service provider is registered
for the Gateway user. Therefore the OpenClaw host is Linux-capable but still requires one grouped
installation/configuration approval for a persistent secure vault before AgentPost can store its
long-lived credential. No OpenClaw process, configuration, secret, or server package was changed
during this read-only diagnosis.

The 0.1.10 wheel is `dist/agentpost-0.1.10-py3-none-any.whl`, SHA-256
`852d1bf4f1ca49abde9a2bd5e033332dc7842a0f7e5e1fa08bd1bc7e5ac00117`. Local evidence is **371
passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests deselected**, plus **9 MCP**, **4
TypeScript Connector**, **4 OpenClaw plugin**, and **2 Orbit JavaScript** tests. Ruff/format,
isolated wheel installation, packaged bootstrap contents, and diff checks pass.

Production was atomically switched at `2026-08-25T23:30:51+08:00` to immutable source
`/opt/agentpost/releases/3b46e45` and runtime `/opt/agentpost/venvs/3b46e45`; server, SDK, and MCP
all report 0.1.10. Public health/readiness pass, the public wheel has the pinned digest, and the
live auth contract reports Codex=`mac`, WorkBuddy=`mac`, OpenClaw=`mac,linux`. Schema remains
`0020_pairing_agent_intent`; counts are unchanged across cutover at 22 Agents, 48 Messages, 48
Deliveries, and 8 current Connector bindings. The verified rollback point is
`/opt/agentpost/backups/20260825-2324-3b46e45-pre-010/`, including readable database and attachment
archives, protected configs, checksums, and guarded `rollback-immediate-0.1.10.sh`.

From the actual Alibaba Cloud Linux OpenClaw server, the public contract returned 0.1.10 with
`['mac', 'linux']`, the downloaded wheel digest matched, and Orbit exposed the Linux copy. Its
OpenClaw Gateway remained active with one process after deployment. The reported
`setup_not_released_for_platform` gate is therefore fixed in production. A Human must now retry
the connection and prove pair/send/receive/restart recovery; current evidence is
`openclaw_linux_release_gate_deployed_https_verified`, not `production_accepted`.

## Orbit Agent deletion empty-response fix (deployed, 2026-08-25)

The Agent deletion API correctly completes a history-preserving soft delete and returns HTTP
`204 No Content`. The Orbit browser client nevertheless called `response.json()` whenever the
response headers declared JSON. An empty successful body therefore raised
`Unexpected end of JSON input` after the server mutation had already succeeded. The false error
also prevented the dashboard refresh, making a completed deletion appear to have failed.

Release `c1c3a78` / package `0.1.9` reads a JSON-labelled response as text first and parses it only
when the body is non-empty. Non-empty JSON and HTTP error handling remain unchanged. The API
regression also asserts that soft delete returns an empty body and preserves the Agent's immutable
identity, address, ownership, Inbox, Thread, ACL, Connector records, and message history while
revoking only its current access. A dedicated JavaScript regression reproduces the former browser
exception and verifies both empty-204 and non-empty-JSON behavior against the real frontend helper.

The immutable production paths are `/opt/agentpost/releases/c1c3a78` and
`/opt/agentpost/venvs/c1c3a78`; server, Python SDK, and MCP report `0.1.9`. Schema remains
`0020_pairing_agent_intent`. The public wheel SHA-256 is
`37f325fdfc6052be9abc08e2d4ae1c9d6e1fb57997722a27fb37275f1489a04b`. The verified pre-cutover
rollback point is `/opt/agentpost/backups/20260825-2230-c1c3a78-pre-019/`, containing the database
dump, attachments, protected configuration, prior 0.1.8 wheel, checksums, counts, and guarded
application-only rollback script. Data counts were unchanged across cutover: 22 Agents, 46
Messages, 46 Deliveries, and 19 Connectors.

Local evidence is **365 passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests
deselected**, plus **10 MCP**, **4 TypeScript Connector**, and **2 Orbit JavaScript** tests.
Ruff/format, JavaScript syntax, isolated wheel installation, wheel contents, and diff checks pass.
Post-cutover health/readiness, component versions, public wheel digest, migration head, Nginx,
backup readability, data counts, and fatal-journal checks pass. The deployed public Orbit asset
contains the fix and is served with `cache-control: no-store`.

An authenticated `mars` page currently shows two active and connected Agents, Codex `codex` and
WorkBuddy `buddy`, each with its own delete action. No real Agent was deleted during verification.
Because the old exception occurred after a successful 204, the user's earlier attempted deletion
may already have completed, but the current-only view cannot safely identify the former target.
The Human must refresh and retry the intended remaining Agent deletion before this interaction can
be accepted. Current evidence is `orbit_empty_response_delete_fix_deployed_https_verified`, not
`production_accepted`.

Release `19e406b` / package `0.1.8`, which fixed non-interactive authorization-result flushing, is
the immediate previous release and current application rollback baseline.

## WorkBuddy completed-setup truth (deployed, 2026-08-25)

A real WorkBuddy report exposed that 星轨 treated Human approval and a current binding as a usable
connection before the local process had stored its vault credential and written WorkBuddy's MCP
configuration. The old CLI also sent its first healthy heartbeat **before** host registration. If
the foreground process stopped at that point, 星轨 displayed “已连接” while WorkBuddy had no MCP
entry and could not send.

Release `e22bfeb` / package `0.1.7` makes the completion boundary explicit. A current active
Connector with no successful heartbeat has `connection_state=awaiting_agent`; it is excluded from
the connected-Agent metric and is shown as “等待 Agent 完成本机连接”, with “继续连接” and “取消未
完成连接” actions. The CLI now writes and verifies the host MCP configuration first and reports its
first heartbeat only afterwards. Setup failures return a safe machine-readable stdout result instead
of appearing as empty output. No long-lived credential is added to a file or response.

Production read-only evidence separated two different machines. `020` now has a genuinely current,
healthy WorkBuddy Connector at `020-workbuddy-001@agentpost.me`, with its first heartbeat at 18:36;
it successfully sent `msg_3904d107573943528aea85861ffbaa09` to `magent@agentpost.me`. The `mars`
account has a different new Agent (`wordbuddy`) whose 0.1.6 WorkBuddy Connector has no heartbeat;
the authenticated 0.1.7 page now correctly shows it as waiting and says that it cannot yet send or
receive. No Connector or Agent was deleted during diagnosis.

The immutable production paths are `/opt/agentpost/releases/e22bfeb` and
`/opt/agentpost/venvs/e22bfeb`; server, Python SDK, and MCP report `0.1.7`. Schema remains
`0020_pairing_agent_intent`. The public wheel SHA-256 is
`5447ca2c460f9eb7489a602166acbaee7233badbf085354514ab5e2ed948bd86`. The verified pre-cutover
backup is `/opt/agentpost/backups/20260825-1841-e22bfeb-pre-017/` and contains the PostgreSQL dump,
attachment archive, protected configuration, prior 0.1.6 wheel, checksums, counts, and guarded
application-only rollback.

Local evidence is **364 passed, 1 explicit loopback sandbox skip, and 5 PostgreSQL tests
deselected**, plus **10 MCP** and **4 TypeScript Connector** tests. Ruff/format, JavaScript syntax,
isolated wheel installation, diff, production health/readiness, auth metadata, public WorkBuddy
contract, wheel digest, Nginx, backup readability, migration head, and fatal-journal checks pass.
The first cutover command used an unsupported POSIX-shell `ERR` trap and stopped before any mutation;
0.1.6 was reverified, then the guarded POSIX-compatible cutover succeeded.

Current evidence is `workbuddy_setup_truthful_state_deployed_https_verified`, not
`production_accepted`. `mars` still needs to finish its one WorkBuddy authorization/retry and prove
send/receive from that new independent Agent.

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
