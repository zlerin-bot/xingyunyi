# 星云驿项目交接文档

- 交接阶段：`orbit-empty-delete-response-deployed`
- 核验日期：2026-08-25
- 代码分支：`main`
- 阶段性质：Agent 删除空响应修复已部署为 0.1.9；真实删除仍待 Human 确认重试

## 0. 当前接续摘要（优先于下方历史冻结记录）

最新问题是星轨删除 Agent 时显示
`Failed to execute 'json' on 'Response': Unexpected end of JSON input`。服务端实际上已经成功
执行保留历史的软删除并返回 `204 No Content`；错误来自浏览器请求封装按 JSON 响应头直接
调用 `response.json()`，空 body 因而在服务端完成操作后抛异常，同时跳过页面刷新。0.1.9
已改为先读取文本，仅对非空 JSON body 做解析；非空 JSON 与 HTTP 错误路径保持不变。

当前生产是 `0.1.9` / `c1c3a78` / `0020_pairing_agent_intent`，路径为
`/opt/agentpost/releases/c1c3a78` 与 `/opt/agentpost/venvs/c1c3a78`，server、SDK、MCP 版本
一致。公开 wheel SHA-256 为
`37f325fdfc6052be9abc08e2d4ae1c9d6e1fb57997722a27fb37275f1489a04b`。有效回滚点是
`/opt/agentpost/backups/20260825-2230-c1c3a78-pre-019/`，立即回滚目标为 0.1.8 /
`19e406b`，迁移不降级。切换前后数据计数一致：Agents 22、Messages 46、Deliveries 46、
Connectors 19。

本地证据为 365 passed、1 个 loopback sandbox skip、5 个 PostgreSQL deselected，另有 MCP
10、TypeScript Connector 4、Orbit JavaScript 2 passed；格式、语法、隔离 wheel、wheel 内容
和 diff 检查通过。线上已验证 health/ready、版本、公开 wheel 哈希、迁移、Nginx、备份、
数据计数及 journal。已登录的 `mars` 实页当前显示 Codex `codex` 和 WorkBuddy `buddy` 两个
活动且已连接的 Agent，每张卡片都有删除操作。核验没有点击真实删除。由于旧异常发生在
成功 204 之后，用户此前尝试删除的对象可能已被软删除，但仅凭当前页面无法可靠归因；需
Human 刷新后对仍需删除的目标再次确认。证据标签是
`orbit_empty_response_delete_fix_deployed_https_verified`，不是 `production_accepted`。

0.1.8 / `19e406b` 修复了非交互式授权结果 flush，现作为直接回滚基线。以下 0.1.7 内容
保留为前一切片历史。

最新问题是星轨曾把“Human 已批准并建立 current binding”提前显示为“已连接”，而旧 CLI 又在
写 WorkBuddy MCP 配置前先上报健康心跳，导致前台进程若在两步之间停止，就出现“网页已连接、
本机没有 MCP 配置”的假阳性。0.1.7 已改为：本机 MCP 配置先写入并核验，之后才发首次心跳；
current 但无心跳的 Connector 状态为 `awaiting_agent`，不计入已连接数量，并显示“等待 Agent
完成本机连接”“继续连接”“取消未完成连接”。失败命令会在 stdout 返回安全结构化错误，不再
只有空输出。

生产只读检查确认 `020` 和 `mars` 是两个不同情况：`020` 已有 current + healthy 的独立
WorkBuddy `020-workbuddy-001@agentpost.me`，18:36 首次心跳，并成功向 `magent` 投递消息
`msg_3904d107573943528aea85861ffbaa09`。`mars` 新建的 `wordbuddy` 仍是 0.1.6、无心跳；新版
真实星轨已把它显示为等待状态并明确“现在不能收发消息”。诊断和部署均未删除 Agent、
Connector、Inbox、Thread 或历史。

当前生产是 `0.1.7` / `e22bfeb` / `0020_pairing_agent_intent`，路径为
`/opt/agentpost/releases/e22bfeb` 与 `/opt/agentpost/venvs/e22bfeb`，server、SDK、MCP 版本
一致。公开 wheel SHA-256 为
`5447ca2c460f9eb7489a602166acbaee7233badbf085354514ab5e2ed948bd86`。有效回滚点是
`/opt/agentpost/backups/20260825-1841-e22bfeb-pre-017/`，无数据库迁移，回滚只切回 0.1.6
应用与配置。当前证据标签为 `workbuddy_setup_truthful_state_deployed_https_verified`，不能
写成 `production_accepted`；下一真实门槛是完成 `mars` WorkBuddy 的续接与双向收发。

以下 0.1.6 内容保留为上一切片的发布历史。

最新真实页面检查确认：`mars` 当前只有一个真实 Agent `magent@agentpost.me`，不是四个。
页面中另外三条是这个 Agent 被重新配对后留下的 WorkBuddy/Codex Connector 审计记录。此前
这些旧记录与当前连接并排显示，造成“多个 Agent 且没有删除按钮”的误解。0.1.6 已将“Agent
连接”改为默认只显示 current Connector，旧记录折叠到“查看 3 条历史连接记录”；“我的
Agent”才是可操作的 Agent 列表，每张卡片继续提供重连、断开、修改短名称和“删除 Agent”。
验证期间没有点击删除，也没有清理历史记录。

当前生产是 `0.1.6` / `e378a7e` / `0020_pairing_agent_intent`，路径为
`/opt/agentpost/releases/e378a7e` 和 `/opt/agentpost/venvs/e378a7e`。server、Python SDK、MCP
三处版本均为 0.1.6，公开 wheel SHA-256 为
`c896e6254fa2e7a00dbcffed0485fa49e87846c6a4d8a1abf66b28dba68e133e`。0.1.6 切换前的有效
回滚点是 `/opt/agentpost/backups/20260825-1749-e378a7e-pre-016/`；迁移版本未变化，因此立即
回滚只切回 0.1.5 应用和配置，不应恢复或降级数据库。`20260825-1746...` 与
`20260825-1747...` 是未完成备份，已保留但不得作为回滚点。

部署后分段检查通过服务、组件版本、迁移、health/ready、HTTPS/301、公开 wheel 哈希、
Nginx、备份可读性和 fatal journal 扫描。已登录星轨实页确认一条当前连接、三条折叠历史、
一张真实 Agent 卡片和“删除 Agent”按钮。标签为
`connector_history_ux_deployed_https_verified`，不能写成 `production_accepted`。

以下 0.1.5 内容保留为上一切片的设计与发布历史。

最新部署切片修复测试用户 `020` 的 WorkBuddy 配对导致原 Codex 下线问题。根因不是数据库
只能存一个 Agent，而是星轨在“只有一个已有 Agent”时自动复用它，触发了同一 Agent 的
Connector 替换。现在普通“连接新的 Agent”始终新建独立 Agent；只有从某张 Agent 卡片点击
“连接/重新连接”才携带并核验该 Agent 的目标意图。新 Agent 地址自动按 Human 名、Agent
类型和序号生成，例如 `mars-codex-001`，Human 不填写地址、profile、Connector 或密钥。

星轨每张 Agent 卡片现独立展示已连接/未连接，并提供连接/重新连接、断开、修改短名称、
删除。总览显示 current Connector 数量；Codex 和 WorkBuddy 可各有自己的 current binding。
删除采用保留历史的软删除：仅撤销目标 Connector 并从活动星轨隐藏，Agent ID/address、
Inbox、Thread、ACL、Connector 记录和消息历史继续保留。新增迁移 head 为
`0020_pairing_agent_intent`。

当前生产是 `0.1.5` / `20afebd` / `0020_pairing_agent_intent`，路径为
`/opt/agentpost/releases/20afebd` 和 `/opt/agentpost/venvs/20afebd`。server、Python SDK、MCP
三处版本均为 0.1.5，公开 wheel SHA-256 为
`38dc93bdb9de5938b56d5fb95403ce50e0044b7e3b26304fcf7fb07bcf84b1f7`。本地证据为 363
passed、1 个 loopback sandbox skip、5 个 PostgreSQL deselected，另有 MCP 10 passed、
TypeScript 4 passed；Ruff、format、浏览器 JavaScript 语法、Skill/Plugin 副本一致、Alembic
单 head、PostgreSQL offline SQL 和 diff 检查通过。隔离的真实 PostgreSQL 已通过
`0019 -> 0020 -> 0019 -> 0020` 迁移/回滚循环，线上 health、ready、服务、公开 wheel、星轨
逐 Agent 控件和 journal 均已验证。

0.1.5 切换前备份在
`/opt/agentpost/backups/20260825-1655-20afebd-pre-015/`，含数据库、附件、环境、systemd、
Nginx、0.1.4 wheel、校验和与受确认保护的一键回滚脚本。第一次 0.1.4 切换因 readiness 等待
仅两秒而触发失败；未删除或重建数据，已以前向恢复完成，并修正跨 0020/0019 的回滚顺序。
随后发现 0.1.4 的 SDK/MCP 仍声明 0.1.3，因此没有覆盖不可变 0.1.4，而是增加包边界回归并
发布 0.1.5。

`mars` Codex 的第一次重连确认因短期 Pairing 已过期而返回 HTTP 409；后台结果明确为
`PAIRING_EXPIRED`，不是 Agent 冲突或数据丢失。重新发起的 Pairing 继续指向原 Agent
`91d935c3-1410-4c85-8b56-0b42f4df2da1`，一次 Human 网页确认后恢复同一个
`magent@agentpost.me`、历史和 scoped OS-vault profile，没有新建身份。原任务随后自动恢复：
统一 resolver 分别把“用户020的 Agent”和“用户ianw的 Agent”解析为唯一真实收件人，两条
零附件通知均为 `delivered`，消息 ID 分别为
`msg_b6a4a837574c4b4aadf52d2f068118b8`、
`msg_1cc63d9025774d159b2df15b0a1f7724`。

下一步由 `020` 验证 Codex 与 WorkBuddy 同时在线，由 `mars` 验证逐卡片断开/重连、改简称和
历史保留。当前标签是 `multi_agent_connection_deployed_https_verified`，不能写成
`production_accepted`；`delivered` 也不能表述为对方已读或已接受发布。

---

OpenClaw 检测补充：生产 `AP-OPENCLAW-V1` 接入页与 0.1.5 下载元数据在线。隔离安装的官方
OpenClaw `2026.7.1-2` 在 Node 24.19.0 上通过真实 `mcp set/show/doctor`，并由真实
`mcp probe` 启动当时的生产 0.1.3 `agentpost-mcp`、发现含 resolver 在内的七项工具。检测同时发现
OpenClaw 在 MCP 启动失败时仍可能返回退出码 0；本地源码现改为解析 probe JSON，只有七项
工具齐全且 diagnostics 为空才返回 configured，并修正 OpenClaw 三个官方路径环境变量的
优先级。全量本地结果为 356 passed、1 skip、5 PostgreSQL deselected，加独立 MCP 10
passed；该增强已进入生产 0.1.5 wheel，但尚未在切换后重跑真实 OpenClaw CLI，也未完成真实
Human 授权/收发/重启验收。可选原生
OpenClaw HTTP plugin 在当前官方 CLI 的 build/validate 阶段仍遇到宿主 loader 错误，不能
与已通过的普通用户 MCP 接入路径混为一谈。

Ianw 实测补充：线上 `ianw` handle、`Ianw` Human 归属和 Codex Connector 数据均正确；失败
来自发送端仍运行六工具版 AgentPost 0.1.1 和旧 0.1.2 插件。该次检查时测试机已自动升级为 0.1.3
七工具版，个人插件已刷新为 `0.1.3+codex.20260825045435`。两个原始自然语言表述均通过
现有钥匙串身份只读解析到唯一 `ianw`，未发送消息；需在新 Codex 任务中复测实际发送。
技能已增加旧 MCP 自动升级并恢复原操作的规则。另发现公网 bootstrap 在 macOS 系统
Python 下受 `dataclass(slots=True)` 阻断；修复与回归测试已部署在公共 0.1.5。当前 Codex
身份仍须完成一次网页重连授权，取得实际消息 ID 前不能写成通知已发送。

当前功能提交为 `1abbf56`、`213bc9e`、`10f4d14`、`c62319a`；0.1.3 候选与生产验收修正为
`5a5b509`、`6ada188`：

- Agent 新增可修改的全局唯一短名称 `handle`；不可变 UUID、完整地址以及 Inbox、Thread、
  Message、Delivery、ACL、Connector 和历史归属不变。
- 新增统一 `POST /api/v1/directory/resolve`；解析顺序为完整地址、handle、Agent 显示名、
  Human 姓名与 Agent 类型/名称、关系范围内模糊匹配。禁止把输入机械拼成地址。
- Human 姓名与模糊发现只在同一主人、共同组织、既有往来或明确 allow rule 内进行；不开放
  全站 Human 枚举，返回继续标记 `external_agent_content`。
- Python SDK、CLI、七项 MCP 工具、自然语言 Skill 和星轨均已接入 resolver。唯一匹配直接
  继续发送；歧义返回一次友好候选；未找到不猜地址；旧完整地址仍兼容。
- 星轨在 Pairing 和“我的 Agent”中均可设置短名称，Agent 卡片以短名称为主，底层地址折叠
  展示。Human owner 才能修改。

当前本地证据：352 passed、1 skipped、5 PostgreSQL tests deselected；独立 MCP 10 passed；
Ruff、TypeScript Connector、JavaScript 语法和 diff 检查通过。部署前在隔离的真实
PostgreSQL 数据库执行了五项迁移/并发/重启/100-Agent 验收并全部通过。该切片部署时为 `0.1.3` /
`6ada188` / 数据库 `0019_agent_handles`；公开 wheel 哈希为
`c157dbfd7dbdfd1697c9c85651455beec30e7679062aa9e9b91cea1fd0956757`。生产登录页保留现有
Agent 与历史消息，并可打开短名称编辑器；公开安装包已在全新 Python 3.12 环境安装验证。

切换前 PostgreSQL、附件、环境、systemd、Nginx 和 0.1.2 wheel 备份位于
`/opt/agentpost/backups/20260825-1210-5a5b509-pre-013/`，其中包含需显式确认才执行的一键
回滚脚本。阿里云新快照因配额已满而未创建；未删除任何旧快照。下一步由独立测试 Human
按张子良、`kcode`、同名 Human、多 Codex、not-found、旧地址和改名连续性案例完成真实
体验。当前标签是 `recipient_resolution_deployed_https_verified`，不能写成
`production_accepted`。

下方第 1-11 节是 `v0.1.0-local.1` 的历史冻结记录；与本节冲突时以本节为准。

## 1. 一页结论

星云驿已经形成一个可运行的模块化单体：云驿负责 Agent 身份、地址、持久 Inbox、
离线投递、显式 read/ACK、回复、线程、附件、Directory、ACL 和审计；星轨负责 Human
注册登录、Agent 归属、组织治理、授权、Pairing 和运行观察。PostgreSQL 是生产消息与
授权状态的 Source of Truth，MCP、OpenClaw、A2A 和具体 Agent 工具均为适配层。

当前生产站点为 `https://agentpost.me`。Human 自助注册和 Codex Connector 的真实浏览器
Pairing 已完成一次实际体验；长期 Agent 凭证只进入操作系统钥匙串。已配对 Connector
可以通过 `agentpost-connect` 完成 send/inbox/read/ACK/reply，但 AgentPost 尚未注册为
Codex 原生 MCP 工具，因此“在任意 Codex 任务中直接用自然语言收发”仍是下一开发切片，
不能把“Pairing 成功”宣传为这一能力已经完成。

## 2. 版本与代码基线

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| 本地阶段版本 | `v0.1.0-local.1` | 本交接提交的 annotated Git tag |
| Python 包/API 服务版本 | `0.1.0` | 本阶段没有变更公开协议或包版本 |
| Message Envelope | `0.1` | `schemas/message-envelope-v0.1.json` |
| 阶段建立前 HEAD | `c5e528d` | Pairing 校验修复的部署记录 |
| 当前生产应用代码 | `dda639e` | 已部署的 Pairing 地址校验修复 |
| 生产数据库迁移 | `0018_rate_limit_buckets` | 已在阿里云 PostgreSQL 执行 |
| Git remote | 未配置 | 当前版本仅存在本地仓库，不等于已推送 GitHub |

阶段 tag 只冻结本地代码与文档状态，不会自动修改阿里云、DNS、数据库或线上服务。

## 3. 已实现能力

- Agent Identity、唯一 Address、API-key authentication 和认证上下文发送者绑定。
- PostgreSQL 持久 Inbox、离线投递、幂等发送、Delivery 记录和审计日志。
- 显式 read、ACK、reply、Thread；GET 不隐式改变状态。
- 附件上传/下载、SHA-256、大小和路径校验、参与者权限。
- capability Directory 与 public/contacts/allowlist/private 入站 ACL。
- Python SDK、TypeScript Connector SDK、`agentpost-connect` CLI。
- stdio MCP 七项工具、OAuth-protected Remote MCP 实现和 OpenClaw 适配包。
- Human 邮箱注册登录、MFA、恢复、Human key 轮换、组织邀请和治理。
- Agent Pairing、绑定已有/新建 Agent、Connector 迁移、撤销、轮换和 heartbeat。
- 星轨 Web 控制面、Human 审批队列、组织范围观察和安全操作审计。
- Docker Compose、Alembic、结构化日志、`/health`、`/ready` 和确定性 demo。

## 4. 2026-08-24 本地核验证据

以下检查在阶段提交前实际执行：

| 检查 | 结果 |
| --- | --- |
| `make lint` | Ruff lint 通过；206 个 Python 文件 format check 通过 |
| `make test-fast` | 306 passed，1 个 sandbox loopback skip，5 个 PostgreSQL tests deselected |
| `pytest integrations/mcp/tests` | 8 passed |
| TypeScript Connector Node harness | 4 passed |
| OpenClaw HTTP client Node harness | 4 passed |
| `make demo` | 12 步 Alice/Bob 离线发送、服务重启、read、ACK、reply 全部通过 |
| Python compile / `git diff --check` | 通过 |
| dependency check / lock check | 63 个已安装包兼容；`uv.lock` 可解析 |
| wheel / sdist build | `agentpost-0.1.0` wheel 和 sdist 构建成功 |

本机没有 Docker、PostgreSQL server 或 `psql`，因此以下 5 个 marked PostgreSQL 用例
只完成收集，没有在本机执行：迁移、并发限流、Pairing 原子性与重启、离线消息重启、
100-Agent 并发与幂等状态转换。阿里云真实 PostgreSQL 已有独立部署验收记录，但不能用它
替代本地环境的未执行事实。

## 5. 线上与真实体验状态

- `https://agentpost.me` 的 HTTPS、健康、就绪和星轨入口已部署并验证。
- 生产环境使用 Nginx -> loopback AgentPost -> loopback PostgreSQL，附件目录不公开。
- Human 自助账户创建和一次真实 Codex Pairing 已完成；Connector heartbeat 为 healthy。
- 首次 Pairing 暴露的 `local_agent_id` 422 已在 `dda639e` 修复并部署。
- 长期 `agt_` 凭证不出现在星轨或命令输出，只存入操作系统钥匙串。
- 真实“双 Human、双 Agent、双方不同时在线”的同事体验尚未完成验收。
- 当前证据标签应为 `deployed_https_verified + controlled_pairing_verified`，不是
  `production_accepted`。

生产部署、备份、回滚和服务检查以 `docs/ALIYUN_DEPLOYMENT.md` 为准。任何线上修改前都要
重新做只读 preflight、数据库/附件/配置备份，并保留当前 release 回滚点。

## 6. 当前明确缺口

1. **Codex 原生调用尚未完成。** `codex mcp list` 中没有 AgentPost。当前 stdio MCP 仍要求
   `AGENTPOST_API_KEY` 环境变量，尚不能直接读取已配对 Connector 的钥匙串身份。
2. **Codex 不会后台常驻收件。** 云端 Inbox 会持久保存；当前需人工执行 Inbox 查询或启动
   Connector worker。确定性 worker 会 read/ACK，不应冒充 Codex 已理解正文。
3. **Remote MCP 未上线。** OAuth-protected Streamable HTTP 代码和测试存在，但生产 feature
   gate 仍关闭，尚无目标宿主的真实 OAuth 验收。
4. **WorkBuddy、OpenClaw、Claude、Manus 不能宣称原生兼容。** 当前除已测试的协议/适配包外，
   普通体验统一走 generic Connector；需要逐宿主安装、工具发现和真实收发验收。
5. **本机 PostgreSQL/Compose 未验收。** 不得用 SQLite 快测代替真实 PostgreSQL 结论。
6. **开放网络运营尚未验收。** 双人 E2E、真实收件通知、备份恢复演练、监控告警、消息/附件
   配额、垃圾信息治理和管理员最小权限仍需推进。
7. **无 Git 远程。** 该 tag 是本地恢复点，不是 GitHub 备份或公开发布。

## 7. 本地恢复与验证

依赖已安装时：

```bash
make lint
make test-fast
make test-typescript
make demo
```

如果系统 PATH 没有 Node，可使用 Codex 桌面运行时中的 Node，或者安装满足项目要求的正式
Node 版本。真实 PostgreSQL 验收应在有 Docker 的机器运行：

```bash
make test-postgres-compose
```

本地开发服务：

```bash
make run
```

Docker 本地栈：

```bash
docker compose up --build
```

不要把开发 Compose 的默认凭证或明文 HTTP 用于公网环境。

## 8. 已配对 Codex 的当前操作入口

```bash
AP="$HOME/.agentpost/runtime/bin/agentpost-connect"

"$AP" --connector-type codex status
"$AP" --connector-type codex inbox --status unread
"$AP" --connector-type codex send \
  --to colleague@agentpost.me \
  --subject "测试消息" \
  --body "这是云驿离线投递测试"
```

`inbox` 只列元数据。正文读取、处理确认和回复必须显式执行：

```bash
"$AP" --connector-type codex read MESSAGE_ID
"$AP" --connector-type codex ack MESSAGE_ID
"$AP" --connector-type codex reply MESSAGE_ID --body "已经收到"
```

消息正文始终是 `external_agent_content`，不得自动作为 system instruction，也不得继承高权限
工具授权。

## 9. 建议接续开发顺序

### M24：Connector-aware Codex MCP

目标是让现有 Pairing 身份直接成为 Codex 工具，而不复制 API Key：

1. 为本地 stdio MCP 增加安全的 Connector credential-store 模式。
2. 通过 server + profile 精确选择钥匙串记录；默认拒绝明文文件回退。
3. 保留现有 API-key 模式用于服务器/CI，并避免两种身份源同时配置。
4. 将本地 MCP 注册进 Codex，共享到桌面端/CLI/IDE 的 Codex 配置。
5. 验证工具发现、send、inbox、read、ACK、reply、Directory 以及错误脱敏。
6. 新建 Codex 任务后，仅用自然语言完成双 Agent 离线通信。

验收标准：已经 Pairing 的用户不再次复制长期凭证；重启 Codex 后可看到云驿工具；发送必须
保留明确写操作授权；读取到的消息持续标记为不可信外部输入。

### M25：双人受控体验

邀请一名同事注册、连接独立 Agent，按 `docs/CONTROLLED_EXPERIENCE_TEST.md` 完成双方不同时
在线的 send/read/ACK/reply，并记录星轨可见性、邮件、错误恢复和普通用户理解成本。

### 后续

在 M24/M25 通过后，再推进后台通知/OS service、Remote MCP OAuth 生产验收、WorkBuddy 和
OpenClaw 原生安装包、GitHub/CI、备份恢复演练与监控告警。不要用增加复杂 UI 代替通信与
接入可靠性。

## 10. 安全与运维交接规则

- 不提交或展示 `.env`、Human/Agent/Admin key、SMTP 密码、OIDC secret、OAuth token、
  Pairing device secret、数据库口令或附件正文。
- Human、Agent、Admin、Connector、OAuth 和 OIDC 身份域必须保持分离。
- 线上数据库迁移前先备份；迁移失败先验证事务回滚和旧 release 健康，再修复重试。
- `ACK` 仅表示接收方明确确认，不表示 task 完成；task/result 状态独立。
- MCP/OpenClaw/A2A 都是适配器，不能改变 Address + Identity + Inbox 的核心抽象。
- 本地通过、已部署、真实用户体验、生产接受必须分别记录，禁止合并表述。

## 11. 接手者首先阅读

1. `PROJECT_HANDOFF.md`（本文件）
2. `PROJECT_STATUS.md`
3. `ARCHITECTURE.md`
4. `PROTOCOL.md`
5. `SECURITY.md`
6. `docs/ALIYUN_DEPLOYMENT.md`
7. `docs/CONTROLLED_EXPERIENCE_TEST.md`
8. `ROADMAP.md`

恢复阶段版本后应先运行 `git status --short --branch`，确认没有用户未提交改动，再按 M24 的
小切片方式继续：Design -> Implement -> Test -> Run -> Fix -> Commit。
