# AI售后客服分流系统

面向售后咨询的 AI 应用，将知识检索、业务流程、安全判断和人工接管连接起来。系统提供用户咨询页面和人工客服工作台：普通问题继续自动处理，需要人工介入时创建真实的交接记录，并保留此前的对话与判断依据。

项目在小米 AI Native 工程师训练营期间开展，重点探索 AI 判断如何与可校验的业务流程配合。

## 核心功能

| 功能 | 实现方式 |
| --- | --- |
| 售后知识问答 | 检索本地政策与故障知识，组织客服回答 |
| 自由文本分流 | 将问题映射到既有业务流程，校验候选路径并请求用户确认 |
| 安全风险处理 | 识别明确或疑似风险，创建 P0 人工接管记录 |
| 人工接管 | 处理主动找人工、权限不足、能力不足或自动处理无进展等情况 |
| 客服工作台 | 查看队列、交接包和对话，完成接单、回复与解决 |
| 状态与审计 | 记录工单状态、优先级和操作过程，检查业务动作是否实际发生 |

## 设计思路

**模型提出判断，后端规则执行业务动作。** 模型负责理解、候选路径和检索回答；流程校验、真实交接、优先级和工单状态由后端控制。

- 候选路径必须属于已有流程，并经用户确认后写入正式状态。
- 普通知识咨询可以直接检索回答，避免无必要的人工转接。
- 安全风险触发真实 P0 交接，客服端可以检查对应工单和风险依据。
- 人工接管时保留用户原话、历史对话、已走流程和判断信息。
- 使用 Case、Queue、Handoff Packet 和 Audit 核验结果，区分模型回答与实际业务状态。

详细实现见 [系统设计](docs/design.md)，迭代过程见 [开发记录](docs/progress.md)。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 后端 | Python、FastAPI、Pydantic、HTTPX |
| 前端 | Vue 3、Vite、Pinia、Vue Router、Axios |
| 知识检索 | Markdown 知识库、轻量 TF-IDF RAG |
| 模型接入 | MiMo / OpenAI 兼容接口，支持规则降级 |
| 回归测试 | pytest、FastAPI TestClient |

## 本地启动

需要 Python 3.10 或更新版本，以及兼容 Vite 5 的 Node.js。以下命令使用 Windows PowerShell，从仓库根目录开始执行。

### 1. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/server/requirements.txt
```

### 2. 启动后端

```powershell
cd src
..\.venv\Scripts\python.exe -m uvicorn server.main:app --reload --port 8000
```

默认不需要模型密钥，可以体验现有规则与降级流程。需要使用模型时，在启动后端的同一个终端中，先设置自己的密钥：

```powershell
$env:MIMO_API_KEY = "填写你自己的密钥"
```

`MIMO_BASE_URL` 和 `MIMO_MODEL` 可分别覆盖服务地址和模型名称。配置直接读取环境变量，不自动加载 `.env` 文件。

### 3. 启动前端

另开一个 PowerShell，在仓库根目录执行：

```powershell
cd src/client
npm ci
npm run dev
```

| 页面 | 地址 |
| --- | --- |
| 用户咨询 | http://localhost:5173/user |
| 人工客服工作台 | http://localhost:5173/agent |
| 后端 API 文档 | http://localhost:8000/docs |

## 演示案例

分别新建会话输入以下内容，同时观察用户端和客服端：

| 输入 | 检查内容 |
| --- | --- |
| 我要看退货规则 | 是否继续回答规则咨询 |
| 我的充电宝爆了 | 是否出现真实 P0 工单及交接包 |
| 没有冒烟，只是开不了机 | 是否正确处理否定语境，避免误触发 P0 |
| 找真人 | 是否进入人工队列，以及能否接单、回复并解决 |

模型模式和规则模式需要分别验证，具体结果应结合工单状态与审计记录判断。

## 自动化测试

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd src
..\.venv\Scripts\python.exe -m pytest tests -q
```

现有 7 项测试覆盖安全风险、否定语境、真实人工队列、权限边界、退款意图和候选路径合法性。测试方式、历史记录与本次检查范围见 [验证说明](docs/validation.md)。

## 项目结构

- `src/server/`：API、流程规则、模型适配器与模拟业务数据。
- `src/client/`：用户咨询页面与人工客服工作台。
- `src/knowledge-base/`：售后政策、故障处理与安全知识。
- `src/skills/`：模块职责与行为规范。
- `src/tests/`：规则与接口回归测试。
- `docs/`：设计、验证和开发过程说明。

## 当前限制

业务数据为模拟数据，尚未接入真实订单、退款资金流和审批系统。工单、会话和审计记录保存在内存中，后端重启后清空。目前未提供生产环境的持久化、多客服权限与高并发支持。
