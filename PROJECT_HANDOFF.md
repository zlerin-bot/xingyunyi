# 星云驿项目交接文档

- 交接阶段：`v0.1.14-startrail-conversations-deployed`
- 核验日期：2026-08-26
- 代码分支：`main`
- 阶段性质：确认稿中的星轨对话导航、未查看红点、完整右栏详情和移动端对应体验已随 0.1.14 部署并完成 HTTPS 核验；仍不是完整生产验收
- 本地开发状态：发布候选 `91d0e4f` 已提交并部署；本节记录本次部署与回滚证据

## 0. 当前接续摘要（优先于下方历史冻结记录）

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
