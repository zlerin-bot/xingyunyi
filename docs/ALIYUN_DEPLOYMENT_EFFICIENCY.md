# 星云驿阿里云发布提效方案

更新时间：2026-08-27

适用环境：阿里云轻量应用服务器（杭州）、Ubuntu 24.04、systemd AgentPost、Nginx、同机
PostgreSQL。本文优化操作通道，不删减预检、备份、迁移、健康检查或自动回退。

## 0. 当前唯一推荐的成功路径

截至 2026-08-27，这台生产服务器尚未完成部署专用 SSH 公钥的只读连通验证。因此后续发布**不要
先尝试 SSH、命令助手传文件、Base64 分片或 Docker Compose**；当前默认路径固定为：

> 干净提交生成一个上传包 → Workbench 上传一个文件到 `/home/admin` → 一条 staging 命令自动建目录并校验解包 → 一条受保护切换命令 → 一条后检命令

### 第一步：本机从明确提交生成完整发布物

先确认版本提交已经存在且本地验证完成，再运行：

```bash
scripts/aliyun/prepare-release.sh <commit> <version> <alembic-head>
```

例如 0.1.19：

```bash
scripts/aliyun/prepare-release.sh 8f9bc79 0.1.19 0023_human_usernames
```

脚本只读取指定 Git 提交，不打包当前工作树，并在 `dist/<version>/` 生成内部六个发布文件，另外
自动生成两个操作入口：

1. `agentpost-<version>-source.tar.gz`
2. `agentpost-<version>-py3-none-any.whl`
3. `manifest-<version>.txt`
4. `SHA256SUMS`
5. `aliyun-switch-release.sh` 与 `aliyun-postflight.sh`
6. **唯一需要上传的** `agentpost-<version>-aliyun-upload.tar.gz`
7. 本机复制命令用的 `workbench-commands-<version>.txt`（不要上传）

缺少项目 `.venv`、提交版本不匹配、wheel 文件名不匹配或任一构建步骤失败时立即停止，不进入阿里云。

### 第二步：Workbench 只上传一个文件，不在界面建目录

Workbench 当前文件选择器只支持单文件，不能把“选择六个文件”当成一次上传。文件树在窄窗口里
创建、刷新和进入目录也很慢。因此固定进入 `/home/admin`，只上传：

```text
dist/<version>/agentpost-<version>-aliyun-upload.tar.gz
```

不要先在文件管理器创建 `agentpost-release-<version>`，不要逐个上传内部六个文件，也不要上传
`workbench-commands-<version>.txt`、源码工作区、环境文件、密钥或数据库备份。

上传后从本机打开 `dist/<version>/workbench-commands-<version>.txt`，复制第一条 staging 命令。它会
一次完成外层上传包 SHA-256、版本目录创建、解包、内部六文件 SHA-256、脚本语法及执行权限修正，
最后必须输出：

```text
stage_status=ok release=<version>
```

所有文件必须显示 `OK`。目录已存在时 staging 命令会停止，不覆盖既有目录；先只读检查它属于哪次
尝试，再决定是否使用新的版本号或另行处理。任一哈希不一致都重新上传完整单包，禁止绕过继续。

### 第三步：一条命令完成预检、备份、演练和切换

复制 `workbench-commands-<version>.txt` 的第二条命令即可；不要现场重新拼路径。

该脚本自动从生产读取旧 release、旧版本和旧 schema，不再手工抄参数；按固定顺序完成：

1. 旧生产 release/schema/health、三个服务、环境权限和全部发布物校验；
2. PostgreSQL、附件、环境、systemd、Nginx、旧 wheel 和即时回滚脚本的完整备份；
3. 新不可变 release/venv 准备和 package/server/SDK/MCP 版本核验；
4. PostgreSQL 可访问临时 dump 上的 `upgrade → downgrade → upgrade` 演练；
5. release 配置、systemd、Nginx 下载入口和生产 schema 更新；
6. 原子 `current` 指针切换，仅重启 AgentPost、reload Nginx；
7. 本机 health/ready 失败时自动回滚。

只有看到下面一行才表示切换成功：

```text
deploy_status=ok release=<version> commit=<commit> backup=<verified-backup-path> duration_seconds=<seconds>
```

在此之前失败时不得手工接着执行后半段；先确认旧生产仍健康，再修复固定脚本并重新生成/上传。

### 第四步：一条命令完成服务器和公网后检

复制 `workbench-commands-<version>.txt` 的第三条命令即可；不要现场重新拼路径。

切换脚本的每个 `deploy_step` 都带服务器时间，健康启动等待会安静重试，不再用重复的 curl 错误刷屏；
这让“仍在正常等待”和“已经停止”可以直接区分。

只有看到带 `duration_seconds` 的 `postflight_status=ok` 才能更新部署记录。随后用同一登录会话**新开
标签页**打开 Orbit 检查主流程，
并把真实 Agent 宿主接入、收发和跨设备测试继续单列为 `待确认`。

### SSH 何时替代 Workbench

只有部署专用公钥已经追加到 `admin`、主机指纹固定、`ssh` 与 `sudo -n true` 的只读探针明确通过后，
才把第二步替换为一次 `rsync`。构建、服务器切换脚本和后检脚本完全不变；不得在每次发布现场
重新试 SSH 登录。也就是说，SSH 只是未来更快的传输通道，不是另一套发布逻辑。

仓库根目录的 `scripts/deploy-production.sh` 是旧 Docker Compose 拓扑入口，默认会拒绝运行；当前
阿里云生产禁止使用它。

## 1. 0.1.14–0.1.19 发布暴露的问题

1. 本机 SSH 客户端能到达服务器，但没有服务器接受的身份；`root` 与 `admin` 公钥登录均失败。
2. 只能转用浏览器 Workbench 和命令助手。源码包与 688 KB wheel 被拆成 246 个片段上传，既慢，
   又消耗命令记录配额，还增加漏片、顺序和粘贴长度风险。
3. 每个版本在 Nginx 中使用一个精确 wheel 路径。0.1.14 第一次切换后，新服务健康，但新 wheel
   仍被旧白名单返回 404，触发了正确的自动回退。
4. 备份、canary、切换和 postflight 的判断本身有效，但当场生成并粘贴长脚本，重复劳动较多。
5. Workbench 适合紧急处置，不适合作为每次发布的主传输与编排通道；终端断开、分页器和浏览器
   输入长度都会放大操作成本。
6. 0.1.18 的 PostgreSQL 迁移演练最初直接读取 root-only 备份目录中的 dump。即使把 dump 本身交给
   `postgres`，父目录没有穿透权限仍会失败；不能靠反复放宽备份目录权限解决。
7. 正确做法是在保持正式备份目录 `0700 root:root`、dump `0600 root:root` 的前提下，用 `install`
   复制一份仅供演练的临时 dump 到 PostgreSQL 可访问目录，设置最小所有权/权限，演练后无论成功
   或失败都删除临时 dump 和临时数据库。
8. Workbench 终端粘贴多行脚本会出现“确认粘贴”弹窗；确认只代表内容进入终端，仍需检查是否已
   真正执行。发布脚本应优先作为完整文件上传，再以一条短命令做语法、哈希和显式确认参数检查。
9. 某一步在生产指针切换前失败时，应保留诊断备份并重新核对生产仍指向旧版本；已完成哈希校验的
   release/venv 可以在幂等条件成立时复用，但不能跳过备份、迁移演练或切换前状态核对。
10. 0.1.19 实际验证了 Workbench 文件选择器是单文件模式，“六个文件一次上传”的文字与工具能力
    不一致；逐文件选择会被上传任务浮层和提示气泡打断。
11. 0.1.19 在文件树里建立目标目录时，窄视口导致按钮在可视区外，目录缓存又需要折叠/展开刷新；
    这个步骤没有安全价值，应由 staging 命令确定性完成。
12. Workbench 直接上传的脚本没有保留可执行位，第一次切换在任何生产变更前以 `Permission denied`
    停止。上传包内保留模式，同时 staging 命令显式 `chmod 750`，以后不再现场排查。
13. 登录态旧标签可能保留发布前 JavaScript，即使服务端和公网资源已更新。生产 UI smoke 必须打开
    一个同会话的新标签页，不用旧标签刷新结果判断发布内容。

结论：不能为了“快”删掉保护门禁；当前无 SSH 时用单上传包消除目录操作和六次文件选择，完成
专用 SSH 验证后再把传输替换为 `rsync/SFTP`。

## 2. SSH 已完成一次性准备后的日常发布通道

### 一次性准备（需要用户单独授权）

1. 在本机生成星云驿部署专用密钥，私钥仅保存在本机并设置口令；不复用个人通用私钥。
2. 通过阿里云客户端或已登录的 Workbench，把**公钥追加**到服务器 `admin` 账户；不得替换现有
   `authorized_keys`。
3. 先只读验证 `ssh admin@112.124.33.54`、主机指纹和 `sudo -n true`，不立即发布。
4. 在本机 SSH 配置中固定主机名、用户、公钥路径与主机指纹；禁止关闭
   `StrictHostKeyChecking`。

不建议在轻量服务器控制台重新“绑定密钥对”。官方说明该动作会覆盖已绑定实例密钥，且需要重启
实例后生效；这会扩大日常发布的影响范围。阿里云客户端提供“追加 SSH 密钥”模式，更符合当前
已有 Workbench `admin` 用户和同机受保护服务的实际情况。

### 每次发布

1. **Prepare（本机）**
   - 从明确且干净的 Git 提交生成源码归档，不打包工作树。
   - 构建一个 wheel。
   - 生成一个 manifest，记录 commit、版本、Alembic head、两个文件的 SHA-256 和构建时间。
   - 运行 Ruff、受影响测试、Orbit JavaScript、MCP/SDK 和 PostgreSQL 门禁。
2. **Preflight（一次 SSH 调用，只读）**
   - 读取当前 release、systemd runtime、schema、关键数据量、端口、磁盘、环境权限。
   - 记录 AgentPost/Nginx/PostgreSQL 进程和受保护服务健康信号。
3. **Transfer（一次 rsync）**
   - 把源码归档、wheel 和 manifest 一次传到新的 staging 目录。
   - 在服务器端重新计算 SHA-256；不通过 Shell 参数传二进制，不拆 Base64 片段。
4. **Switch（一次 SSH 调用）**
   - 运行仓库版本化、root 拥有且不可由普通用户修改的参数化发布脚本。
   - 脚本完成备份校验、独立 venv 安装、迁移演练、canary、原子指针切换、AgentPost 重启、
     Nginx reload 和失败自动回退。
   - 迁移演练使用 PostgreSQL 可访问目录中的临时 dump，不修改正式备份目录的 root-only 边界；
     trap 必须清理临时数据库和临时 dump。
5. **Postflight（一次 SSH 调用 + 公网检查）**
   - 精确比较本机/公网 health 和 ready 的完整 JSON。
   - 核对 schema、数据量不减少、服务 PID 连续性、错误/5xx、wheel SHA、未知下载 404。
   - 记录备份与即时回退脚本路径，再更新交接文档。

正常情况下，SSH 路径的交互动作是一次构建、一次 rsync、一次受保护切换、一次后检；Workbench
路径是一次构建、一次单文件上传、一条 staging、一条切换、一条后检。网络、备份、依赖安装和迁移
演练时间仍存在，但 Workbench 人工操作目标应控制在 2–3 分钟，总发布通常 5–10 分钟。

## 3. Nginx 的一次性提效改造

当前每个 wheel 使用独立的 `location =`。后续可在一次单独授权、已备份的基础设施变更中改为：

```nginx
location ~ ^/downloads/agentpost-[0-9]+\.[0-9]+\.[0-9]+-py3-none-any\.whl$ {
    root /opt/agentpost/public;
    try_files $uri =404;
    default_type application/octet-stream;
    add_header Content-Disposition "attachment";
    add_header Cache-Control "public, max-age=300";
}

location /downloads/ { return 404; }
```

该规则只允许规范 wheel 文件名，文件不存在仍返回 404，不开放目录列表。完成实际 Nginx 语法、
旧 wheel、新 wheel、未知路径和回退验证后，应用发布不再需要逐版本改 Nginx。

## 4. 无 SSH 时的回退通道

- **Workbench**：用于首次追加公钥、紧急排障和回退。0.1.15 已验证其文件管理可一次上传完整的
  1.5 MB 源码归档和 672 KB wheel，明显优于命令助手分片；它仍是人工应急路径，不替代日常
  `rsync/SFTP` 自动化。
- **轻量应用服务器命令助手**：适合只读探针和短脚本。官方控制台“发送文件”要求文件不超过
  24 KB，因此不传 wheel 或源码归档。
- **SWAS OpenAPI `RunCommand`**：可以把固定预检/后检脚本改为 API 调用并查询执行结果；如使用
  阿里云 CLI，优先使用 OAuth 或 RAM 角色/STS 临时凭据；确需长期 AccessKey 时只能使用最小权限
  RAM 子用户并保存在本机安全存储中，不进入 Git。
- **SFTP**：当 rsync 不可用时，用阿里云客户端 SFTP 传完整发布物，仍需在服务器校验 SHA。

Workbench 回退发布按以下顺序执行：

1. 文件管理只上传 `agentpost-<version>-aliyun-upload.tar.gz` 到 `/home/admin`；不在界面建目录，
   不逐个上传内部文件，不上传环境文件、私钥或数据库备份。
2. 终端复制生成的 staging 单行命令，自动创建目录并运行外层/内层 SHA-256、`bash -n` 和权限修正。
   如需粘贴多行只读探针，处理“确认粘贴”后还要
   再按一次执行键并观察 shell prompt/退出状态；切换命令保持单行、短且带显式确认参数。
3. 先运行只读 preflight，再运行受保护切换脚本。脚本输出必须有可检索的步骤标记、最终 release、
   commit、备份路径和成功/回退状态。
4. 若在 switch 前失败，立即核对 `current`、schema、三个服务和本机 health/ready 仍是旧基线；
   失败目录只作诊断证据，不得标记成有效回滚点。
5. 修复脚本后重新上传并校验脚本 SHA。仅当源码、wheel、manifest 和既有 release/venv 仍与目标
   commit 精确一致时才可复用 staging；新的正式尝试必须生成新的完整备份和回滚脚本。
6. 成功后从服务器本机和开发机公网分别做 postflight，再打开有登录态的 Orbit 做 UI smoke；
   浏览器能渲染不等于真实 Agent 宿主已经完成接入。

## 5. 安全与权限边界

- 新增 SSH 公钥、RAM 身份、Nginx 稳定下载规则和服务器端常驻发布脚本都是单独的生产变更，必须
  明确授权后执行。
- 私钥、AccessKey、环境文件、数据库转储和 Workbench 会话信息不得进入仓库、聊天或命令输出。
- 常规发布仍只重启 AgentPost、reload Nginx；不重启 PostgreSQL、OpenClaw Gateway 或整机。
- `deployed_https_verified` 与真实双 Human、移动端和重启恢复验收继续分开。

## 6. 每次发布的证据清单

发布结束前必须留下以下不含秘密的证据：

- 目标 commit、package/server/SDK/MCP 版本、源码与 wheel SHA-256；
- 发布前后 `current`、Alembic revision、关键表计数、磁盘和环境文件权限；
- AgentPost、Nginx、PostgreSQL 状态和 PID，明确哪些进程允许变化；
- 正式备份目录、dump/list、附件 archive/list、受保护配置、旧 wheel、校验和与即时回滚脚本；
- 临时迁移数据库完成 upgrade/downgrade/upgrade，且临时数据库和 dump 已清理；
- 本机与公网 health/ready、公开 wheel 哈希、未知下载 404、Nginx 语法、切换后 warning/error；
- 登录态 Orbit 主流程 smoke，以及尚未执行的真实 Human/Agent/跨设备验收。

只有前述生产检查通过才能写 `deployed_https_verified`。真实宿主保存、tools/list、收发、重启恢复
或跨 Human 行为未由测试人员完成时，必须继续标为 `待确认`，不得写成 `production_accepted`。

## 7. 官方依据

- [轻量应用服务器：远程连接 Linux 服务器](https://help.aliyun.com/zh/simple-application-server/user-guide/connect-to-linux-server-remotely)
- [轻量应用服务器：通过命令助手上传文件](https://help.aliyun.com/zh/simple-application-server/user-guide/upload-files-to-the-lightweight-application-server)
- [轻量应用服务器：命令助手 OpenAPI](https://help.aliyun.com/zh/simple-application-server/developer-reference/api-swas-open-2020-06-01-dir-command-assistant/)
- [阿里云客户端管理轻量应用服务器与追加 SSH 密钥](https://help.aliyun.com/zh/simple-application-server/user-guide/manage-lightweight-application-servers-through-alibaba-cloud-clients)
- [轻量应用服务器：管理密钥对](https://help.aliyun.com/zh/simple-application-server/user-guide/manage-key-pairs-linux)
- [阿里云 CLI：快速开始与 OAuth 凭据](https://help.aliyun.com/zh/cli/quickly-start-using-alibaba-cloud-cli)
- [阿里云 CLI：RAM 角色临时凭据](https://help.aliyun.com/zh/cli/ram-role-credentials)
