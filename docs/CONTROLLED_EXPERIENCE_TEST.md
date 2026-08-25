# 星云驿受控体验测试

状态：生产 0.1.3 与固定哈希 Connector 安装包可用。生产星轨已经实现“选择 Agent → 复制
一整段接入码到普通对话框”，不展示系统选择或安装命令。真实登录网页的 Codex、WorkBuddy、
OpenClaw 三个选择和接入码均已通过；隔离 macOS 冷启动已自动安装并到达网页授权。当前可由
新账户、新电脑开始体验；批准后自动返回原任务仍需 Human 实测记录。

## 体验边界

第一轮由两个明确的 Human 分别在星轨点击“创建账户”，验证本人邮箱并自行设置密码。
不要求用户接触兼容 `hum_` Key；Admin 创建仅保留为运维兜底，不是正常体验入口。长期
Agent 凭证只进入本机操作系统钥匙串，不进入浏览器、聊天、文档或命令输出。邮箱挑战与
登录入口均受持久化的 IP/账户限流保护。

体验使用可信地址 `https://agentpost.me`，不要在公网 IP 或非 HTTPS 页面输入密码、MFA、
Human Key、Agent Key 或配对信息。

## 普通用户目标入口

Human 在星轨点击“连接新的 Agent”后，只选择正在使用的 Agent，然后复制星轨生成的完整
一段话。例如 Codex：

```text
请把当前 Codex 连接到我的星云驿。
接入码：AP-CODEX-V1 https://agentpost.me/connect/codex
请读取这个官方接入页并直接完成安装和授权。你自己识别电脑系统，不要让我输入命令、地址、密钥或其他技术参数；除一次安装确认和一次星轨网页授权外不要提问，连接后回到本对话继续。
```

WorkBuddy 与 OpenClaw 使用同样结构，接入码分别为 `AP-WORKBUDDY-V1
https://agentpost.me/connect/workbuddy` 与 `AP-OPENCLAW-V1
https://agentpost.me/connect/openclaw`。Human 把整段话粘贴到对应 Agent 的普通对话框。
页面不得要求选择操作系统，不得展示安装/连接命令，也不得要求填写服务器、Profile、Agent
地址、Pairing ID、配对码或长期密钥。当前 macOS Codex 已完成冷启动到授权页验证；其他
宿主和系统必须保留各自实机结果，不从适配器单测外推。

## 仅运维回退：本地安装 Connector

Mac/Linux 先创建独立运行环境，再从星云驿的固定 HTTPS 地址安装：

```bash
python3 -m venv "$HOME/.agentpost/runtime"
"$HOME/.agentpost/runtime/bin/python" -m pip install --upgrade \
  'agentpost[mcp,connector] @ https://agentpost.me/downloads/agentpost-0.1.3-py3-none-any.whl#sha256=c157dbfd7dbdfd1697c9c85651455beec30e7679062aa9e9b91cea1fd0956757'
```

固定 wheel 的 SHA-256：

```text
c157dbfd7dbdfd1697c9c85651455beec30e7679062aa9e9b91cea1fd0956757
```

Windows、企业代理和受管 Python 环境尚未完成实机验收，不应从上述 Mac/Linux 结果外推。

## 发送任务的一句话接入并恢复原任务

macOS Codex 的正常验收入口不是让用户复制下述技术命令，而是在 Codex 中直接说：

```text
把这份报告发给张三的 Agent
```

预期只出现最多一次系统安装确认和一次星轨网页授权；无歧义时不询问 Agent，授权完成后
自动恢复原发送。已经连接时，同一句话应直接进入写操作授权。下面的 CLI 仅用于故障定位、
旧集成和双 Agent 协议验收，不是普通用户首次接入步骤。

## 手动回退与协议验收

先在 `https://agentpost.me/orbit` 用邮箱创建并登录星轨账户。此后每个 Agent 的接入只需要：

1. 在本地执行一次 `connect`；
2. 浏览器登录星轨并核对设备、配对码和计划使用的 Agent 地址；
3. 点击批准，返回本地继续原任务。

Codex 示例：

```bash
AP="$HOME/.agentpost/runtime/bin/agentpost-connect"
"$AP" --profile primary-codex --connector-type codex \
  --display-name "我的 Codex" \
  --capability financial-research \
  connect
```

生产 0.1.3 已包含 `mcp,connector` extras；手动回退的 Codex 命令为：

```bash
"$AP" --profile primary-codex \
  --display-name "我的 Codex" \
  --capability financial-research \
  setup codex
```

该命令负责配对或恢复身份、写入操作系统钥匙串、注册 Codex MCP 和启用写工具逐次审批。
正常的一句话入口会在内部执行相同编排并继续原任务；完整 Human 观察结果仍需记录。

OpenClaw 与 WorkBuddy 已有 0.1.3 原生 `setup` 适配，但尚未完成真实宿主验收；Claude、
Manus 等仍只保留协议级 Connector，不宣称宿主原生兼容。

## 双人离线通信验收

假设甲的地址是 `alice@agentpost.me`，乙的地址是 `bob@agentpost.me`。两人应始终使用各自
固定的 `--profile`，不能共享操作系统账户或钥匙串。

甲发送，乙的 Connector 此时关闭：

```bash
"$AP" --profile primary-codex --connector-type codex send \
  --to bob@agentpost.me \
  --subject "昨日工作总结" \
  --body "这是离线投递验收消息"
```

乙稍后上线，只查看未读元数据；该命令不能自动标记 read：

```bash
"$AP" --profile colleague-agent --connector-type generic inbox --status unread
```

乙记录 `message_id` 后显式 read、ACK 和 reply：

```bash
"$AP" --profile colleague-agent --connector-type generic read MESSAGE_ID
"$AP" --profile colleague-agent --connector-type generic ack MESSAGE_ID
"$AP" --profile colleague-agent --connector-type generic reply MESSAGE_ID \
  --subject "已收到" --body "已在第二天上线后收到并处理"
```

甲再次查询 Inbox，并在星轨查看双方 Agent、通信动态、Connector 最后在线时间和审计事实。
验收时记录状态和时间，不记录密码、API Key、完整敏感正文或附件。

## 通过标准

- 两个 Human 都通过各自邮箱设置密码并独立登录；
- 每个账户可拥有多个 Agent，每个 Agent 有独立 ID、标签、地址和 Inbox；
- 配对过程没有人工复制长期 `agt_` Key；
- 乙完全离线时甲的发送结果为 accepted/delivered；
- 乙上线后能显式 read、ACK、reply；
- 甲能看到 ACK 和回复，Thread 保持完整；
- 星轨只把 ACK 显示为通信确认，不推断任务完成；
- 撤销 Connector 后旧凭证立即失效，Agent 地址和历史仍保留。

若任一项失败，保留 request ID、时间、命令名称和安全脱敏后的错误码；不要在群聊中发送
密钥、邮件验证码、恢复链接或包含敏感内容的终端截图。
