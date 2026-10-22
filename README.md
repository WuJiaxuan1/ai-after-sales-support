# AI售后客服分流系统

面向售后咨询的双角色原型：普通问题由 AI、知识检索和业务流程处理；安全风险、权限边界或用户明确要求人工时，创建真实的人工接管记录，并向客服交接上下文。

本项目来自小米 AI Native 工程师训练营实践。本仓库整理了可运行源码、设计说明、规则回归测试和开发过程记录。

## 主要功能

| 场景 | 系统行为 |
| --- | --- |
| 售后规则与常见故障咨询 | 检索本地知识库，组织回答，继续自动服务 |
| 自由文本选择业务路径 | AI 提出既有流程中的候选路径，后端校验后由用户确认 |
| 明确或疑似安全风险 | 创建人工接管记录，进入 P0 队列并保留风险依据 |
| 找人工、权限或能力边界 | 交接用户原话、对话历史、业务路径和判断依据 |
| 人工客服工作台 | 查看队列、接单、回复和解决状态，以及交接包和审计记录 |

核心设计是 **AI Judgment ≠ Business Action**：AI 输出理解、检索结果和结构化判断；实际工单、优先级和状态变更由后端规则执行。

## 技术实现

- 后端：Python、FastAPI、Pydantic、HTTPX。
- 前端：Vue 3、Vite、Pinia、Vue Router、Axios。
- 检索：本地 Markdown 知识库与轻量 TF-IDF 检索。
- 模型：MiMo / OpenAI 兼容接口；没有密钥或模型不可用时使用现有规则与降级逻辑。
- 验证：pytest、FastAPI TestClient，以及双端人工回归。

## 开发重点

- 业务问题定义、AI 与人工的能力边界、流程分类及方案取舍。
- 基于初始 MVP 重构候选路径确认、RAG 调用时机、安全判断、人工交接和客服状态约束。
- 通过用户端与客服端验证 Case、Queue、Handoff Packet 和 Audit，核对业务动作是否发生。
- 修复知识咨询被误转人工、回复暴露内部知识库措辞等问题，并整理流程规范和实现文档。

## 本地运行

需要 Python 3.10 或更新版本，以及兼容 Vite 5 的 Node.js。以下示例使用 Windows PowerShell，在仓库根目录执行。

### 1. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/server/requirements.txt
```

### 2. 启动后端

```powershell
# 可选：在当前终端设置自己的模型密钥。
# 未设置密钥也可体验规则流程，但不代表已验证真实模型能力。
$env:MIMO_API_KEY = "填写你自己的密钥"

cd src
..\.venv\Scripts\python.exe -m uvicorn server.main:app --reload --port 8000
```

使用规则模式时，跳过设置密钥那一行即可。模型服务地址和模型名称可分别通过 `MIMO_BASE_URL` 与 `MIMO_MODEL` 环境变量覆盖。本项目直接读取环境变量，不会自动加载 `.env` 文件。

### 3. 启动前端

另开一个 PowerShell，在仓库根目录执行：

```powershell
cd src/client
npm ci
npm run dev
```

| 地址 | 用途 |
| --- | --- |
| http://localhost:5173/user | 用户咨询页面 |
| http://localhost:5173/agent | 人工客服工作台 |
| http://localhost:8000/docs | 后端 API 文档 |

## 演示路径

1. 用户端输入“我要看退货规则”，检查是否继续提供规则咨询。
2. 新建会话输入“我的充电宝爆了”，在客服端检查真实 P0 队列和交接包。
3. 新建会话输入“没有冒烟，只是开不了机”，检查否定语境是否避免误触发 P0。
4. 输入“找真人”，在客服端接单、回复，再标记解决，观察状态和审计变化。

更多验证方法见 [测试说明](docs/validation.md)。

## 自动化测试

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd src
..\.venv\Scripts\python.exe -m pytest tests -q
```

现有 7 项测试覆盖安全风险、否定语境、真实人工队列、权限边界、退款意图和候选路径合法性，不调用外部模型。

## 目录

```text
ai-after-sales-support/
├── README.md
├── requirements-dev.txt
├── docs/                    # 公开设计、验证和开发过程
└── src/
    ├── client/              # 用户端与客服端
    ├── server/              # API、流程、AI 适配器与模拟业务数据
    ├── knowledge-base/      # 售后政策、故障处理与安全知识
    ├── skills/              # 原项目的模块职责与行为规范
    └── tests/               # 规则与接口回归测试
```

## 当前边界

- 这是团队训练原型，尚未接入真实订单、退款资金流和审批系统。
- 业务数据为模拟数据；工单、会话和审计记录保存在内存，重启后清空。
- 规则降级的正确结果与真实模型的判断效果需要分别验证。
- 尚未提供生产环境的持久化、多客服权限与高并发能力。

## 项目文档

- [系统设计](docs/design.md)
- [测试说明](docs/validation.md)
- [开发过程记录](docs/progress.md)
