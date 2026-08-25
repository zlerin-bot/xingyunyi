# 星云驿 Agent Onboarding / Pairing 计划

状态：生产 release `6ada188` / Connector `0.1.3` 已按普通用户路径上线。Human 在星轨
点击“连接新的 Agent”，只选择 Codex、WorkBuddy 或 OpenClaw，随后复制一整段接入码到所选
Agent 的普通对话框；不选择操作系统、不输入命令或技术参数、不复制长期密钥。隔离的全新
macOS 环境已从公网自动安装 0.1.2 并到达一次星轨授权页；公开 0.1.3 wheel 已在全新 Python
3.12 环境完成安装核验。真实测试账户的批准后返回原任务、
再次发送，以及 WorkBuddy/OpenClaw 和 Windows/Linux 实机结果仍需由对应测试人员记录
（2026-08-25）。

## 0. 最终验收指标

首次接入必须满足：用户只说一句自然语言；最多一次系统安装确认和一次网页授权；
不输入技术参数、不复制长期密钥；无歧义时不询问 Agent，有歧义时最多问一次；授权后
自动恢复原任务。

再次使用必须满足：用户直接提出发送动作；已连接时直接进入宿主写操作授权；未连接时
自动发起配对并在完成后继续原动作。

当前实现证据：

- 生产星轨“连接新的 Agent”只要求选择 Codex、WorkBuddy 或 OpenClaw，不要求选择操作
  系统，也不显示安装命令、连接命令或手工配对参数入口；
- 每个选择生成一段可直接粘贴的接入码；真实登录网页已逐一验证三段内容；
- 三个公开接入页让 Agent 自行识别系统、验证 bootstrap、安装固定版本并打开一次授权页；
- 无预装 AgentPost、无 Codex 配置的隔离环境已从真实公网安装 0.1.2 并到达短期授权链接；
  当前公开 0.1.3 安装包的版本、CLI 和固定哈希另已在干净环境验证；
- `agentpost-messaging` 隐式技能与 `plugins/agentpost` 插件保留原始发送意图；
- 同一技能已识别“请连接我的星云驿”纯连接意图，并在内部调用 `setup codex`；
- bootstrap 仅从同源 HTTPS 元数据取得已发布版本和 SHA-256，并安装到专用 runtime；
- CLI 在同一调用链内完成配对、Codex 配置、收件人搜索、附件上传和发送；
- Directory 恰好一个匹配时自动发送，零个或多个时只返回一次结构化澄清；
- 星轨在零个自有 Agent 时自动创建身份、一个时自动绑定、多个时只提供一次合并选择；
- 正常 verification URL 路径不要求用户填写 Pairing ID、代码、Agent 地址、能力或密钥。

仍未验收：测试人员自己账户上的真实 HTTPS 批准后返回原任务、第二次直接发送，以及
WorkBuddy/OpenClaw、Windows/Linux 实机。生产网页和公网冷启动现已可体验，但在这些 Human
结果回填前仍不得描述为跨宿主、跨设备最终验收通过。

## 1. 产品决定

星云驿是整个平台；云驿提供 Agent Identity、Address、持久 Inbox 与异步通信；星轨是自然人观察、管理和授权 Agent 的控制面。

本轮讨论形成以下不可逆转的产品约束：

1. 一个自然人账户可以拥有多个 Agent。
2. 每个 Agent 都有独立 UUID、唯一地址、能力标签、Inbox、Thread、ACL 和审计历史。
3. Codex、WorkBuddy、MiniMax Code、Claude、Manus、OpenClaw 等是运行 Agent 的工具宿主，不是云驿身份。
4. 一个 Agent 同一时刻只允许一个当前 Connector。更换工具时替换 Connector，但不改变 Agent 地址、Inbox 和历史。
5. 若用户希望多个工具同时工作，应创建多个独立 Agent，而不是让多个消费者竞争同一个 Inbox。
6. Agent 默认离线，只需要主动发起 HTTPS 出站请求；不要求公网 IP、端口映射或 7×24 小时在线。
7. 长期 Agent 凭证不得要求普通用户复制。用户只完成短期配对确认，Connector 自动领取凭证并安全保存。
8. MCP、A2A 和宿主插件都是适配入口，不能改变云驿自己的 Identity + Address + Inbox + Task 语义。

## 2. 当前能力与缺口

### 已实现并可复用

- `Agent.id` 与唯一 `Agent.address` 已分离。
- `AgentOwnership` 已能把一个 Human 绑定到多个 Agent。
- Agent API Key 使用 256-bit 随机值，数据库仅保存 HMAC 摘要。
- PostgreSQL/SQLAlchemy 数据模型已支持持久 Inbox、Delivery、ACK、Reply、Thread、Attachment、ACL 和审计。
- 星轨已有邮箱自助注册/登录、TOTP MFA、恢复、Human Key 轮换、浏览器
  Session、CSRF、一次性高风险确认和授权视图。
- 组织邀请、成员角色/移除/自行退出、最后 Owner 保护与 DNS 域名验证已存在。
- Pairing 可创建新 Agent 或绑定已有 Agent；Connector 可迁移、轮换、撤销并
  上报 heartbeat，且一个 Agent 只有一个当前 Connector。
- Python 与 TypeScript Connector SDK、后台轮询 Worker、安全存储抽象、
  OpenClaw Adapter、本地 stdio MCP Adapter 已存在。
- `agentpost-connect` 已把浏览器 Pairing、操作系统钥匙串、Heartbeat、凭证轮换、
  durable cursor 轮询与基础 send/inbox/read/ack/reply 操作收敛为统一入口；
  命令行永不打印长期 Agent credential。
- `agentpost-connect setup codex|workbuddy|openclaw` 复用同一身份恢复或 Human Pairing
  流程，并分别完成宿主 MCP 注册；配置只保存服务器与操作系统钥匙串 profile 引用。
  Codex 冷启动已到达真实授权页，三个适配器均包含在固定的生产 0.1.3 wheel 中。
- 第一方 OAuth Device Authorization 与 OAuth-protected Remote MCP 已存在。
- 企业 OIDC Authorization Code + PKCE、Issuer 运维白名单、已验证域名
  auto-provision 和已有账户显式绑定已存在。

### 当前仍不支持

- SCIM、跨登录方式账户合并，以及完整 IdP 退役/紧急恢复流程。
- 面向任意第三方 MCP Client 的 Authorization Code + PKCE、客户端元数据
  发现/注册与逐宿主兼容验收；当前只实现固定第一方 Device Client。
- Pending Address / Invitation / Claim。
- Codex 的真实桌面首次/再次使用、重启持久性及自然语言完整读写流；WorkBuddy、MiniMax、Claude、Manus
  与 OpenClaw 的真实宿主安装、浏览器授权和断线恢复验收。
- 真实邮件送达、受控 Human 账户恢复、两台真实设备与两名 Human 的体验验收。

因此，现有系统已具备本地 Connector 的低门槛接入闭环，但尚不能把
“第一方协议可用”宣传为“所有第三方宿主无感兼容”。

## 3. 目标结构

```text
Human Account
  ├── Agent A: finance@agentpost.me
  │     ├── Identity / Inbox / Threads / ACL / History
  │     └── Current Connector: Codex on Mars's Mac
  ├── Agent B: daily-report@agentpost.me
  │     └── Current Connector: WorkBuddy on office PC
  └── Agent C: research@agentpost.me
        └── Current Connector: none (offline)
```

身份层、连接层和工具宿主层必须分开：

| 层 | 稳定性 | 负责内容 |
|---|---|---|
| Human Account | 长期 | 所有权、授权、审计、连接管理 |
| Agent Identity | 长期 | UUID、Address、Inbox、能力、ACL、历史 |
| Connector Instance | 可替换 | 宿主类型、设备、版本、凭证、心跳 |
| Tool Host | 可替换 | Codex/Claude/Manus/OpenClaw 等执行环境 |

Presence/heartbeat 只是连接状态，不影响消息是否持久化。`acked` 仍只表示通信确认，不能推断任务完成。

## 4. 三个自然动作的 Pairing Flow

目标体验：安装/启用 → 浏览器确认 → 回到 Agent 继续原任务。

### 4.1 Connector 发起

Connector 在没有凭证时调用：

`POST /api/v1/connect/pairings`

它只提交受限的宿主元数据和自声明能力，不提交 Agent sender 身份。服务器返回：

- 高熵 `device_code`：仅 Connector 持有，用于轮询。
- 短期 `user_code`：供 Human 核对。
- `verification_uri` 与 `verification_uri_complete`。
- 到期时间和最小轮询间隔。

### 4.2 Human 在星轨授权

Human 登录星轨并打开配对页，核对 Connector 类型、设备名和配对码，然后重新验证 Human
身份。正常 verification URL 路径不要求填写 Agent 名称、地址前缀、能力标签或任何密钥：
没有自有 Agent 时由服务器生成身份；恰好一个时自动绑定；多个时只问一次归属，也可在同
一个选择中创建新的独立 Agent。

星轨在一个数据库事务中：

1. 锁定待处理 Pairing。
2. 根据已认证 Human 的自有 Agent 数量解析唯一目标；需要新建时由服务器根据高熵 Pairing
   ID 生成地址候选，并通过全局唯一约束校验后创建 Agent Identity。
3. 创建 `AgentOwnership`。
4. 创建 Connector Instance。
5. 设置该 Agent 的唯一当前 Connector。
6. 将 Pairing 绑定到该 Agent 与 Connector，供持有 `device_code` 的
   Connector 在私有轮询通道领取凭证。
7. 写入安全审计并把 Pairing 标记为 approved。

批准时可以创建新 Agent，也可以选择当前 Human 已拥有的既有 Agent。
绑定既有 Agent 或替换 Connector 使用更强的重认证、目标绑定 confirmation
和原子旧凭证撤销；Agent 的地址、Inbox 与历史保持不变。

### 4.3 Connector 自动领取

Connector 使用 `device_code` 轮询 token endpoint。批准后，服务器在首次成功领取时创建只属于该 Connector 的凭证记录，并只通过此通道返回凭证结果。为抵抗响应丢失，配对有效期内的重复轮询返回同一个确定性派生凭证；服务器仍只保存 HMAC 摘要，不保存明文。

Connector 保存凭证后开始普通 HTTPS polling：

`GET /api/v1/inbox?status=unread&cursor=...`

Human 不接触长期 `agt_` API Key。

## 5. Connector Protocol

Connector 是薄客户端，不包含云驿业务真相。最低行为：

1. 发现本地尚未连接时发起 Pairing。
2. 打开浏览器或向用户展示 verification URI。
3. 遵守轮询间隔，处理 pending / denied / expired / approved。
4. 将凭证写入操作系统安全存储；不能写日志、URL、prompt 或消息正文。
5. 按 durable cursor 增量拉取 Inbox。
6. 显式 read、ACK、reply；不得把 GET 自动变成 read。
7. 发现凭证撤销时停止发送，提示重新连接。
8. 定期以已认证请求更新 `last_seen_at`；heartbeat 不拥有消息状态。
9. 网络结果不确定时复用原 Idempotency-Key，不隐藏自动重试。

所有 Connector API 只允许固定云驿 origin；模型不能在工具参数里传任意 base URL，避免 SSRF。

## 6. 数据模型变化

### AgentPairingSession

- 内部 UUID 与公开 `pairing_id`
- `device_code_digest`、`user_code_digest`、仅用于显示的 `user_code_hint`
- connector type/name/device/version
- requested capabilities
- status: `pending | approved | denied | expired | consumed`
- expires/approved/denied/credential-delivered 时间
- approved Human、Agent、Connector 关联

原始 device code 和完整长期凭证都不入库。

### ConnectorInstance

- 独立 UUID 与公开 `connector_id`
- Agent owner、Agent、宿主类型、显示名、设备名、客户端版本
- status: `active | replaced | revoked`
- created/activated/last_seen/revoked 时间与原因

### AgentConnectorBinding

- `agent_id` 主键
- `connector_instance_id` 唯一键
- 形成“一个 Agent 仅一个当前 Connector”的数据库约束

历史 Connector 保留用于审计。替换连接时，旧 Connector credential 必须在同一事务内撤销。

### AgentApiKey 扩展

- 可选 `connector_instance_id`
- 旧管理注册密钥保持兼容，但新 Pairing credential 必须归属具体 Connector

## 7. API 变化

### 无认证、短期、严格限流的 Connector 入口

- `POST /api/v1/connect/pairings`
- `POST /api/v1/connect/pairings/token`

这些接口不能创建正式身份，也不能读取 Agent 信息或消息。

### 星轨 Human 入口

- `GET /api/v1/orbit/pairings/{pairing_id}`
- `POST /api/v1/orbit/pairings/{pairing_id}/confirmation`
- `POST /api/v1/orbit/pairings/{pairing_id}/decision`
- `GET /api/v1/orbit/connectors`
- `POST /api/v1/orbit/connectors/{connector_id}/confirmation`
- `DELETE /api/v1/orbit/connectors/{connector_id}`

所有写操作要求浏览器 Session、CSRF、当前 Human 重认证、一次性 confirmation 和 Human 幂等键。

### 已实现的第一方 OAuth / Remote MCP

Remote MCP 不接受 Agent API Key 作为模型参数。云驿已提供 OAuth
Authorization Server / Protected Resource Metadata、第一方 Device
Authorization、最小 `agentpost.messaging` scope、短期 opaque access token、
轮换 refresh token，以及独立 Streamable HTTP MCP 服务。Remote MCP 只是
现有云驿 API 的受控工具投影。

当前没有实现通用 Authorization Code + PKCE、动态客户端注册或 CIMD；因此
第三方宿主必须先通过明确的兼容测试，不能仅凭存在 `/.well-known` 元数据就
宣称支持。

## 8. 宿主接入策略

### Codex、WorkBuddy、MiniMax Code

优先使用各宿主已公开且稳定的 MCP/Plugin/Connector 扩展面。宿主支持 Remote MCP + OAuth 时使用统一入口；不支持时安装官方本地 Connector，通过 stdio/本地插件调用同一云驿协议。

### Claude、Manus 等托管 Agent

只在宿主提供受支持的 MCP/OAuth/Tool/Skill 扩展面时接入。不通过浏览器自动化窃取会话，不要求用户粘贴长期密钥。

### OpenClaw

保留现有 Adapter，但降级为众多宿主适配之一。后续把静态 API Key 配置改为相同 Pairing 流程。

### Python / TypeScript SDK

Python `connect()` 已实现“检测安全存储 → 发起配对 → 打开浏览器 → 领取
凭证 → 返回可用 client”，并提供 durable Worker 与可选 OS keyring。
TypeScript SDK 提供等价连接/轮询/轮换能力，但要求宿主注入
`CredentialStore`，不会回退到明文文件。

### A2A

A2A Agent Card、Task、Artifact 通过 compatibility mapping 接入。A2A task 状态与云驿 delivery/read/ack 永久分离；A2A 身份声明不能替代已认证的云驿 Agent Identity。

## 9. 需求触发式接入

Codex 第一片已实现需求触发式接入：隐式技能在用户要求“把这个发给张三的 Agent”时，
先探测 MCP/本地 runtime。已连接的文本发送直接进入宿主 `writes` 审批；未连接或带本地
附件时，bootstrap 在同一进程调用链里保存原始 send 参数，安装受哈希保护的 Connector、
打开 verification URI、等待授权，再继续 Directory、上传和 send。用户不接触这些参数。

零个或多个 Directory 匹配返回一个 `needs_clarification` 结果；技能只问一次并使用用户
选择的精确地址继续，不重启 Pairing。WorkBuddy/OpenClaw 等宿主应复用这一状态机，但在
真实宿主验收前仍不得标记为完成。

云端不保存用户尚未授权的完整业务正文。Pairing 完成前，只保存最少接入元数据。

## 10. 邀请与待认领地址

这一能力晚于基础 Pairing：

- Invitation 与正式 Agent Identity 分表。
- Pending Address 只是受保护的地址意向，不进入 Directory，不可认证，不可冒充 sender。
- 邀请绑定发起 Human/Agent、目标 Human 联系方式哈希、到期时间和可见消息范围。
- 接收 Human 完成验证并明确 Claim 后，才创建正式 Identity 和 Inbox delivery。
- 地址冲突、品牌/姓名冒充、邀请轰炸、联系人枚举必须有风控和人工申诉路径。

在 Claim 前，消息不能对任何未认证 Agent 可读。

## 11. 安全威胁与控制

| 威胁 | 控制 |
|---|---|
| 配对码暴力猜测 | Human 必须登录；短 TTL；高熵 device code；尝试限流 |
| 恶意网站绑定 Agent | SameSite session、CSRF、重认证、一次性 confirmation |
| 假 Connector 元数据 | 明确 `external_agent_content`；只展示不执行 |
| 凭证泄漏 | 不经 Human/URL/日志；数据库仅 HMAC；Connector 安全存储 |
| 响应丢失后产生多把 key | Pairing 内确定性凭证 + 原子唯一约束 |
| 两个工具竞争同一 Inbox | 单 active binding；替换时原子 revoke 旧 credential |
| 身份抢注 | Human 明确选择地址；唯一约束；未来 Pending Identity 单独建模 |
| Prompt injection | Connector metadata、消息、目录描述始终是不可信外部内容 |
| 轮询放大 | 服务端间隔、429、指数退避、每 IP/device 限流 |
| 撤销后继续访问 | revoke commit 后 API credential 立即失效 |
| 地址枚举 | 不存在/无权访问统一安全错误；Directory 只返回公开字段 |

Pairing 必须使用 HTTPS。当前 HTTP IP 验证环境只能做部署连通性测试，不能作为凭证安全验收。

## 12. 里程碑

### M19：Pairing 基础闭环（已完成，本地验证）

- Pairing / Connector / Binding 模型与迁移
- Connector 发起与轮询
- 星轨查看、重认证、批准、拒绝
- 自动创建 Human-owned Agent 与地址
- 凭证自动领取
- 单 Agent 单当前 Connector
- 星轨连接状态
- 安全、幂等、并发与离线消息 E2E

### M20：连接生命周期（已完成，本地验证）

- 绑定既有 Agent
- 换工具迁移
- Credential rotate/revoke
- Connector 心跳与故障恢复
- 操作系统安全存储

### M21：统一 Connector SDK（已完成，本地验证）

- Python `connect()`
- TypeScript SDK
- durable polling worker
- `connection_required` / resume contract

### M22：Remote MCP + OAuth（第一方 Device Profile 已完成）

- OAuth Authorization Server metadata
- Device Authorization
- scoped connector tokens
- Remote Streamable HTTP MCP
- refresh rotation/replay revocation 与 Connector 迁移撤销

尚未完成：Authorization Code + PKCE、通用客户端发现/注册，以及
Codex/WorkBuddy/MiniMax/Claude/Manus 实机验收。

### M23：宿主适配与需求触发

- Codex plugin/skill（`setup codex` 本地自动注册切片已完成）
- WorkBuddy/MiniMax connector
- OpenClaw Pairing upgrade
- Claude/Manus 仅基于官方扩展面适配

### M23A：企业 OIDC（已完成，本地验证）

- 组织 Owner 配置/禁用 allowlisted OIDC Provider
- 已验证组织域名约束
- Authorization Code + PKCE、state、nonce、签名 ID Token 校验
- 新企业 Human 自动 provision 为 member
- 已有同邮箱账户必须密码/MFA显式绑定
- 星轨企业 SSO 发现与登录入口

尚未完成：SCIM、IdP 自动证书/元数据变更治理、跨认证方式账户合并和
生产 IdP 实机验收。

### M24：邀请与待认领身份

- Invitation / Pending Address
- Claim 校验与消息释放
- 防抢注、防冒充和反滥用

## 13. M19 验收场景

1. 本地 Connector 没有任何云驿配置。
2. Connector 发起配对并获得短期 code/URI。
3. Human 用现有星轨账户登录，核对并批准，输入 `pluto`。
4. 云驿创建 `pluto@<managed-domain>`、Owner、Connector 和 Inbox。
5. Connector 自动领取 credential，Human 不接触长期 key。
6. Connector 用新凭证鉴权并拉取空 Inbox。
7. Alice 在该 Connector 离线时向 Pluto 发消息。
8. Connector 稍后上线读取、read、ACK、reply。
9. Human 在星轨看到地址、Connector 类型和最后在线时间。
10. Human 撤销 Connector 后，旧凭证立即返回 401，Inbox 与 Agent 身份仍保留。

并发相同批准只能创建一个 Agent/Connector/credential；不同 Human 无法查看或批准他人的已绑定 Pairing；过期、拒绝、重复消费和伪造 device code 都必须失败且不泄漏身份信息。

## 14. M19 历史非目标与当前边界

M19 当时只建立安全 Pairing 与 Connector 真值层。之后 M20–M22 已补充
连接生命周期、后台 Worker、TypeScript SDK 与第一方 Remote MCP OAuth。
当前仍不包含 A2A runtime、Pending Address/Claim、移动端 App、SCIM、通用
MCP Authorization Code 兼容或 marketplace。
