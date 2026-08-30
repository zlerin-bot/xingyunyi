# 星云驿项目交接文档

- 交接阶段：`v0.1.33-human-collaboration-contract-prototype-local`
- 核验日期：2026-08-30
- 代码分支：`main`
- 阶段性质：生产仍为 0.1.33；Human 协作视图信息合同与新版群交互原型已在本地冻结并完成响应式浏览器验收
- 当前生产状态：`765ec5a / 0.1.33`，schema 为 `0026_message_attachment_links`

## 0. 当前接续摘要（优先于下方历史冻结记录）

### Human 协作视图信息合同与新版群交互原型（本地设计切片）

`docs/星云驿Human协作视图信息合同_20260830.md` 已冻结为 `v1.0.1 / FROZEN_FOR_PROTOTYPE`。
合同明确星云驿只有一份持久化协作事实，但 Human 默认只消费管理结论层：最新结果、需 Human 决定、
异常与风险、责任与期限、协作就绪和更新时间；有意义的协作过程按需展开，完整正文、Delivery、ACK、
消息编号、原始 JSON 与技术错误进入技术审计层。`delivered/read/ACK/result/Human decision` 保持独立，
Human 打开或折叠页面不得改写 Agent 状态。

Human 可见 Agent 身份统一使用“Human 的 Agent”格式，例如“mars 的 codex”；责任人、等待对象、
成员就绪、关键过程和附件消费状态不得只显示可能重名的 Agent 短名称。无法确认或无权显示 Human 时，
明确写“Human 待确认 的 Agent”，底层仍以不可变 `human_id + agent_id` 区分。

`docs/星云驿Human协作视图群交互原型_20260830.html` 是对应的自包含可点击原型。桌面端保留三栏，
移动端使用“协作群列表 → 群概览 → 事项详情 → 返回”的分层；可以切换小孔和拉格朗日，查看 Human
管理摘要、异常、结果、事项过程、成员协作就绪、附件消费状态以及隔离的技术审计信息。原型使用
2026-08-30 的脱敏观察快照，不连接生产、不发送消息、不提交决定，也不把模拟按钮包装成已上线能力。

验收证据：内联 JavaScript 语法检查通过；页面不包含外部 URL、iframe、表单、网络请求、动态代码执行
或浏览器持久化。1280px 桌面端和 390×844 移动端均完成群切换、列表/概览/事项返回、就绪抽屉、
审计抽屉和附件信息边界检查，`body/document scrollWidth = innerWidth`；抽屉 Escape 关闭后焦点返回
原触发按钮。该切片没有改动生产代码或接口，生产仍为 `765ec5a / 0.1.33`。

下一实现切片应让服务端生成同一份 `human_summary` 读模型，并先落地小孔/拉格朗日所需的结果、待决、
异常和协作就绪口径；`2c8e5a3` 的连接复用说明修复仍待与下一版本一起部署，不能算入当前生产 0.1.33。

### 组织协作群附件与拉格朗日反馈原型（0.1.33 已部署并完成 HTTPS 后检）

组织频道消息现在接受最多 32 个已上传附件 ID。一个附件对象在服务端只保存一次，通过新增的
`message_attachments` 关系同时关联到该组织 Event 的每一份投递 Message；发送者和所有组织参与
Agent 读取到相同文件名、类型、大小和下载内容，组织外 Agent 仍按既有 not-found 边界返回 404。
重试同一幂等键不会重复绑定，已经绑定的上传不能被另一个 Event 再次占用。Agent API 和 Orbit 的
下载鉴权都改为读取关系表，不再只依赖旧的单 Message 外键。

SDK、MCP、OpenClaw、Manus 本地文件夹适配器及 CLI 均已发布组织附件字段。新增
`agentpost-connect send-organization` 可先上传本地文件再创建组织 Event；公开机器合同明确发布
`attachment_field=attachments`、同一附件对象跨投递副本共享、所有有效参与 Agent 可见。两份安装
Skill 在当前宿主 MCP schema 尚未刷新时使用固定版本 bootstrap，仍保持组织群语义，不降级成私聊。

本地证据：组织附件聚焦测试在内共 25 passed；Ruff check 通过、Ruff format 全部 257 files 通过；
完整 non-PostgreSQL 回归为 468 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests
deselected。SDK TypeScript 4 passed、Orbit JavaScript 33 passed、OpenClaw 4 passed，OpenClaw dist
语法检查通过；Alembic 单一 head 为 `0026_message_attachment_links`。PostgreSQL 专属测试未在本地
运行，生产切换已完成 PostgreSQL `0025 → 0026 → 0025 → 0026` 演练和正式升级。

发布提交为 `765ec5a / 0.1.33`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `a3f2dce70a2331295f8da24298efb8c0310d0d1e1eb318018e3a1499b17daadf`、
`e85ec3f0d1db321a91126e62475a669fcb1bca909667761316e29b66d231bcfb`、
`8c5bc38f4bd95817e5b946ffe0713c4f53644388cf30370edaf78298184ad926`。Workbench 单文件上传后，
staging 返回 `stage_status=ok`；受保护切换返回 `deploy_status=ok release=0.1.33 commit=765ec5a`，
耗时 39 秒，备份为 `/opt/agentpost/backups/20260830-085052-765ec5a-pre-033/`。

独立 postflight 返回 `postflight_status=ok`，耗时 2 秒，schema 为
`0026_message_attachment_links`；切换前后均为 62 Agents / 285 Messages / 285 Deliveries /
27 Attachments / 16 Humans。AgentPost PID 从 `309741` 更新为 `324922`，Nginx 与 PostgreSQL PID
保持 `245451/321670`；备份清单、即时回退脚本、Nginx 配置、受保护环境文件和发布后 warning 日志
检查均通过。开发机公网 health/ready 均返回 0.1.33，公开合同包含组织附件字段，公开 wheel 哈希
精确一致，未知下载返回 404。当前状态是 `deployed_https_verified`，不是
`production_accepted`。

已读取拉格朗日原 Thread `bf677074-87bd-4233-8f51-5403d401a023` 的反馈：pa020 建议冻结
“组织 → 默认协作群 → Thread → Event → Delivery”，群首页优先待办和结果，责任状态指向具体
Agent，正文点名与结构化分派冲突时暂停，附件进入 P0，并区分组织归档与个人归档；zcode 只确认了
外部操作需要 Human 授权，alalei 暂未回复。`docs/星云驿组织协作群交互样式稿_20260829.html`
已按这些反馈改版，补充附件安全预览、重复 Thread 人工决策、固定话题摘要、“跳到最新”和移动端
群列表/话题分层。1440px 桌面和 390×844 移动端均完成主流程、筛选、抽屉、附件说明、返回和
横向溢出检查，控制台无 warning/error。

修订稿已复用当前健康的 `magent / codex` Connector profile，作为一个真实 HTML 附件继续发送到
同一拉格朗日 Thread；Event 为 `1edf242f-74cc-4a4a-a673-eafa15ce0615`，三份 Message 为
`msg_246b01f197db4750afe589a75374b6b3`、`msg_3a6ba041c909470fa7b21022da40a10c`、
`msg_dd7b78eb314a4a59b871f18c48f23c70`，`attachment_count=1`，服务端返回 `accepted`。发送前发现
安装 Skill 的 fallback 有一处关键缺口：已认证 MCP 只是 schema 较旧时，说明只要求运行最新版
bootstrap，却没有要求把当前 MCP 的 `AGENTPOST_PROFILE` 原样传给新进程，导致新 CLI 按设备名
推导了另一个 profile 并误触发配对。多余配对已中止；两份 Skill、公开协议文档和 `/connect/{host}`
冷启动说明现已明确“已认证读取成功即复用现有 profile，不能重新配对”。这是后续待发布的说明修复，
不冒充已经进入当前生产 0.1.33。三份群投递已经创建，但 Agent ACK 和评审回复仍是独立待观察事实。

### 组织邀请闭环、组织解散与协作群改进评审（0.1.32 已部署并完成 HTTPS 后检）

待接受的组织邀请现在明确显示邀请人、组织名称和有效期；“接受并进入组织”成功后直接打开组织详情，
确认本人已经出现在成员列表中、默认或显式参与 Agent 已生效，并说明星轨中的组织群聊已经可见。
“组织与成员”入口同步显示待确认邀请数量。Owner 可以在组织详情中解散组织，但必须输入完整组织名称
和当前星轨密码重新确认；服务端将组织归档、撤销待接受邀请并释放显式 Agent 归属，不硬删除历史消息
或审计记录，归档组织及其历史群聊不再进入 Human 或 Agent 的可见读取范围。

本地证据：Ruff check 通过、Ruff format 全部 255 files 通过；组织治理、系统 API、安装 Skill 与包边界
聚焦测试 35 passed，Orbit JavaScript 28 passed；完整 non-PostgreSQL 回归 465 passed、1 个预期
loopback sandbox skip、5 个 PostgreSQL tests deselected。隔离 Orbit 桌面端和 390×844 均完成组织解散
界面、名称校验和布局检查，窄屏 `body/document scrollWidth = innerWidth = 390`，控制台无
warning/error；为避免破坏测试组织，真实浏览器未执行最后一步成功解散，服务端成功路径由集成测试覆盖。
PostgreSQL 专属测试未在本地运行。

发布提交为 `18101fb / 0.1.32`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `0a8c3af9f707b1c21ff701ee7ed1dbbb6c5d1283411367061be463598f5b38a3`、
`fddc1d89594e69200bf217e6e0de40d6f9350582776101544700fd340479c9ad`、
`af686bc4175246f9de157b17fbc39a239472524faf38375082cc3289d144ebf2`。本轮进入生产核对时，
`current` 已由同目标既有发布切到 `/opt/agentpost/releases/18101fb`，因此没有重复执行生产切换。
现网记录的部署时间为 `2026-08-29T08:34:51+08:00`，备份为
`/opt/agentpost/backups/20260829-083421-18101fb-pre-032/`。

独立重跑 postflight 返回 `postflight_status=ok release=0.1.32 commit=18101fb
schema=0025_human_thread_archives`，耗时 2 秒；当时数据量为 60 Agents / 246 Messages /
246 Deliveries / 27 Attachments / 15 Humans。AgentPost、Nginx、PostgreSQL PID 分别为
`309741/245451/304910`，服务均 active；受保护环境文件权限为 `600 root:root`，磁盘使用率 26%。
开发机公网 health/ready 均返回 0.1.32，公开 wheel 哈希精确一致，未知下载返回 404。生产登录页可正常
渲染，但当前浏览器的既有登录态已经失效，因此真实受邀者接受、成员列表即时刷新、星轨群聊出现和
Owner 解散仍为 `待确认`。当前状态是 `deployed_https_verified`，不是 `production_accepted`。

后续产品建议已写入 `docs/星云驿组织协作群后续改进建议_20260829.md`，配套的自包含交互样式稿为
`docs/星云驿组织协作群交互样式稿_20260829.html`。样式稿已完成桌面和 390×844 的群概览、话题筛选、
时间正序详情、责任人进度、成员抽屉及列表/详情返回验收，无横向溢出和控制台 warning/error。
完整建议正文已作为组织 `request` 发到拉格朗日群 Thread
`bf677074-87bd-4233-8f51-5403d401a023`，指定 alalei、pa020、zcode 三个 Agent 回复；Event 为
`71a9141f-a1bf-41eb-9a94-510fd6a7ef04`，三份 Delivery 已创建。0.1.32 的组织群消息合同没有附件字段，
因此 HTML 不能作为群文件绑定，也没有降级成私聊附件；“组织群附件能力”应作为真实 P0 缺口进入下一切片。

### 归档入口、Agent 可见性与星轨返回逻辑（0.1.31 已部署并完成 HTTPS 后检）

星轨桌面端和移动端主界面恢复为“待我处理、任务进展”两个快捷入口；“已归档对话”迁到
“设置”，并提供独立列表、完整对话查看和恢复路径。归档仍不删除服务器消息、不改变其他 Human
的视图，也不改写 Delivery、Agent read、ACK 或任务状态；但归档 Human 直接拥有的 Agent 此后会
从星云驿 Inbox、消息详情和 Thread 列表中排除该完整 Thread，恢复后重新可见。该规则只约束后续
服务端读取，无法远程擦除 Agent 在归档前已缓存的内容。

“待我处理”和“任务进展”不再形成难以退出的页面状态：点击左侧/底部“星轨 · 我的对话”、中栏
“我的对话”父节点或页面非交互空白处，都会清除快捷状态并返回全部对话；点击任务卡、审批卡和表单
控件不会误触返回。浏览器前进/后退也会在归档、异常和全部列表之间重新读取正确的数据范围。

本地证据：Ruff check 通过、Ruff format 全部 255 files 通过、Orbit JavaScript 28 passed；完整
non-PostgreSQL 回归 463 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected。
隔离浏览器桌面端完成待处理/任务页空白返回、两个“我的对话”入口返回、设置归档、打开和恢复；
390×844 下只有两个快捷入口同排，`body/document scrollWidth = innerWidth = 390`，底部星轨可从任务
页返回全部对话，控制台无 warning/error。PostgreSQL 专属测试未在本地运行。

发布提交为 `1430601 / 0.1.31`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `b207d15e231f3dac39bbd8e8a5582a8a8d57cba10974cc51e4c3c65068457542`、
`f26bf81009b06dd984269d45e80f685443e2a61b8e3bb3cf7798107f68a0dd9d`、
`eccc7ca998a3b806b1a752c6b41497870f42b0875bbe7952b86f0c0c26bab613`。Workbench 单文件上传后，
staging 返回 `stage_status=ok`；受保护切换返回
`deploy_status=ok release=0.1.31 commit=1430601`，耗时 40 秒，备份为
`/opt/agentpost/backups/20260829-063458-1430601-pre-031/`。

独立 postflight 返回 `postflight_status=ok`，耗时 3 秒，schema 保持
`0025_human_thread_archives`；发布前后均为 60 Agents / 234 Messages / 234 Deliveries /
27 Attachments / 15 Humans。AgentPost PID 从 `300439` 更新为 `306456`，Nginx PID 保持
`245451`。需要单独记录：发布前只读核对之后、staging 之前，系统
`apt-daily-upgrade/unattended-upgrade` 在 06:33:36 自动重启 PostgreSQL，PID 从 `245492`
变为 `304910`；这不是切换脚本触发，数据库在发布开始前已恢复 active，后续迁移演练、生产读取和
数据量校验均通过，但不能把整个发布窗口描述为 PostgreSQL 进程连续。

开发机公网 health/ready 均返回 0.1.31，认证配置发布六类宿主的 macOS/Linux/Windows，公开 wheel
哈希精确一致，未知下载返回 404。生产登录页可正常渲染，但当前浏览器没有生产登录态，因此设置中的
归档列表、真实 Agent 归档后读取阻断及恢复后的重新读取仍为 `待确认`。当前状态是
`deployed_https_verified`，不是 `production_accepted`。

### 个人资料用户名修改（0.1.30 已部署并完成 HTTPS 后检）

“设置 → 个人资料”已从用户名只读展示改为可直接编辑和保存。用户名继续遵守 3–32 位小写字母、
数字或名称中间单个连字符的规则，并由服务端和数据库共同保证全平台唯一；已占用和格式错误都会给出
普通用户可理解的明确提示。修改只更新公开寻址标识，Human ID、组织关系、消息、Agent 所有权和历史
审计不变；成功操作写入 `control.human_username_updated` 审计记录，新目标解析立即使用新用户名。

本地证据：聚焦后端 2 passed；完整 non-PostgreSQL 回归 463 passed、1 个预期 loopback sandbox
skip、5 个 PostgreSQL tests deselected；Ruff check/format、JavaScript syntax 和 Orbit JavaScript
27 passed。隔离 Orbit 桌面端完成真实修改并即时显示成功结果；Chrome 390×844 下完成登录、修改和
保存，`body/document scrollWidth = innerWidth = 390`，输入框、按钮和表单均位于 47–343px，控制台
无 warning/error。PostgreSQL 专属测试未在本地运行。

发布提交为 `b4d3217 / 0.1.30`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `57733f784ce483b3c06d4c9aa2ce645dbfe22782012473e569b5130df57c06ac`、
`b7203307d36aa8d793ea5b4e25afd831019b70b25dcb20b328da93c13d270e3a`、
`7fe76f50e4a7fdfd04fd625e4ee1587175568fd70de56d08fb5aba50bad3f749`。Workbench 单文件上传后，
staging 返回 `stage_status=ok`；受保护切换返回
`deploy_status=ok release=0.1.30 commit=b4d3217`，耗时 38 秒，备份为
`/opt/agentpost/backups/20260828-223027-b4d3217-pre-030/`。

独立 postflight 返回 `postflight_status=ok`，schema 保持 `0025_human_thread_archives`；后检为
59 Agents / 220 Messages / 220 Deliveries / 27 Attachments / 15 Humans。发布前为 59 / 215 /
215 / 27 / 15，部署期间新增的 5 条消息和 Delivery 是持续业务写入，不是数据丢失。AgentPost、
Nginx、PostgreSQL PID 为 `300439/245451/245492`，确认 Nginx 与 PostgreSQL 未重启。开发机公网
health/ready 均返回 0.1.30，公开 wheel 哈希精确一致，未知下载返回 404；六类已发布宿主的
macOS/Linux/Windows 配置保持一致。生产登录页可正常渲染，但当前浏览器没有生产登录态，因此
登录后的用户名修改与真实跨 Human 新用户名寻址仍为 `待确认`。当前状态是
`deployed_https_verified`，不是 `production_accepted`。

### 组织好友邀请与自有 Agent 候选解释（0.1.29 已部署并完成 HTTPS 后检）

组织邀请新增“沟通过的好友”下拉框。候选只从当前 Human 名下 Agent 的真实发送或接收记录推导，
按最近沟通时间排序，并排除本人、现有组织成员和仍有效的待接受邀请；未发生真实沟通的陌生 Human
不会被枚举。选择好友后自动填写其全平台唯一用户名，同时保留手工输入准确用户名的首次邀请入口。

“添加我的 Agent”此前只显示 `!agent.organization` 的自有活动 Agent，导致已经显式加入当前或其他
组织的 Codex 等 Agent 被静默隐藏。现在列表展示全部自有活动 Agent：可加入项正常选择；已在本组织
或已加入其他组织的项保留可见但禁用，并直接说明原因。底层仍保持一个 Agent 最多显式加入一个组织；
按组织计算的默认 Agent 参与多个组织的规则未改变。

聚焦后端 10 passed；Ruff check/format、JavaScript syntax 和 Orbit JavaScript 27 passed；完整
non-PostgreSQL 回归 462 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected。
隔离 Orbit 桌面端确认完整 Agent 候选及原因文案；390px 下组织弹窗、Agent 选择和好友选择均为单列，
`document/body scrollWidth = 390`、弹窗 `scrollWidth = clientWidth = 350`，控制台无 warning/error。
PostgreSQL 专属测试未在本地运行。发布提交为 `26ee7c7 / 0.1.29`。干净归档生成的源码、公开 wheel、
Workbench 单上传包 SHA-256 分别为
`3c0b100ef976e98a7ab93dd3d4e8265f1ba7c4d52c9cc0dc98d3bec35347be5a`、
`ac7615ee4014520631b46cb7da45d9ba6c1008dd5d7a2fedb3c86362098eb135`、
`5a7a4c55ec45bac05130a36d403aa6d943eebe7b0c7c2fe205f271fc339a065f`。Workbench staging 返回
`stage_status=ok`；受保护切换返回 `deploy_status=ok release=0.1.29 commit=26ee7c7`，耗时 39 秒，
备份为 `/opt/agentpost/backups/20260828-215859-26ee7c7-pre-029/`。

独立 postflight 返回 `postflight_status=ok`，schema 保持 `0025_human_thread_archives`；切换后为
59 Agents / 214 Messages / 214 Deliveries / 27 Attachments / 15 Humans，关键数据量与切换前一致。
AgentPost、Nginx、PostgreSQL PID 为 `297650/245451/245492`，确认 Nginx 与 PostgreSQL 未重启。
开发机公网复核 health/ready 均为 0.1.29，公开 wheel 哈希精确一致，未知下载返回 404；六类已发布
宿主的 macOS/Linux/Windows 配置保持一致。生产登录页可正常渲染，但当前浏览器没有生产登录态，
因此登录后的好友邀请下拉框、自有 Agent 完整候选及原因文案仍为 `待确认`。当前状态是
`deployed_https_verified`，不是 `production_accepted`。

### 历史组织 Thread 归组与 Human 可恢复归档（0.1.28 已部署并完成 HTTPS 后检）

生产截图确认历史“拉格朗日”Thread 的首条组织消息带有组织频道元数据，但较新的普通回复可能没有
重复携带该字段。0.1.27 列表错误地只看最后一条消息，导致整个 Thread 被投影成私聊并留在组织群
父节点外。本切片改为扫描完整 Thread：只要其中存在真实组织频道消息，就沿用该消息的组织 ID 和名称
进行父子归组；不改写历史消息、路由、送达或回复关系。因此历史拉格朗日测试对话可直接并入群下，
无需伪造迁移或删除服务器数据。

“我的对话”每张完整对话卡和详情头部新增“删除”入口，语义为当前 Human 的可恢复归档，不是服务器
删除。经 390px 实机布局复核后，列表卡片上的删除入口已移除，删除/恢复只在打开完整对话后的详情页
提供，避免每张卡片为操作按钮预留高度。新增 `human_thread_archives`，按
`human_user_id + thread_id` 独立保存；默认列表排除归档。桌面端在列表工具区提供“已归档对话”，
移动端把“待处理 / 任务 / 已归档”压缩为同一行三个轻量入口，进入归档列表后打开详情即可恢复。
归档不会拆散回复链，也不会影响其他 Human 视图、
Delivery、Agent read、ACK 或任务状态；新消息也不会擅自自动恢复。无权 Thread 仍统一返回 404。

本地证据：Ruff check/format 全通过；JavaScript syntax 和 Orbit JavaScript 27 passed；完整
non-PostgreSQL 回归 461 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected；
Alembic 单一 head 为 `0025_human_thread_archives`。隔离 Orbit 桌面端确认详情页删除入口、明确的
非服务器删除说明和直接可见的归档库；390px 下确认三个快捷入口同排、列表不再出现删除按钮、
详情页删除按钮可见，以及
`document/body scrollWidth = 390`，控制台无 warning/error。PostgreSQL 专属测试未在本地运行，
但生产切换脚本已完成 PostgreSQL `0024 → 0025 → 0024 → 0025` 演练和正式迁移。

发布提交为 `3f869b1 / 0.1.28`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `ffc0c613bfba009b99293b1fa3c7c3a7bc94aaddc0032ec2da87f1485f3719b3`、
`b4d3aeccecc4c0f36b603e6b80330c53ee81f75948fda123054b88207590db95`、
`dc16cfc4e6eb9459435d466510244efe918dde6d326bbdf3319334866de92f8e`。Workbench staging 返回
`stage_status=ok`；受保护切换返回 `deploy_status=ok release=0.1.28 commit=3f869b1`，耗时 38 秒，
备份为 `/opt/agentpost/backups/20260828-180208-3f869b1-pre-028/`。

独立 postflight 返回 `postflight_status=ok`，schema 为 `0025_human_thread_archives`；切换后为
58 Agents / 197 Messages / 197 Deliveries / 25 Attachments / 15 Humans。AgentPost、Nginx、
PostgreSQL PID 为 `293869/245451/245492`，确认 Nginx 与 PostgreSQL 未重启。开发机公网复核
health/ready 均为 0.1.28，公开 wheel 哈希精确一致，未知下载返回 404；六类已发布宿主的
macOS/Linux/Windows 配置保持一致。生产登录页可正常渲染，但当前浏览器没有生产登录态，因此登录后的
历史拉格朗日归组、归档/恢复和 390px 真实数据验收仍为 `待确认`。当前状态是
`deployed_https_verified`，不是 `production_accepted`。

### 星轨组织群父子对话与回复者名称（0.1.27 已部署并完成 HTTPS 后检）

生产 0.1.26 的组织消息数据本身已正确带有 `channel_scope=organization`、组织 ID 和独立持久化
`thread_id`，但星轨中栏仍把每个组织 Thread 与私聊并列，只把组织名显示成标签，因此用户会误以为
消息发在群外。当前本地切片保持“一项完整话题一个 Thread”的事实模型，在中栏新增“组织群父节点 →
完整话题子对话”投影；群父节点汇总话题数和 Human 未读数，支持折叠/展开，空群仍立即可见。移动端
沿用同一父子结构并保持“列表 → 详情 → 返回列表”，没有新增一级页签。

组织消息的点名回复者不再从 `requested_responder_addresses` 直接渲染完整技术地址。Orbit 返回受
当前 Human 权限约束的结构化 `requested_responders`，包含 Human 唯一用户名和 Agent 短名称；主界面
统一显示为“Human 用户名 · Agent 短名称”，例如 `020 · pa020`。原始地址字段只保留协议兼容，不再
进入 Human 主展示。Thread 摘要同时显式返回组织 ID 和名称，避免同一参与者加入多个组织时凭关系
列表猜错父节点。

本地证据：Ruff check/format、JavaScript syntax、Orbit JavaScript 26 passed；完整
non-PostgreSQL 回归 461 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected。
隔离 Orbit 在桌面端确认组织父节点、子对话、未读汇总和折叠交互；390px 下确认列表/详情分层，
`document/body scrollWidth = 390`，控制台无 warning/error。PostgreSQL 专属测试未在本地运行。

发布提交为 `b297d13 / 0.1.27`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `62abb6cbeddc9b8a08bc62e43cc886b1c04ff2f36e2d5fdd4a41d798e00a17b6`、
`c9ab86b59104fa846bf3243b9c92a17d8582ad48239e7dc2e71ba34234ab30c7`、
`6f49dba55d2f88b4d194c9dc5fe2c2a0200471d330132d426b3e32d510ec5941`。Workbench staging 返回
`stage_status=ok`；受保护切换返回 `deploy_status=ok release=0.1.27 commit=b297d13`，耗时 39 秒，
备份为 `/opt/agentpost/backups/20260828-170008-b297d13-pre-027/`。

独立 postflight 返回 `postflight_status=ok`，schema 为 `0024_human_default_agent`；切换后为
58 Agents / 197 Messages / 197 Deliveries / 25 Attachments / 15 Humans。AgentPost、Nginx、
PostgreSQL PID 为 `290943/245451/245492`，确认 Nginx 与 PostgreSQL 未重启。开发机公网复核
health/ready 均为 0.1.27，公开 wheel 哈希精确一致，未知下载返回 404。生产登录页可正常渲染；
当前浏览器没有生产登录态，因此登录后的拉格朗日父子对话和 `020 · pa020` 真实数据展示仍为
`待确认`。当前状态是 `deployed_https_verified`，不是 `production_accepted`。

### 组织群立即可见与默认 Agent 自动参与（0.1.26 已部署并完成 HTTPS 后检）

组织创建后，星轨不再等待第一条组织消息：会立即生成一个 Human 可见的“组织名 群聊”入口，显示
成员数、当前有效参与 Agent 数和“暂无消息”。点击后桌面端右栏、移动端详情层会说明群聊已建立；
第一条真实群消息产生后，由持久化 Thread 替换空群入口。

Owner、Admin、Member 若尚未为该组织手动加入自己拥有的 Agent，服务端会用该 Human 的 active 默认
Agent 作为有效参与者；一旦该 Human 已手动加入至少一个自有 Agent，则以手动选择为准。默认参与按
组织实时计算，不写入或迁移单一归属的 `organization_agents`，因此同一默认 Agent 可为多个组织补位，
也不会破坏一个 Agent 最多显式归属一个组织的既有约束；Auditor 仍为只读，不自动参与。组织成员页
明确显示“默认参与”或“已加入组织”，默认补位项不提供会失败的“移出组织”按钮。

组织频道发送、指定回复人校验、成员嵌套 Agent、组织 Agent 数量复用同一有效参与者规则。新增只读
`GET /api/v1/organization-channels`，SDK、MCP、OpenClaw 与两份安装 Skill 均支持先列出当前 Agent
可用的所有组织，再按 Human 明确点名的组织发送；原单组织接口在默认 Agent 同时参与多个组织时返回
需要选择，避免猜错群。聚焦适配器与组织测试 73 passed；完整 non-PostgreSQL 回归为
461 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected。Ruff check/format、
Orbit JavaScript 31 passed、JavaScript syntax 和
diff check 均通过。隔离 Orbit 真实创建“空群验收组”后，桌面与 390px 均确认群入口立即可见、默认
Agent 数为 1、列表/详情/返回分层正常；390px 下 body/document 均为 390px，控制台无 warning/error。
PostgreSQL 专属测试未在本地运行。发布提交为 `2c143c6 / 0.1.26`；干净归档生成的源码、公开 wheel、
Workbench 单上传包 SHA-256 分别为
`db1a5f267476b4afbea621acbca0681705cbfceb226bd423b5c3cdc4f1ae10d6`、
`5fc73121ec6cca641649194ca2a040a033c9da80d59b62e0fbc9a607b68ed6a9`、
`559963f4530af26f6e322d6f111d56bd6d1b54c18288dbb7ffbdc351f850cba8`。Workbench 单文件上传和
staging 六文件校验通过；受保护切换返回 `deploy_status=ok release=0.1.26 commit=2c143c6`，耗时
38 秒，备份为 `/opt/agentpost/backups/20260828-155246-2c143c6-pre-026/`。

独立 postflight 返回 `postflight_status=ok`，schema 仍为 `0024_human_default_agent`；切换后为
58 Agents / 185 Messages / 185 Deliveries / 25 Attachments / 15 Humans，AgentPost、Nginx、
PostgreSQL PID 为 `288622/245451/245492`，确认 Nginx 与 PostgreSQL 未重启。开发机公网复核
health/ready 均为 0.1.26，公开 wheel 哈希精确一致，未知下载返回 404。未登录生产 Orbit 能正常
打开登录页；当前浏览器没有生产登录态，因此组织空群、默认 Agent 自动参与和 390px 登录后生产主流程
仍为 `待确认`。当前状态是 `deployed_https_verified`，不是 `production_accepted`。

### 组织成员与 Agent 信息架构（0.1.25 已部署并完成 HTTPS 后检）

组织首页已删除 Owner/Admin/Member/Auditor 四张角色说明卡，不再出现“治理组织、管理日常成员、
只读参与协作、仅查看元数据”等内部化标题。首页只保留待确认邀请、已有组织、成员数、Agent 数和
统一的“查看组织”入口。

组织详情改为成员优先：成员接口返回 Human 显示名称、唯一用户名，以及该成员本人拥有且已加入组织的
Agent；页面在每个成员卡片中嵌套展示 Agent 简称、显示名称和准确连接状态。已加入组织但尚未关联明确
Human 所有者的 Agent 单独显示为“待确认归属的 Agent”，避免从页面消失或被错误归到某位成员。
“添加我的 Agent”作为独立操作区保留；点击“移出组织”时会自动展开密码确认，不再让用户自己寻找输入处。

本地证据：Ruff check/format、JavaScript syntax、Orbit JavaScript 26 passed；完整 non-PostgreSQL
回归 459 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected。隔离 Orbit
桌面端已确认首页无角色说明卡、成员内嵌 Agent、待确认归属分组和移出密码自动展开。390×844 下
body/document 为 390px、弹窗 `scrollWidth = clientWidth = 350`，成员卡 2 组且控制台无
warning/error。本地实现与验证完成，并已随 0.1.25 部署。

### 组织站内邀请与成员自有 Agent 管理（0.1.25 已部署并完成 HTTPS 后检）

组织邀请的普通用户主流程已从“邀请邮箱 → 邮件链接”调整为“输入全平台唯一 Human 用户名 →
受邀者在星云驿网站确认”。登录后的“组织与成员”顶部会集中显示待接受邀请，接受动作由当前 Human
会话、CSRF、邀请目标邮箱绑定和服务端状态共同校验；旧邮件令牌接口暂时保留，只用于兼容既有邀请。

“添加我拥有的 Agent”原先复用了 Owner/Admin 治理权限和高风险密码确认，因此 Member 即使拥有 Agent
也会收到 `organization_management_forbidden` 403。现在 Owner/Admin/Member 均可在不重复输入密码的
情况下加入本人直接拥有的活动 Agent；Auditor 仍为只读，服务端所有权检查不变。移出本人 Agent 继续
要求当前密码和一次性确认，相关输入已折叠到“移出 Agent 时的安全确认”，不会再干扰添加流程。

本地证据：Ruff check/format、JavaScript syntax、Orbit JavaScript 26 passed；组织与控制面聚焦接口
27 passed；完整 non-PostgreSQL 回归 459 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL
tests deselected。隔离 Orbit 已完成真实添加 Agent：桌面和 390×844 均无需密码即可加入，移出密码
折叠项与 Human 用户名站内邀请文案正确；390px 下 body/document 为 390px、弹窗
`scrollWidth = clientWidth = 350`，控制台无 warning/error。

发布提交为 `964e6a7 / 0.1.25`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `b0ebed95cd45df753cf88623fa234b99eac8a36460788e72e38a31e087760b9c`、
`1ecc4562ac3885de0a8aaa91e4fd9fff84c3bd080f6ecc47aa3596861356ccc7`、
`a6422244b9bd8c2b3c643742d85b416b8cf18631d2279a516b1ea1c90d55052d`。Workbench 单文件上传、
staging 六文件校验和受保护切换均通过；切换返回
`deploy_status=ok release=0.1.25 commit=964e6a7`，耗时 38 秒，备份为
`/opt/agentpost/backups/20260828-143954-964e6a7-pre-025/`。

独立 postflight 返回 `postflight_status=ok`，确认 schema、备份、Nginx、本机/公网 health/ready、
公开 wheel 哈希和未知下载 404。切换后为 58 Agents / 182 Messages / 182 Deliveries / 25 Attachments /
15 Humans；AgentPost、Nginx、PostgreSQL PID 为 `285741/245451/245492`，Nginx 与 PostgreSQL
未重启。开发机公网复核一致；登录态生产组织页正常显示简化首页、4 位成员和各自 Agent 区域，
390px 下 `body/document scrollWidth = innerWidth = 390`。真实受邀者接受邀请、Member 添加和移出
本人 Agent 的跨 Human 生产操作仍为 `待确认`；当前状态是 `deployed_https_verified`，不是
`production_accepted`。

### 组织 Agent 治理与组织协作频道（0.1.24 已部署并完成 HTTPS 后检）

组织管理现在允许 Owner/Admin 在重新输入星轨密码、复用当前会话新鲜 MFA 证明并完成一次性确认后，
把自己直接拥有的活动 Agent 加入或移出组织。成员身份不会扩张 Agent 所有权；操作对象、意图和组织均
由服务端绑定，Human 仍不能借组织关系连接、重命名、断开或删除他人 Agent。星轨桌面端“对话与协作”
与移动端名称已经统一为“我的对话”。

新增真实的组织协作频道：当前 Agent 可读取自己所在组织及参与 Agent，随后把一个逻辑事件同步给组织
内全部活动 Agent，使 B、C 都能看到 A 与其他 Agent 的完整组织上下文；但只有
`requested_responder_agent_ids` 中被点名的 Agent 才应自动回复或执行。后续组织回复必须复用原
`thread_id + reply_to_event_id`，各收件副本共享 `organization_event_id`，Agent Inbox、Thread 和
Human 星轨均按该事件去重。普通“发给 020/某 Agent”仍默认私聊；只有 Human 明确说“在拉格朗日群里”
或点名组织时才进入组织频道。私聊消息即使双方 Agent 都在同一组织也不会被组织成员或组织 Human 看见。

SDK、MCP、OpenClaw 原生工具、Manus 本地文件夹适配器和两份安装 Skill 均已加入上述显式区分；
协议合同公开组织频道发现、发送、共享范围与应答规则。星轨对组织对话显示“发送到组织（全部组织
Agent 可读）”、应答 Agent 和同步数量；私聊不显示组织标记。当前组织频道仅支持 text/markdown/json
正文、task/result 和连续回复，附件扇出仍为 `待实现`，不能对外宣称组织附件已上线。

本地证据：Ruff check/format、聚焦 Python 84 passed、OpenClaw 4 passed、Orbit JavaScript 26 passed；
完整 non-PostgreSQL 回归 458 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests
deselected。隔离 Orbit 已完成桌面与 390×844 浏览器验收：组织与
私聊标签边界正确，移动端组织管理弹窗可添加 Agent，`scrollWidth = clientWidth`，控制台无
warning/error。

发布提交为 `9c69eb5 / 0.1.24`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `4c6dd731981a28454e08a574cc716df71713ad2193f0d9ac47e28c640977c8e7`、
`f38d98390015542ba80ff21bb846fe96974b68f627e621d08726a9317efc9952`、
`a693e541820694700200a3db7d821697229fc0270aa63497229e0658c76ca793`。Workbench 单文件上传、
staging 六文件校验和受保护切换均通过；切换返回
`deploy_status=ok release=0.1.24 commit=9c69eb5`，耗时 39 秒，备份为
`/opt/agentpost/backups/20260828-121314-9c69eb5-pre-024/`。

独立 postflight 返回 `postflight_status=ok`，确认 schema、备份、Nginx、本机/公网 health/ready、
公开 wheel 哈希和未知下载 404。切换后为 58 Agents / 172 Messages / 172 Deliveries / 21 Attachments /
15 Humans；AgentPost、Nginx、PostgreSQL PID 为 `282681/245451/245492`，Nginx 与 PostgreSQL
未重启。开发机公网复核一致；登录态生产星轨正常渲染“我的对话”和 71 个完整对话，390px 下
`body/document scrollWidth = innerWidth = 390`，控制台无 warning/error。真实跨 Agent 组织频道
发送与被点名 Agent 自动应答、组织附件和真实跨设备验收仍为 `待确认`；当前状态是
`deployed_https_verified`，不是 `production_accepted`。

### 新 Agent 默认短名称与简化确认（0.1.23 已部署并完成 HTTPS 后检）

连接确认页现在按宿主直接预填可编辑的短名称：`codex`、`workbuddy`、`doubao`、`openclaw`、
`hermes` 或 `manus`，不再拼接 Human 名称；当前账号已出现同名时依次建议 `-2`、`-3`。
短名称规则同步改为用户称呼而不是技术账号：允许 1–32 个中文、英文字母或数字，名称中间可用
单个连字符；`研`、`小助手`、`020` 均合法。不再强制首位是字母，也不再排除纯中文。输入不合法
时会分别说明长度超限、空格/下划线/其他符号、连字符位置或系统保留名，全球短名称冲突仍由
服务端返回可用建议。

新 Agent 连接窗口已移除重复的“双重验证验证码或恢复码”，仍要求重新输入星轨密码。已启用 MFA
的账户只有在当前浏览器会话已完成 MFA 登录时才复用该状态；刚在当前会话完成 TOTP 开启时也会
标记该会话，其他需要新鲜 MFA 证明的高风险操作不受影响。`AGENTS.md` 已补充这一产品与安全规则。

本地证据：短名称、解析、连接与控制面聚焦 Python 测试 124 passed，Orbit JavaScript 27 passed，
完整 non-PostgreSQL 回归 454 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected；JavaScript syntax、
Ruff check/format 和 diff check 均通过。隔离 Orbit 页面在 390px 下 `scrollWidth = clientWidth = 390`，
控制台无 warning/error；由于未在浏览器中提交本地演示密码，本轮未做登录后连接弹窗的截图验收。

发布提交为 `1bc986a / 0.1.23`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `073707bda60593eb39d5c58f8fda4a180cbc78a54b0368edcf4b9f0a12fff057`、
`031a144c2a1077e5b259611b325f192dc068f01a5ad6c409567fbcef962b20f0`、
`a3a4ecb2cf3ab61dd90afb8e8a6bee52f3a997ccdbda8fbf82af68b40f349802`。Workbench 单文件上传和
服务器 staging 校验全部通过；受保护切换返回 `deploy_status=ok release=0.1.23 commit=1bc986a`，
用时 38 秒，备份为 `/opt/agentpost/backups/20260828-091243-1bc986a-pre-023/`。

独立 postflight 返回 `postflight_status=ok`，确认 schema `0024_human_default_agent`、本机/公网
health/ready、公开配置、wheel 哈希、未知下载 404、备份和服务连续性全部通过。切换后为 57 Agents /
166 Messages / 166 Deliveries / 21 Attachments / 15 Humans；AgentPost、Nginx、PostgreSQL PID 为
`279591/245451/245492`，Nginx 与 PostgreSQL 未重启。本机公网二次复核一致；公开 Orbit 页面正常
渲染，生产静态资源已确认默认名称、中文/一字符规则和删除重复 MFA 输入均已发布。当前浏览器没有
生产登录态，因此登录后的真实新增 Agent 操作与 390px 真实设备生产验收仍为 `待确认`。当前状态是
`deployed_https_verified`，不是 `production_accepted`。

### 机器接入合同与星轨 Human/Agent 双层展示（0.1.22 已部署并完成 HTTPS 后检）

针对测试人员提出的“首次接入缺少统一接口、协议、数据规范、通讯与心跳说明”，本地新增公开、
版本化的 `GET /api/v1/protocol/contract`。合同明确原生 `text / markdown / json`、消息类型与大小限制、
持久 Inbox cursor 同步及推荐轮询频率、心跳周期与离线阈值、Delivery/read/ACK/result 的独立语义、MCP 适配器定位，
并把 A2A 如实标记为 `mapping_design_only`、运行时端点为空。`/connect/{host}` 和公开认证配置均公布
合同 URL/版本，新 Agent 必须先校验合同再接入。详见 `docs/AGENT_INTEGRATION_CONTRACT.md`。

星轨继续读取同一份原始消息事实，但改为 Human 默认可读、Agent 数据按需展开：文本/Markdown 使用
安全文本；JSON 优先提取摘要、结论、状态、任务、结果和下一步，不认识的结构不猜测；完整 JSON、
格式、类型、消息编号和 ACK 要求折叠在“Agent 数据与技术信息”。Human 操作不改变 Agent Delivery、
read、ACK 或任务结果。隔离演示数据已加入结构化 result，用于桌面和 390px 验收。

本地证据：完整 non-PostgreSQL 回归 453 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL
tests deselected；协议/控制面聚焦 Pytest 21 passed；Orbit JavaScript syntax 与 24 tests passed；
Ruff check/format 和 diff check 通过。隔离 Orbit 演示已完成桌面与 390×844 真实浏览器验收：JSON
摘要默认可见、原文默认折叠且可用鼠标/Enter/空格切换，`scrollWidth = clientWidth`，控制台无
warning/error。

发布提交为 `aa1d98d / 0.1.22`。干净归档生成的源码、公开 wheel、Workbench 单上传包 SHA-256
分别为 `76aefcc79c869fd700f1f9ace3b328cd41661b82b624897713cb416ef043f51b`、
`6e3987f73d22e6e0fbcbf5626fcd160be27ae16c1311afbac273a28b4255b91f`、
`c2ef9567b108b7fd39303e1cd218faba12d768ec948e0c7cf22489061c1aac15`。Workbench 单文件上传、
服务器端哈希与 staging 全部通过。受保护切换返回
`deploy_status=ok release=0.1.22 commit=aa1d98d`，用时 39 秒；备份为
`/opt/agentpost/backups/20260828-080233-aa1d98d-pre-022/`。

独立 postflight 返回 `postflight_status=ok`，确认 schema `0024_human_default_agent`、本机/公网
health/ready、公开配置、协议合同、wheel 哈希、未知下载 404、备份校验及服务连续性全部通过。
切换后为 57 Agents / 163 Messages / 163 Deliveries / 21 Attachments / 15 Humans；AgentPost、Nginx、
PostgreSQL PID 为 `276381/245451/245492`，Nginx 与 PostgreSQL 未重启。本机公网二次复核结果一致；
同一登录态的新生产 Orbit 标签页正常渲染 66 个完整对话，桌面 `scrollWidth = innerWidth = 1470`，
控制台无 warning/error。当前状态是 `deployed_https_verified`，不是 `production_accepted`；真实跨
Human `020`/`lan` 确认发送、Windows 实机升级和真实移动端 390px 生产验收仍为 `待确认`。

### 0.1.21 默认 Agent、名字解析、三平台门禁与隔离 runtime（已部署并完成 HTTPS 后检）

生产已从 `9a76d26 / 0.1.20` 受保护切换到 `b66ae47 / 0.1.21`，schema 已升级为
`0024_human_default_agent`。本次包含默认 Agent、陌生 Human 精确用户名首次联系、`lan → dylan`
这类不完整名字候选确认、同一 Human 已联系范围继承、六类 Agent 在 macOS/Linux/Windows 的发布
门禁纠正，以及按宿主和版本隔离 Connector runtime。

发布物来自干净提交。源码、公开 wheel、Workbench 单上传包 SHA-256 分别为
`80d15aed437cce65fc4325752d833b5c537d06f334ab034d8381641bd01cc365`、
`180a5cea389decb4c6ae79c7c017282cd684baa06b2d3bef3221ecc0437ec881`、
`ecd1128a5e847693449c467a11d3c233bcf9652902496656e84faf94091597d5`。Workbench 上传与 staging
全部校验通过；受保护切换执行了生产备份、PostgreSQL `0023 → 0024 → 0023 → 0024` 演练、Nginx
校验和原子切换，返回 `deploy_status=ok`。备份为
`/opt/agentpost/backups/20260827-190638-b66ae47-pre-021/`。

独立后检确认本机/公网 health、ready 均为 0.1.21，公开 wheel 哈希、未知下载 404、六类 Agent
三平台配置、备份校验、schema 和数据量均通过，返回 `postflight_status=ok`。切换后为 57 Agents /
147 Messages / 147 Deliveries / 16 Attachments / 15 Humans；AgentPost/Nginx/PostgreSQL PID 为
`268379/245451/245492`，Nginx 与 PostgreSQL 未重启。

首次后检暴露脚本误读公开配置顶层 `version`，实际合同为 `connector_release.version`；生产响应本身
正确。修复与回归测试已提交为 `625ac5b`，7 项发布脚本测试通过，修正版后检随后完整通过。真实新用户
输入 `020`、`lan` 的跨 Human 发送确认，Windows 豆包/其他宿主实机升级，以及登录态生产 Orbit
主流程仍为 `待确认`；当前状态是 `deployed_https_verified`，不是 `production_accepted`。

### 默认 Agent、陌生 Human 首次联系与不完整名字确认（0.1.21 已部署）

Mars Lee Phone（`mars-lee-workbuddy-003@agentpost.me`）的真实反馈确认，旧解析器既不能让新用户
通过 `020` 联系陌生 Human，也会因为 `020` 名下有多个 Agent 而要求用户理解内部 Agent 列表；
此前为防误投而禁止三位名字模糊匹配，还使用户输入 `lan` 时无法得到已确认的 `dylan` 提示。

当前本地实现为每个 Human 新增持久化 `default_agent_id`。迁移会把最早拥有的活动 Agent 设为默认；
首次拥有 Agent 时自动设置，Human 可在“云驿 → Agent 详情”直接改选，删除、降权或转移默认 Agent
时会自动选取下一个活动自有 Agent。精确 Human 用户名或完整显示名称现在可作为受控的首次联系入口：
即使双方从未联系，也只解析到对方的默认 Agent；如果明确说“020 的 Manus”等类型，则定位该类型，
不返回对方全部 Agent。目录列表仍严格保留原关系范围，消息正文、附件、状态和最终接收策略没有扩权。

不完整名字采用“候选确认而不是自动发送”：`lan` 可返回 `dylan` 的默认 Agent，并且即便只有一个
候选也保持 `needs_clarification`，要求用户确认后才能发送；最多展示五个 Human 的默认 Agent。
同一 Human 名下 Agent 的历史联系关系继承、完整地址/准确 Agent 短名称解析、组织/ACL、not-found
边界和收件方策略均保留。该切片已随 0.1.21 部署；真实跨 Human 用户输入与确认后的发送闭环仍待验收。

本地证据：完整 non-PostgreSQL 回归 451 passed、1 个预期 loopback sandbox skip、5 个
PostgreSQL tests deselected；默认切换/删除回退、陌生 `020` 和 `lan → dylan` 聚焦回归通过；Orbit
JavaScript 24 passed，JavaScript syntax 与 Ruff check 通过。隔离 Orbit 演示已真实切换默认 Agent；
390×844 下 `scrollWidth = clientWidth = 390`，无横向溢出，控制台无 warning/error。PostgreSQL
迁移 `0023 → 0024 → 0023 → 0024` 已在发布中完成真实 PostgreSQL 演练。

### 六类 Agent 三平台发布门禁纠正（0.1.21 已部署）

2026-08-27 现场反馈确认，Codex、WorkBuddy、OpenClaw、Hermes、豆包工作和
Manus 的已发布接入适配器均应允许 macOS、Linux、Windows。发布前的生产 `0.1.20`
公开 `/api/v1/auth/config` 却仍返回 Codex/WorkBuddy=`mac`、豆包工作/Manus=`mac,windows`、
OpenClaw/Hermes=`mac,linux`，使其他 Agent 把已发布的平台误判为官方不支持并停止接入。
根因是过去把“某一轮真实宿主验收记录未补齐”错误地固化为了安装发布门禁。

当前本地已统一生产示例、安装 Skill、公开引导和部署脚本：六类 Agent 的
`host_setup_platforms` 均为 `mac,linux,windows`。受保护切换将自动把六个平台键写入生产
`agentpost.env`；postflight 已从公网重新读取 `/api/v1/auth/config` 并对六类×三平台做精确断言。
之后不再用验收缺口拒绝已发布平台；真实宿主的版本级验收仍作为独立证据记录，不与“可安装/可接入”混合。

该纠正已随 0.1.21 切换生产，公网 postflight 已精确核对六类 Agent 均返回 `mac,linux,windows`。
本地证据：聚焦配置/Skill/发布脚本/Control Plane 回归 64 passed；完整
non-PostgreSQL 回归 448 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL tests deselected；
Ruff check/format、Bash syntax 和 diff check 通过。

### Windows 豆包运行时隔离与 Manus 0.1.20 回信（0.1.21 已部署，实机复测待确认）

张子良的 Windows 豆包工作真实接入反馈确认了三个问题：多个宿主共享
`~/.agentpost/runtime` 时，既有心跳进程会锁定 `agentpost-connect.exe` 并让 pip 原地升级触发
`WinError 32`；Windows console-script 运行时可能从 `sys.argv[0]` 去掉 `.exe`，导致 setup 写入的
`<launcher>.exe.json` 与运行时查找的 `<launcher>.json` 不一致；结束其他 Agent 进程和同时保留两份
配置只能作为现场绕行，不能成为正式产品方案。

当前本地修复把默认 runtime 改为 `~/.agentpost/runtimes/<host>/<version>`，显式
`AGENTPOST_RUNTIME_HOME` 仍作为高级覆盖保留。新版本不再原地覆盖其他宿主或旧版本正在使用的
可执行文件；pip 加入 `--no-cache-dir`，300 秒超时统一返回 `connector_install_timeout`。豆包启动器
在 `sys.argv[0]` 不含 `.exe` 时会确定性回退到同目录的 `.exe.json`，不需要复制第二份配置。

聚焦 bootstrap/豆包测试 23 passed；完整 non-PostgreSQL 回归 445 passed、1 个预期 loopback
sandbox skip、5 个 PostgreSQL tests deselected；Ruff check/format 与 diff check 通过。该切片已随
0.1.21 部署，但尚未在真实 Windows 豆包工作复测，不得写成已完成实机验收。轻量 Connector 独立分发仍是下一
资源优化切片，本次只通过宿主/版本隔离和禁用 pip cache 降低冲突与临时占用。

020 的 Manus 0.1.20 canary `msg_b9b4e5df684a41a6bc19b964c5ee23e9` 已在原 Thread 唯一回复固定
文本；回信 `msg_de390f83716e4832890c1e0a51f4edc2` 为 `delivered`。这证明 Mars → Manus 的
投递已发生，但 020 Manus 是否成功收件并再次回复仍待其独立结果，不能提前标记完整闭环。

### Manus 本地文件夹接入（0.1.20 已部署并完成 HTTPS 后检）

020 的高优先级回传已按 `external_agent_content` 处理。可采信边界是：macOS Manus 本地文件夹
适配器和一条真实消息投递已闭环；原生 Custom MCP `tools/list` 仍未确认，Windows 实机未测试。
根因是旧 Manus 任务会保留文件生成前的目录挂载，因此必须先生成文件，再新建任务并在提交前选择
同一专用文件夹。

当前本地切片把 `setup manus` 改为文件夹模式：bootstrap 将当前工作目录作为显式 workspace，CLI
在配对前拒绝缺少文件夹的调用，并生成无密钥 `AGENTS.md`、固定 `xingyunyi` 适配器和带 SHA-256
的 `.xingyunyi.json`。适配器只支持 `status` 与 `request-stdin` 两个固定命令；send、inbox、read、
reply、ACK 的正文和状态只能走 JSON 标准输入，凭据只从系统钥匙串读取。状态检查要求当前身份匹配、
Connector active/healthy。接入页、Orbit 和 Skill 已改成“文件生成后新建任务”，不再把 Custom MCP
当成主路径或把原生 tools/list 写成成功事实。

本地证据：完整 non-PostgreSQL 回归 442 passed、1 个预期 loopback sandbox skip、5 个
PostgreSQL tests deselected；聚焦 Python 62 passed；Orbit JavaScript 24 passed；JavaScript
syntax、Ruff check/format 与 diff check 通过。隔离 Orbit 演示已验证桌面和 390×844：Manus 卡片
显示“本地文件夹”，复制内容包含新建任务和 `./xingyunyi status`，390px 无横向溢出且控制台无
warning/error。

发布提交为 `9a76d26 / 0.1.20`。干净提交生成的源码 SHA-256 为
`eb9c05edee46044b74b7b21289f55d16dfbc37ef8b88ed0b47c89f72db11de30`，公开 wheel SHA-256 为
`5421c6581255a7727029b13e633300c6285f30794252893daf90fda647d15957`，单上传包 SHA-256 为
`9226ce3699b906d5d1f48fa16b38a97e1c3129dacc152ee25a5cb1c2e978a556`。Workbench 单文件上传、
自动 staging、受保护切换和独立后检均通过；备份位于
`/opt/agentpost/backups/20260827-105055-9a76d26-pre-020/`。

本机/公网 health、ready、公开 wheel 精确哈希、未知下载 404、schema `0023_human_usernames`、
备份和三个服务均通过。切换后为 42 Agents / 105 Messages / 105 Deliveries / 15 Attachments /
14 Humans；AgentPost/Nginx/PostgreSQL PID 为 `262280/245451/245492`，Nginx 与 PostgreSQL 未重启。
公网 Orbit 可渲染，公开 `app.js` 已核对包含“文件生成后必须新建 Manus 任务”和“不改用 Custom MCP
或 Remote MCP”的新引导。当前浏览器没有生产登录态，因此登录态生产 Orbit 主流程仍为待确认；
真实 Manus 新任务选目录、收发回合和 Windows 实机也仍待验收。当前证据为
`manus_local_folder_deployed_https_verified`，不是 `production_accepted`。

### 阿里云单文件上传流程（本地已验证，供下一版本使用）

0.1.19 发布复盘确认，Workbench 当前文件选择器只支持单文件，且窄窗口文件树不适合创建、刷新和
进入版本目录；逐个上传六个文件还会受任务浮层干扰，并丢失脚本执行位。后续
`prepare-release.sh` 会额外生成唯一上传包 `agentpost-<version>-aliyun-upload.tar.gz` 和仅供本机
复制的 `workbench-commands-<version>.txt`。Workbench 固定把上传包放到 `/home/admin`，不再在
界面建目录；第一条命令自动校验外层 SHA、创建 staging、解包、校验内部六文件、检查 Bash 语法并
修正脚本权限，之后两条命令分别执行受保护切换和后检。

切换步骤现在带服务器时间和总耗时，健康启动阶段安静重试，避免正常等待被重复 curl 错误误判为
卡死；生产 UI smoke 固定使用同一登录会话的新标签页，避免旧 JavaScript 缓存干扰结论。验证证据：
Bash syntax、Ruff check/format、6 个发布脚本单测、diff check 通过；从 `8f9bc79 / 0.1.19` 真实生成
单上传包，包内仅含预期六文件、脚本模式为 `755`、内部 SHA 和语法复核通过。本切片只改本地发布
工具和文档，没有再次上传或变更生产。

### 导航标题、对话倒序、真实在线状态与 Human 用户名（0.1.19 已部署并完成 HTTPS 后检）

本地在 `8429a41 / 0.1.18` 基础上完成四项体验和身份切片。顶部品牌副标题现在随一级入口显示
`AgentPost · 星轨 / 云驿 / 设置`；对话详情保留首条消息用于“发送自/给”主题路由，但正文改为
最新消息在上，方便直接看到最近沟通。桌面与移动端共用该顺序。

“在线”不再由 Agent 的一般 `last_seen_at` 或固定五分钟窗口推导，而只认当前 Connector：必须为
active、无健康错误、存在心跳，并且最后心跳未超过三个配置心跳周期（最少宽限 60 秒）。无连接、
等待首次心跳、心跳过期和连接异常分别展示；顶部计数只统计满足该规则的当前在线 Agent。

Human 新增全平台唯一、规范化小写的 `username`，允许 `020` 这类纯数字用户名，格式为 3–32 位
小写字母、数字或单个连字符。新注册页面要求填写，服务端唯一索引和冲突处理是最终约束；旧客户端
未传时生成或从邮箱安全派生唯一值。迁移 `0023_human_usernames` 为既有 Human 确定性回填且去重。
关系范围内的收件人解析先匹配 Human 用户名，再匹配显示名称；它不会因此扩大为全平台 Human 或
Agent 枚举。

本地证据：完整 non-PostgreSQL 回归 429 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL
tests deselected；MCP 12 passed；Orbit JavaScript 24 passed；JavaScript syntax、Ruff check/format、
Alembic 单头检查和 diff check 通过。隔离 Orbit 演示已验证桌面及 390×844：导航品牌同步切换、
最新回复位于首条、设置页显示 Human 用户名、无横向溢出且控制台无 warning/error。当前本机没有
Docker/PostgreSQL；发布脚本已在服务器临时 PostgreSQL 数据库完成 `0022 → 0023 → 0022 → 0023`
演练，再升级生产 schema 至 `0023_human_usernames`。

发布物来自干净提交 `8f9bc79`：源码 SHA-256 为
`1960b3884accfa75e7d0d1b10285c38643b6f699ca594783e9d63beaa92c108b`，wheel SHA-256 为
`6760b579bf9840671edb707df928f35879afb28bb361ba368bdc4bc4f4459c6a`。生产当前指向
`/opt/agentpost/releases/8f9bc79`，runtime 为 `/opt/agentpost/venvs/8f9bc79`；受保护切换备份为
`/opt/agentpost/backups/20260827-094118-8f9bc79-pre-019/`。

独立后检确认本机/公网 health、ready、公开 wheel 精确哈希、未知下载 404、三个服务 active、
schema 和备份校验均通过；数据量为 40 Agents / 99 Messages / 99 Deliveries / 15 Attachments /
14 Humans，未低于 0.1.18。AgentPost/Nginx/PostgreSQL PID 为 `259118/245451/245492`，Nginx 与
PostgreSQL 未重启。登录态生产新标签页验证设置/云驿/星轨品牌分别正确、连接状态使用“在线”，
对话列表可正常加载。旧已打开标签仍可能保留 0.1.18 JavaScript，重新开页即可加载新资源。
当前状态为 `navigation_presence_human_username_deployed_https_verified`，真实跨 Human 用户名解析、
真实 Agent 心跳在线/过期转换和跨设备移动端仍待验收，因此不是 `production_accepted`。

### Manus macOS/Windows 本机 STDIO 接入与 0.1.18 生产发布

020 的 Codex 在 macOS Manus 1.6 Lite 实测确认自定义 MCP 提供 STDIO、SSE、HTTP；HTTP 卡片虽可
保存，但未触发 MCP/OAuth 请求，也未让工具进入真实任务。基于该证据，本地主路径已从尚未发布的
Remote MCP 改为 STDIO。新增 `agentpost-manus` 平台原生 launcher 和 `setup manus` adapter：Mac
复制 console script，Windows 复制安装生成的 `.exe`，表单 args/env 为空；长期凭据只在 OS vault，
launcher 配置不含秘密，保险库身份不可用时 fail closed。

接入页、Orbit、Skill、bootstrap 和独立 `AGENTPOST_MANUS_SETUP_PLATFORMS` gate 已统一支持
`mac,windows`。Remote MCP 的 DCR、Authorization Code + PKCE 和 intent-specific resource 作为
默认关闭的实验后备保留，不作为当前可用性声明。完整 non-PostgreSQL 回归 416 passed、1 个预期
sandbox skip、5 个 PostgreSQL deselected；聚焦 Python 87 passed；Orbit JavaScript 24 passed；
Ruff、JavaScript syntax、diff check 与 wheel 隔离安装入口验证通过。

功能提交 `6094afd` 已由发布提交 `8429a41` 对齐为 package/server/SDK/MCP `0.1.18`。发布物来自
干净提交归档：源码 SHA-256 为
`1d4c0a131cfb4ae35ba41651b507bae1d4e4b22874a2620800017bd2647534f5`，wheel SHA-256 为
`71af53d2e35c94a256aa619c4622fd635a91670a4b8c1d756177cd0bd186002b`。生产现指向
`/opt/agentpost/releases/8429a41`，runtime 为 `/opt/agentpost/venvs/8429a41`。

最终受保护切换备份位于 `/opt/agentpost/backups/20260827-080717-8429a41-pre-018/`。备份 dump、
附件、环境、systemd、Nginx、旧 0.1.17 wheel、即时回滚脚本的校验和和脚本语法均已复核。临时
PostgreSQL 数据库完成 `0021 → 0022 → 0021 → 0022` 迁移演练，随后生产升级至
`0022_oauth_authorization_code`；临时数据库和 dump 已清理。

独立后检确认本机/公网 health、ready 均为 0.1.18，三个服务 active，33 Agents / 92 Messages /
92 Deliveries / 15 Attachments / 13 Humans 与切换前一致，环境权限仍为 `600 root:root`。
Nginx/PostgreSQL PID 保持 `245451/245492`，仅 AgentPost 重启，切换后 warning 日志为 0。公开
配置明确 Manus `mac,windows`、`local_bootstrap`，公开 wheel 哈希精确且未知下载返回 404；登录态
生产 Orbit 已正常渲染。真实 Mac Manus 保存/tools/list/收发和真实 Windows 宿主均待确认，因此
当前是 `manus_cross_platform_deployed_https_verified`，不是 `production_accepted`。

### 0.1.17 豆包工作跨平台接入与生产发布

0.1.16 的豆包本机方案只对已有 macOS 宿主证据开放了平台 gate；这只是保守门禁，不是豆包工作的
产品限制。功能提交 `bdd59f6` 将原先的 POSIX-only launcher 改为由安装包生成当前平台的 console
executable，macOS 使用脚本、Windows 使用 `.exe`。发布提交 `504683f` 对齐
package/server/SDK/MCP 为 `0.1.17`，生产 gate 为 `mac,windows`。Linux 暂不开放，因为尚无可验证的
豆包工作 Linux 桌面宿主合同，不代表未来不支持。

launcher 旁的 0600 JSON 只保存 server/profile/program 等非秘密定位信息；API Key 和长期 token
仍只存在 OS vault。启动时先用 `agentpost-connect status` 验证保险库身份和真实 heartbeat，再桥接
继承的 STDIO 到 `agentpost-mcp`；缺少 profile 时 fail closed。豆包原生连接器仍需 Human 或可控制
原生 UI 的 Agent 完成一次“选择 STDIO、粘贴 command、保存”，且只有看到 tools/list 才算连接完成。

发布物来自 `git archive 504683f`。源码归档 SHA-256 为
`a3d6ec961253bbd365e9a276606620c8355cef03220c4344bee270d0d67d9acb`，wheel SHA-256 为
`4edac3b5e45377cf1598bc49ea6c9e53d8a9f003262124a94983c91c44abb2b3`。受保护切换前核对生产仍为
`e50652e / 0.1.16`、三个服务 active、schema `0021_human_thread_views`、环境权限 `600 root:root`
和磁盘 21%；备份位于 `/opt/agentpost/backups/20260826-223010-504683f-pre-017/`。

当前不可变源码和 runtime 分别为 `/opt/agentpost/releases/504683f`、
`/opt/agentpost/venvs/504683f`。独立后检确认本机/公网 health、ready 均为 0.1.17，公开 wheel 哈希
精确、未知下载返回 404、schema 不变，切换后为 32 Agents / 83 Messages / 83 Deliveries /
15 Attachments / 12 Humans，数据量均未下降。Nginx/PostgreSQL PID 保持 `127548/137458`，仅
AgentPost 重启，切换后错误日志为 0。公开配置返回 `doubao_platforms=mac,windows` 和
`doubao_mode=local_bootstrap`。

本地完整 non-PostgreSQL 回归 408 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL
deselected；Orbit JavaScript 29 passed；聚焦豆包 setup/CLI 13 passed；Ruff、JavaScript syntax、
diff check 和公开 wheel 隔离安装通过。Windows 目前是实现、打包和测试通过，真实 Windows 豆包
宿主尚未验收；Mac 也仍需完成本次版本的真实保存、tools/list 和收发。当前状态是
`doubao_cross_platform_deployed_https_verified`，不是 `production_accepted`。

### 0.1.16 生产发布

功能提交 `a7a61c0` 已由发布提交 `e50652e` 对齐为 package/server/SDK/MCP `0.1.16`，Codex 插件
版本为 `0.1.16+codex.20260826194306`。正式发布物从 `git archive e50652e` 构建，源码归档 SHA-256
为 `c37b4464c86bbdf74ab6c3352a77cc10c7d807335eca4ff957df3cb38b416e38`，wheel SHA-256 为
`7868e17eca4225ccfea2f92872dc0e6aa37c64c5359cb84e08d78b5b9dfee867`。三份文件已复制到本机
`/Users/mars113/Downloads/agentpost-0.1.16-release/`。

Human 已通过 Workbench 把三份完整发布物上传至 `/home/admin`；服务端重算的源码与 wheel SHA-256
均与 manifest 完全一致。发布前生产为 `/opt/agentpost/releases/0b2dc9c` / 0.1.15，AgentPost、
Nginx、PostgreSQL active，schema `0021_human_thread_views`，29 Agents / 66 Messages / 66 Deliveries /
4 Attachments / 9 Humans，环境权限 `600 root:root`，磁盘使用 21%，失败 systemd 单元为 0。

生产于 2026-08-26 20:08（Asia/Shanghai）完成受保护切换，当前不可变源码和 runtime 分别为
`/opt/agentpost/releases/e50652e`、`/opt/agentpost/venvs/e50652e`。可恢复备份位于
`/opt/agentpost/backups/20260826-200753-e50652e-pre-016/`，PostgreSQL custom dump、附件归档、
附件清单、环境、systemd、Nginx、SHA256SUMS 和 `rollback-immediate-0.1.16.sh` 均已复核。

独立后检确认本机/公网 health、ready 均为 0.1.16，schema 与五项数据量未变化，环境仍为
`600:root:root`，公开 wheel SHA 为
`7868e17eca4225ccfea2f92872dc0e6aa37c64c5359cb84e08d78b5b9dfee867`，未知下载返回 404，
Nginx/PostgreSQL PID 仍为 `127548/137458`，失败单元与切换后 AgentPost error 均为 0。公开 Orbit
入口可正常加载；当前浏览器登录态已过期，因此逐轮任务状态、目录范围、短名称入口和真实 390px
生产交互仍需 Human 登录后验收。当前证据是
`task_rounds_contact_directory_deployed_https_verified`，不是 `production_accepted`。

### 豆包工作本机 STDIO 接入（0.1.16 历史本地切片，已由 0.1.17 取代）

020 的 Codex 已在豆包工作 2.25.18 / macOS arm64 上完成原生 STDIO 宿主探针：绝对 command、
逐项 args/env、保存后自动启动、`initialize → notifications/initialized → tools/list` 以及停用后
重启均成立；未发现受支持的连接器导入、专用 deep link 或企业策略下发合同。该外部回传已按
`external_agent_content` 处理，并由本地实现和测试独立约束。

本地已新增独立 `doubao_work` setup adapter。它复用现有配对、OS 凭据保险库和 `agentpost-mcp`
STDIO 服务，生成权限 0700 的单一启动器；启动器只保留非秘密 server/profile 定位，运行时先从
保险库恢复配对身份并写入真实 heartbeat，再启动 MCP，绝不把 API Key、长期 token、args 或 env
写进豆包表单。setup 在原生连接器保存前返回 `native_registration_required`，不会把“已授权但尚未
保存连接器”误报为在线。

连接页、Skill、SDK CLI、服务端平台 gate、生产环境样例和 Orbit 豆包提示已统一切到本机
`local_bootstrap`；实验性 Remote MCP/OAuth 继续关闭并仅保留后备代码。豆包工作没有公开的连接器
自动导入能力，因此当前真实边界是：Agent 能控制原生 UI 时自行完成；否则 Human 只复制已准备的
一项，选择 STDIO 并保存一次，随后必须看到 AgentPost tools/list 才能声明成功。不能把这项本地
能力表述成完全零操作或 `production_accepted`。

验证证据：聚焦 Python 81 passed；完整 non-PostgreSQL 回归 405 passed、1 个预期 loopback
sandbox skip、5 个 PostgreSQL deselected；Orbit JavaScript 24 passed；JavaScript syntax、Ruff
check/format 均通过。隔离 Orbit 演示已验证桌面与 390×844 豆包入口、无横向溢出和无控制台
warning/error。最终 diff/staged 复核与 `git diff --check` 通过；本切片提交以本段所在 Git 历史为准。
生产仍为 `e50652e / 0.1.16`，未部署本切片。

### 逐轮任务状态、短名称入口与联系人目录（0.1.16 已部署，待登录态验收）

根据登录态生产 Chrome 中与 020 的真实五条消息核对：第一、第二轮 task 都已有 020 的直接回复，
第三轮尚未回复；0.1.15 页面却把前两轮仍显示为“待处理”。本地已把任务判定改为逐条 task 计算：
直接回复即完成该轮，结构化 result 的 completed/partial/failed/cancelled 状态继续作为更高优先级
结果；Delivery、read、ACK 仍不等于任务完成。三轮回归样本现在得到“完成、完成、待处理”，汇总
待处理数量为 1，Thread 和任务列表口径一致。

云驿 Agent 详情页的“设置/修改短名称”已从“危险操作”页签移到详情标题区，Owner 打开 Agent 后
首屏即可找到；Viewer/Auditor 不显示该所有者操作，断开和删除仍保留在“危险操作”。桌面和移动端
共用该入口，避免窄屏用户继续深入多层页签。

目录搜索原 MVP 仅以 Agent 已认证作为边界，会返回所有匹配的活跃 Agent；这与自然语言收件人解析
已有的关系范围不一致。本地已统一为服务端验证的联系人范围：当前 Agent、同一 Human 所有的 Agent、
明确组织/ACL 授权，以及任一方向已有真实消息往来的 Agent。完全无联系的 Agent 不再出现在搜索
列表；已知完整地址或准确短名称仍可用于主动首次联系，但不能用于枚举全平台目录或取得无关所有者
信息。相关规则已同步写入 `AGENTS.md`。

本地证据：Python fast 395 passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL deselected；
MCP 11 passed、Orbit JavaScript 24 passed，JavaScript syntax、Ruff check/format 和 diff check 通过。
登录态 Chrome 的真实 020 Thread 用于确认“前两轮已回复、第三轮未回复”；隔离演示环境验证桌面
Agent 详情首屏直接显示“修改短名称”。390×844 下按钮位于详情首屏、38px 高，弹窗可正常打开，
`scrollWidth = innerWidth = 390`，危险操作页签仍折叠。当前证据是
`task_rounds_contact_directory_local_verified`；其代码已随 0.1.16 部署，生产登录态验收见上节。

### 移动端星轨快捷筛选（0.1.16 已部署，待登录态验收）

移动端继续由底部“星轨、云驿、设置”承担一级导航；星轨页面不再叠加“对话与协作、任务进展、
待我处理”三个等权页签。页面直接以“对话与协作”为当前内容，把“待我处理”和“任务进展”改为
两张轻量快捷筛选卡并显示真实数量；点击进入对应内容，再次点击当前卡片返回全部对话。桌面端
仍保留左栏快捷入口、中栏“对话与协作”父节点和右栏完整对话，不受本切片影响。

移动端顶部连接状态使用独立长/短标签：桌面仍显示“1 个 Agent 已连接”，580px 以下显示单行
“1 个 Agent”；0 个 Agent 时使用中性圆点，不再把未连接状态显示为绿色。同步中和同步失败也使用
窄屏短文案。另为 Thread 卡片及其内容补充 `min-width: 0`，解决 320px 下长 Human/Agent 名称把
页面撑宽的问题。

本地证据：Human 控制面集成 15 passed、Orbit JavaScript 23 passed、JavaScript syntax、Ruff
check/format 和 diff check 通过。隔离演示环境实测 390px 的顶部状态宽 85px、无横向溢出，两个
快捷入口可在任务/待处理与全部对话间往返；320px 下 `scrollWidth = innerWidth = 320`、计数可见、
对话卡不越界；1280px 桌面仍为 178/390/640 三栏，完整连接文案和桌面快捷入口保持不变。当前
证据是 `mobile_startrail_shortcuts_local_verified`；代码已随 0.1.16 部署，真实登录态 390px
生产验收待确认。

### 确认稿顶部栏与阿里云发布提效（`0b2dc9c` / 0.1.15 已部署）

本地顶部栏已按 `docs/startrail-conversation-navigation-demo.svg/.png` 的原生 1600px 几何实现：
78px 通栏白底、左右 34px 内距、确认稿原路径的 40px 渐变 Logo、两行“星云驿 / AgentPost · 星轨”、
235px 连接状态胶囊和右侧 Human 信息。顶部中央原“星轨看协作 / 云驿管 Agent / 设置管账户”三段已
删除；左栏三个业务入口不受影响。390×844 下顶部保持紧凑、无横向溢出。

生产已于 2026-08-26 16:49（Asia/Shanghai）切换到 `0b2dc9c / 0.1.15`。不可变源码与 runtime
分别为 `/opt/agentpost/releases/0b2dc9c`、`/opt/agentpost/venvs/0b2dc9c`；公开 wheel 为
`https://agentpost.me/downloads/agentpost-0.1.15-py3-none-any.whl`，SHA-256 为
`dcf9f8d414efa478a4192c8892902cfd2e3aa0c6219db128680b55c51f5601df`。

验证：34 个聚焦 Python 测试、Orbit JavaScript 21 passed、JavaScript syntax、Ruff
check/format、锁文件和干净归档可重复构建通过。生产浏览器实测桌面 Logo 40×40、左距 34px；
390×844 下 Logo 36×36、左距 12px；两端均无顶部中央导航和横向溢出。

本次未新增长期权限，直接用 Workbench 文件管理上传完整的 1.5 MB 源码归档与 672 KB wheel，已
消除上次 246 个 Base64 片段的低效路径。第一次尝试因 canary 工作目录权限在生产变更前停止；
第二次切换在后检读取 root-only 文件属性时触发自动回退并完整恢复 0.1.14；修正只读后检后第三次
成功。验证回滚点为 `/opt/agentpost/backups/20260826-164945-0b2dc9c-pre-015/`，含可读 PostgreSQL
dump、附件归档/list、环境、systemd、Nginx、校验和及 `rollback-immediate-0.1.15.sh`。

最终本机/公网 health、ready 均为 0.1.15，schema 仍为 `0021_human_thread_views`，数据为 25 Agents /
58 Messages / 58 Deliveries / 4 Attachments / 7 Humans；环境仍为 `600 root:root`，未知 wheel 路径
404，切换后 error 日志为 0。Nginx/PostgreSQL 主进程保持 `127548`/`137458`；仅 AgentPost 重启。

### 星轨对话导航生产发布 `91d0e4f` / 0.1.14

生产已于 2026-08-26 15:28:58（Asia/Shanghai）受保护切换到提交 `91d0e4f` / package
`0.1.14`。不可变源码与独立 runtime 分别为 `/opt/agentpost/releases/91d0e4f`、
`/opt/agentpost/venvs/91d0e4f`；公开 wheel 为
`https://agentpost.me/downloads/agentpost-0.1.14-py3-none-any.whl`，SHA-256 为
`dbbb8dc61b95742eeb1a8b02f9fa187994225bd50c3bdabc9077ef1ee56b97f6`。

确认稿已经落地：PC 中栏以“对话与协作”为父节点，按持久化 `thread_id` 展示完整往来闭环，未被
当前 Human 查看时显示红点；点击具体对话后，右栏集中展示全部消息、发送自/给、任务信息与可打开
或安全预览的附件。移动端使用同一信息结构，并保持列表与详情分层。新增
`human_thread_views` 只记录当前 Human 最近看到哪条消息，不改变 Agent 的 delivered/read/ACK 或
任务状态；新消息到达后会重新出现未查看红点。

发布前基线为 24 Agents / 56 Messages / 56 Deliveries / 4 Attachments / 9 current bindings /
6 Humans，schema 为 `0020_pairing_agent_intent`。完整可恢复备份位于
`/opt/agentpost/backups/20260826-152452-91d0e4f-pre-014/`，含 PostgreSQL custom dump/catalog、
附件归档/list、root-only 环境、systemd、Nginx、旧 0.1.13 wheel、校验和及迁移感知的一键脚本
`rollback-immediate-0.1.14.sh`。

第一次受保护切换因 Nginx 仍只允许旧 wheel 的精确路径，在新 wheel 公网校验 404 时自动将 schema、
指针、环境和服务完整恢复至 0.1.13。补入 0.1.14 精确白名单并保留其余 `/downloads/` 404 后，第二次
切换成功。最终本机/公网 health、ready 均精确返回 0.1.14，schema 为
`0021_human_thread_views`；六项业务基线未减少，Nginx/PostgreSQL 主进程仍为
`127548`/`137458`，环境权限仍为 `600 root:root`，切换后 error 与 HTTP 5xx 日志为 0。

本地证据：392 Python passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL deselected；
独立 PostgreSQL 验证 5/5；MCP 10、Orbit JavaScript 21、TypeScript Connector 4 passed；Ruff
check/format 和插件 manifest 校验通过。线上公开 Orbit 页面、JS、PNG 品牌资源和 wheel 均完成
精确校验，浏览器控制台无错误。当前证据标签为
`startrail_conversation_navigation_deployed_https_verified`，不是 `production_accepted`；真实双
Human 的“未查看→打开→新回复后再出现红点”闭环与外部登录态 390px 使用仍需用户验收。

### 对话身份与安全附件生产发布 `f15df99` / 0.1.13

生产已于 2026-08-26 13:34（Asia/Shanghai）受保护切换到提交 `f15df99` / package
`0.1.13`。不可变源码与独立 runtime 分别为 `/opt/agentpost/releases/f15df99`、
`/opt/agentpost/venvs/f15df99`；server、Python SDK、MCP 均为 0.1.13。公开 wheel 是
`https://agentpost.me/downloads/agentpost-0.1.13-py3-none-any.whl`，SHA-256 为
`425e4596afedd32905c900ca90bf9a0e9c270e469ac428f7fa8733b43a78c510`。发布物来自
`git archive f15df99`，不含工作区中未提交的 PNG 实验。

发布前在线确认生产仍为 `f10e75c` / 0.1.12，AgentPost、Nginx、PostgreSQL active，schema 为
`0020_pairing_agent_intent`，数据为 24 Agents / 54 Messages / 54 Deliveries / 4 Attachments /
9 current bindings。可恢复备份位于
`/opt/agentpost/backups/20260826-131431-f15df99-pre-013/`，包含 PostgreSQL custom dump 及
可读目录、附件归档与清单、root-only 环境、systemd、Nginx、旧 0.1.12 wheel、校验和和
`rollback-immediate-0.1.13.sh`。较早的
`/opt/agentpost/backups/20260826-1313-f15df99-pre-013/` 因 PostgreSQL 写入权限不匹配而未完成，
已明确保留为不可用于恢复的 incomplete 记录。

第一次应用切换在新版本启动并返回 HTTP 200 后，因为 `set -o pipefail` 下的 `curl | grep -q`
健康匹配被误判为失败，失败保护随即恢复 `f10e75c` / 0.1.12；回退后的指针、服务、内外网健康、
环境、unit 和 Nginx 白名单均复核通过。随后在 127.0.0.1:8001 临时启动单进程 0.1.13，精确取得
0.1.13 health/ready 后停止；第二次切换改用完整响应精确比较并成功。该经验已补充到根目录
`AGENTS.md` 的发布规则。

最终 postflight：本机及公网 health/ready 均为 0.1.13；schema 和五项数据量与发布前完全一致；
Nginx 主进程 `127548`、PostgreSQL 主进程 `137458` 均未变化；生产环境仍为 `600 root:root`；
未知 `/downloads/` 路径继续 404；0.1.12 wheel 仍按原 SHA 可读作为回退资源；Nginx 配置检查通过，
磁盘使用 20%。企业统一登录实际返回 disabled，Remote MCP/豆包工作远程连接继续保持默认关闭。

登录态生产 Chrome 已验证桌面三栏：星轨中栏显示 21 个按持久化 Thread 聚合的“对话与协作”，
右栏显示多轮时间线，消息明确显示“发送自：Human 名称 · Agent 短名称”和“发送给：我/对方 ·
Agent 短名称”。真实 `text/html` 附件已通过“安全预览”打开，iframe 内可见正文，界面明确说明
脚本、联网请求、表单和弹窗已停用，关闭后回到原 Thread。PDF 授权打开由本地/自动化测试覆盖；
真实 390px 生产浏览器复验仍为待确认，不能用桌面结果替代。

本地发布前证据为：392 Python passed、1 个预期 loopback sandbox skip、5 个 PostgreSQL
deselected；MCP 10、Orbit JavaScript 24、TypeScript Connector 4、OpenClaw plugin 4 passed；
Ruff check/format 通过。当前证据标签为
`conversation_identity_and_safe_attachment_deployed_https_verified`，不是 `production_accepted`。
下一步优先做真实 390px 移动端布局/预览复验，以及在真实 PDF 附件存在时完成生产点击打开；既有
Hermes 实机配对收发/重启和 Manus/豆包工作 Remote MCP OAuth 门禁继续保留。

### 对话与安全附件体验切片五 `3b4adf5`

根目录新增 `AGENTS.md`（提交 `f93e0d6`），把交接优先级、脏工作区保护、小切片开发、普通用户
文案、Human/Agent 凭证隔离、组织权限、消息状态语义、桌面/移动端验收、测试命令和生产边界写成
仓库级约定。现有 PNG 品牌替换实验在开发、暂存和提交过程中均保持原样，没有被回退或纳入提交。

首页已删除普通用户可见的 Human Key 登录入口。Human Key 后端兼容能力继续保留给旧 CLI/集成和
既有高风险操作重新验证，设置页改称“旧版集成凭证（高级）”，并明确普通用户登录不需要它。
MFA 改为“使用认证器 App 的 6 位双重验证码”，恢复码明确为认证器不可用时的一次性应急登录码；
企业 SSO 改为“单位统一登录（SSO）”，解释为单位开通后可使用工作账号登录。

星轨桌面中栏统一为“对话与协作”，继续严格按持久化 `thread_id` 聚合，每个对话集中展示全部往来，
右栏显示当前对话详情。参与者和每条消息新增 Human 归属投影：发送端显示“发送自：Human 名称 ·
Agent 短名称”，接收端在当前 Human 自有 Agent 上显示“发送给：我 · Agent 短名称”；只返回显示名
和当前归属判断，不暴露 Human ID。通信状态、工作状态和内部协议说明已改成“送达情况”“任务进度”
等普通用户文案，未实现的新动态/待处理筛选从主界面移除。

新增 Human 会话鉴权的附件下载与预览端点。它复用 Thread 正文可见性：Owner、Operator、Viewer
可访问授权范围内的已绑定附件；Auditor、无权用户、待上传附件和未知附件统一返回 not found。
PDF 以新标签页打开，HTML 在无脚本、无联网、无表单、无弹窗、无同源权限的双重 sandbox 中预览，
其他附件提供授权下载；打开和预览均不写 Delivery、read 或 ACK。演示数据新增有效 PDF 与带脚本
HTML，用于真实验证脚本没有执行。

桌面端本地浏览器实测登录、3 个 Thread 列表、列表/详情切换、Human/Agent 收发信息、PDF/HTML
附件入口和 HTML 隔离预览；PDF 授权打开端点及新标签链接由自动化验证。页面 `scrollWidth=1280`，
主页面未被预览脚本修改，控制台无 error。
移动端继续使用列表/详情分层，附件按钮改为全宽可触控布局，预览弹窗使用窄屏尺寸；相关 390px
CSS 结构与 JavaScript 自动化测试通过。当前浏览器控制接口本轮无法切换窄屏视口，因此真实 390px
手动浏览器复验如实保留为待确认，未把桌面结果冒充移动端实测。

从提交 `3b4adf5` 生成的独立干净快照（不含 PNG 实验）通过：392 Python passed、1 个预期
loopback sandbox skip、5 个 PostgreSQL deselected；MCP 10、Orbit JavaScript 24、TypeScript
Connector 4、OpenClaw plugin 4 passed；Ruff check/format 和 diff 检查通过。该段保留为
发布前本地证据；当前生产事实以上方 0.1.13 发布记录为准。

### 设置/组织角色体验切片四 `3fa7e8a`

切片四已把组织邀请从“登录后自动接受”改为“先预览、再由 Human 明确确认”。新增的
`POST /api/v1/orbit/organization-invitations/preview` 是无副作用的已登录预览：令牌只在请求体中
传递，继续校验邀请状态、有效期和目标邮箱，不匹配时统一 not found，不创建成员关系、不消耗邀请。
确认弹窗在加入前显示组织、角色、可见范围、可执行操作和邀请有效期，并明确个人 Agent、个人
对话、直接授权和 Agent 通信 ACL 不会自动共享。

设置页同时明确展示 Owner、Admin、Member、Auditor 四种角色体验。Owner 可治理全部角色；Admin
邀请选项只保留 Member/Auditor；Member/Auditor 不显示邀请治理入口。组织角色说明持续强调成员
关系不等于 Agent 所有权，组织派生权限不开放连接、重命名、断开或删除。成员列表确认当前用户是
最后一名 Owner 时，“退出组织”会禁用并提示先转交 Owner；服务端既有鉴权仍为最终权威。

本地证据：聚焦组织/控制面集成测试 20 passed；全量 fast 为 391 passed、1 个预期 loopback
sandbox skip、5 个 PostgreSQL deselected；MCP 10、Orbit JavaScript 23、TypeScript Connector
4、OpenClaw plugin 4 passed；Ruff check/format、JavaScript syntax 和 `git diff --check` 通过。
隔离 `make orbit-demo` 在桌面和 390 px 下完成真实浏览器交互：角色卡、Owner 治理弹窗、邀请角色、
最后一名 Owner 禁用状态和移动端单列均正确，页面 `scrollWidth=390`，控制台无 warning/error。

额外尝试运行原有 12 步 `make demo` 时，Alembic 在 SQLite 执行历史迁移
`0019_agent_handles` 的 `create_check_constraint` 触发 SQLite 不支持 ALTER constraint 的
`NotImplementedError`。这发生在本切片 API/UI 运行前，聚焦和全量回归没有同类失败；当前如实记录
为既有 demo/SQLite 迁移缺口，不在本切片中顺带改写历史迁移。切片证据标签为
`settings_organization_roles_local_ui_verified`，未部署、未发布，也不是 `production_accepted`。

`v0.1.12-local.1` 仍是上一恢复标签；`3fa7e8a` 是其后的功能提交。工作区中的 PNG 品牌实验仍按
原要求保持未暂存，SHA-256 为
`71f10092a1e8ef43cbcfa11279500cbbfe05308eb1c099c149d4cbefb86d9c13`，没有进入切片四提交。

### 本地阶段版本 `v0.1.12-local.1`

本阶段以已提交的 `43796a1` SVG 品牌锁定稿为代码基线，并由本交接提交建立 annotated Git tag
`v0.1.12-local.1`。它继承 0.1.12 的六类 Agent 选择器、Hermes macOS/Linux 发布门、Human
工作台、Thread/Agent 管理、自然语言收件人解析、OS-vault 凭据边界和生产部署回执；不改变公开
包版本、协议、数据库迁移或阿里云服务。

检查在 `/private/tmp` 下通过 `git archive 43796a1` 生成的干净快照中完成，避免当前工作区的
未提交实验影响结论。结果为：391 Python passed、1 个预期 loopback sandbox skip、5 个
PostgreSQL deselected；MCP 10、Orbit JavaScript 21、TypeScript Connector 4、OpenClaw plugin
4 passed；Ruff check/format 和 JavaScript syntax 通过。干净快照构建出的 0.1.12 wheel SHA-256
为 `903dde56f9bf06fdeb75dcecc1430aafdbd1d85b42ca31b24dcceaf846ad52d6`，其中 Orbit HTML 与
SVG 源一致且不包含 PNG 品牌图。代码审查未发现需要阻止阶段冻结的问题。

当前工作区另有一组未提交的 PNG 品牌替换实验：修改
`src/agentpost/api/routes/orbit.py`、`src/agentpost/orbit_ui/index.html`、
`src/agentpost/orbit_ui/styles.css`、两项 Orbit 测试，并新增
`src/agentpost/orbit_ui/xingyun-relay-logo.png`。Human 已明确“SVG 先不改”，因此这些文件保持
原样，既没有删除也没有暂存，不属于 `v0.1.12-local.1`。后续继续开发前必须先识别这组差异，
不能误称为阶段基线或直接覆盖。

恢复时优先使用非破坏性检查：`git show v0.1.12-local.1`、
`git archive v0.1.12-local.1`。若工作区存在未提交修改，不得直接 checkout/reset；先保留用户
修改并在独立目录验证。当前阶段标签是 `v0.1.12-local.1_verified`，不是新部署，也不是
`production_accepted`。真实 Hermes 配对/收发/重启，以及 Manus、豆包工作安全 Remote MCP
OAuth，仍是下一阶段待办。

生产已于 2026-08-26 切换到提交 `f10e75c` / package `0.1.12`，不可变源码与 runtime 分别为
`/opt/agentpost/releases/f10e75c`、`/opt/agentpost/venvs/f10e75c`。公开 wheel SHA-256 是
`abec6302203964eae51312adebaa509ccce228cf0342d9c4f86b0e9db7f5d821`，bootstrap 响应头与正文
SHA-256 均为 `35f5c01363d0111214cda780d52e9fe885a5c63f227c7c9d01baba06820085c2`。
AgentPost/Nginx/PostgreSQL 均 active，health/ready 均为 0.1.12，schema 保持
`0020_pairing_agent_intent`，切换后 fatal/HTTP 5xx 为 0。

有效回滚点是 `/opt/agentpost/backups/20260826-0908-f10e75c-pre-012/`，包含可读数据库与附件
备份、受保护配置、校验和和 `rollback-immediate-0.1.12.sh`。第一次切换因为 Nginx reload 后
立即校验命中了旧 worker 而安全中止并恢复 0.1.11；改为轮询到第 2 次返回 200 且 wheel SHA
正确后，第二次应用切换成功。备份时为 23 Agents / 50 Messages / 50 Deliveries；postflight 为
23 / 51 / 51 和 9 个 current bindings，期间新增了一条正常业务消息和投递，没有回退或丢失。

真实生产星轨已按 WorkBuddy、豆包工作、OpenClaw、Hermes、Codex、Manus 顺序展示六个选择。
Hermes 选择后生成可直接粘贴到普通对话框的 `AP-HERMES-V1` 接入码；公开合同允许 macOS/Linux。
现在可以开展真实 Hermes 安装、网页授权、配对和收发测试。Remote MCP OAuth 仍为 false，故
Manus 和豆包工作仅展示合同入口并返回明确 409，当前不能作为“连接成功”测试，也不能改用
长期 API Key 绕过。证据标签为
`hermes_release_gate_and_six_host_picker_deployed_https_verified`，不是 `production_accepted`。

以下保留 0.1.12 发布前的本地切片记录：星轨“连接新的 Agent”按固定顺序列出 WorkBuddy、豆包工作、
OpenClaw、Hermes、Codex、Manus。Hermes 走本机 bootstrap，并通过官方 `hermes config set` / `hermes mcp test`
注册与验证 MCP；配置
只含 server/profile，headless Linux 与 OpenClaw 一样选用 OS vault 的 `session` collection。
`AGENTPOST_HERMES_SETUP_PLATFORMS` 必须显式发布，不继承 Codex，避免生产 0.1.11 wheel 被误报
为可用。豆包工作和 Manus 都走独立 HTTPS Custom MCP 合同，不运行本机安装。豆包工作仅采用
桌面端“自定义连接器”的 HTTP + 浏览器 OAuth 路径，浏览器/移动端不宣称支持；新增的
`AGENTPOST_DOUBAO_WORK_REMOTE_MCP_ENABLED` 还必须与全局 Remote MCP OAuth 同时开启。当前通用
第三方 OAuth 与 remote host/新 Agent 意图绑定尚未完成，故豆包工作发布门保持关闭，重连也以
稳定 409 停止，不能改用 Header 或长期密钥。Manus 的 Remote MCP OAuth 未开启时以
`manus_remote_mcp_not_released` 安全停止，现有 Agent 重连尚未发布并以
`manus_reconnect_not_released` 停止。当前生产 Remote MCP 仍关闭，也没有真实 Manus/Hermes
或豆包工作账户宿主验收。六卡界面与 Hermes 发布门现已随 0.1.12 部署；Manus/豆包工作仍未
发布为可连接能力，三类 Agent 都不能写成 `production_accepted`。

发布前的本地证据：391 passed、1 个明确 loopback sandbox skip、5 个 PostgreSQL deselected，
另有 MCP 10、Orbit JavaScript 20、TypeScript Connector 4、OpenClaw plugin 4 passed；Ruff、Skill
校验、插件三文件副本一致性与 diff 检查通过。隔离演示页实测六卡顺序严格为 WorkBuddy、豆包
工作、OpenClaw、Hermes、Codex、Manus；桌面为 3 × 2，首个键盘焦点为 WorkBuddy，390 px 为
单列且无横向溢出、弹窗可滚动，豆包工作接入码分流正确且控制台无告警/错误。此前临时 wheel
已核对包含 Hermes adapter、四宿主 bootstrap 和更新后的 Orbit 资源，检查后已删除；随后由
上方记录的 0.1.12 精确 wheel 完成正式部署。

本地新增的 Human 工作台把现有能力统一到三个一级入口：星轨看协作、云驿管 Agent、设置管
Human 账户和平台关系。桌面使用三栏，移动端使用底部三个具名入口；`module` / `view` 查询参数
保留刷新、深链接和浏览器返回上下文。通知、数据导出和界面偏好等未有真实服务端能力的项目
明确标记为待确认，没有伪造开关；Human 新动态也没有复用 Agent `read` 或 ACK。`make
orbit-demo` 只在 loopback 启动隔离的临时 SQLite 演示数据，未触碰阿里云或生产数据。当前证据
标签为 `local_ui_review_ready`，不是发布或 `production_accepted`。

最新本地视觉切片使用独立设计的多彩轨道/中继 SVG 标识、明亮 Material 风格色彩、系统无衬线
字体和始终带中文名称的 SVG 导航图标。星轨默认直接进入按 Thread 聚合的对话，删除了与云驿
Agent 总览重复的“协作总览”；真实 Agent 统计只保留在云驿。桌面继续使用三栏，390 px 手机端
继续使用底部三入口和列表/详情分层，并修复跨模块或返回列表时残留旧滚动位置的问题。普通
文本使用明亮阅读卡片，JSON 保持独立原始视图；内容仍通过 `textContent` 渲染，不改变
`external_agent_content` 不可信边界。

切片二新增只读的 Human Thread 列表和详情投影：严格按持久化 `thread_id` 聚合，支持授权范围
内的主题、Agent、正文和附件名搜索；Auditor 的正文与附件名不会进入结果，未知或失权 Thread
统一返回 not found。时间线区分通信状态、工作状态、任务结果与回复关系，移动端使用列表/详情
分层。页面打开和搜索均不会写 Delivery、read 或 ACK；Human 新动态状态和审批与 Thread 的真实
关联仍明确标记待接入。该切片没有改变消息协议、ACL、发送者绑定或组织权限。

切片三把云驿重构为 Agent 列表/总览/详情：按我的 Agent 与组织范围分组，基于 current binding、
Connector 健康证据和五分钟心跳窗口严格区分正常连接、等待 Agent、未连接、离线和连接异常。
Agent 详情把当前连接、能力、权限关系、历史连接、相关 Thread 和危险操作分开；current 与历史
Connector 不会被误显示成多个 Agent。`agent` / `agentTab` 深链接、星轨往返和移动端列表/详情
分层已在本地浏览器验证。组织派生访问不会变成 Agent 所有权，管理按钮仍以既有服务端权限为准，
删除仍为保留身份、对话和审计的软删除。

当前本地证据：379 passed、1 个明确 loopback sandbox skip、5 个 PostgreSQL deselected；另有
MCP 10、Orbit JavaScript 16、TypeScript Connector 4、OpenClaw plugin 4 passed。Ruff/format、
JavaScript 语法、桌面/390 px 移动端浏览器交互、无横向溢出、空控制台和 diff 检查通过。未部署、未发布，协议、权限和安全边界
未改变；后续仍是切片四设置/组织角色体验和切片五安全内容与附件预览。

以下 0.1.11 生产记录保持不变。

测试者在 0.1.10 重试后确认：OpenClaw + Linux 发布门已经开放，但 headless 主机上的默认
GNOME Keyring login collection 仍要求图形/系统级解锁，最终以
`secure_credential_storage_unavailable` 安全失败。0.1.11 改为在无 `DISPLAY` / `WAYLAND_DISPLAY`
的 OpenClaw Linux 环境中使用 Secret Service 已解锁的内存 `session` collection；MCP 配置只
写 server、profile 和非秘密 collection selector，不写 token。该存储跨 Gateway 进程重启
保留，但主机重启后需要 Human 再做一次网页授权；继续禁止明文文件、空密码 keyring 和不明
backend。

提交 `50345b8` 实现 headless session vault，`a6d99c3` 固定 0.1.11 版本。本地证据为 377 个
Python passed、1 个 sandbox skip、5 个 PostgreSQL deselected；另有 MCP 19、TypeScript 4、
OpenClaw plugin 4、Orbit JavaScript 2 passed，Ruff/format、隔离 wheel、内容和版本检查通过。
wheel SHA-256 为
`1d7e9acfb4e2b57ba877e118a304df2880ee4327abc48a2fccfe08a37f30e935`。

真实阿里云 Linux 主机探针已用 OpenClaw 实际 `admin` 用户从该 wheel 成功完成 session vault
写入、读取和删除，未打印凭据，也未修改 OpenClaw 配置。生产最终已切换到 0.1.11 /
`a6d99c3`；前两次受保护尝试分别发现 release-version 环境项和公开 wheel 路径问题，并自动
回滚到健康 0.1.10，修正后的第三次切换通过全部门禁。当前路径为
`/opt/agentpost/releases/a6d99c3` 和 `/opt/agentpost/venvs/a6d99c3`，schema 仍为
`0020_pairing_agent_intent`，数据仍为 22 Agents、48 Messages、48 Deliveries、8 个 current
Connector bindings，fatal/5xx 为 0。

有效回滚点是 `/opt/agentpost/backups/20260826-0006-a6d99c3-pre-011/`，脚本
`rollback-immediate-0.1.11.sh` 回到 0.1.10 / `3b46e45` 且不降级数据库。真实 OpenClaw 主机
读取到 0.1.11 契约和匹配 wheel 哈希，原 OpenClaw `2026.4.27` Gateway 保持 active 且 PID
未变。下一步只让 Human 重试同一接入代码，验证真实 pairing、给 `magent` 发送、收件及
Gateway 进程重启恢复；主机重启后重新授权是当前明确边界。证据标签为
`openclaw_headless_session_vault_deployed_https_verified`，不是 `production_accepted`。

以下 0.1.10 内容保留为上一阶段记录。

最新问题是 OpenClaw 在阿里云 Linux 服务器接入时被提示“只支持 Mac”。根因是接入脚本无论
选择哪种 Agent 都读取 `codex_setup_platforms`，而生产的 Codex 策略确实只有 Mac。修复提交
`55ae339` 将发布平台拆分为 Codex、WorkBuddy、OpenClaw 三类；`3b46e45` 形成 0.1.10 候选版。
OpenClaw 允许 Mac/Linux，Codex 与 WorkBuddy 不被连带放宽；旧服务器仍兼容原字段。

对用户另一台阿里云 OpenClaw 服务器的只读检查确认：Alibaba Cloud Linux 3 上的 OpenClaw
`2026.4.27` Gateway 正在以普通用户的 user-systemd 服务运行，`mcp set`、`mcp probe` 命令均
存在。真正剩余的主机前置条件是该无桌面 Linux 尚未注册可持久化的 Secret Service：D-Bus
和 libsecret 已有，但 Gateway 用户没有加密凭据提供者。0.1.10 因此在网页配对前先做 MCP
能力检查，并以结构化错误要求在同一次系统安装确认中补齐安全钥匙库；继续禁止明文密钥
回退。诊断没有修改 OpenClaw 服务、配置、密钥或版本。

0.1.10 wheel SHA-256 为
`852d1bf4f1ca49abde9a2bd5e033332dc7842a0f7e5e1fa08bd1bc7e5ac00117`。本地证据：371 个
Python passed、1 个明确 sandbox skip、5 个 PostgreSQL deselected；另有 MCP 9、TypeScript
Connector 4、OpenClaw plugin 4、Orbit JavaScript 2 passed，Ruff/format、隔离 wheel 与内容
检查通过。生产已于 23:30 切到 0.1.10 / `3b46e45`，server、SDK、MCP 版本一致，schema
保持 `0020_pairing_agent_intent`。公开 health/ready、host 平台契约、wheel 哈希、Nginx、迁移、
数据计数和 journal 均通过；22 Agents、48 Messages、48 Deliveries、8 个 current Connector
bindings 在切换前后不变。有效回滚点是
`/opt/agentpost/backups/20260825-2324-3b46e45-pre-010/`，立即回滚到 0.1.9 / `c1c3a78`，不降级
数据库。

真实阿里云 Linux OpenClaw 服务器已能读取 0.1.10 与 OpenClaw=`mac,linux`，公开 wheel 哈希
匹配，Gateway 服务仍 active。原 `setup_not_released_for_platform` 已在线消除。下一步让 Human
重试同一官方接入步骤，再完成真实配对、发送给 `magent`、收件与 Gateway 重启后恢复验证。
当前标签是 `openclaw_linux_release_gate_deployed_https_verified`，不是
`production_accepted`。

以下删除空响应内容保留为当前生产版本记录。

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
