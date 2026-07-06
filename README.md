# KnowledgeAssistant

KnowledgeAssistant 是一个面向企业知识问答场景的前后端分离项目，围绕文档入库、混合检索、结构化回答、审核流转和会话记忆构建完整的问答闭环。

项目后端基于 FastAPI、LangGraph 和 LangChain，前端基于 Next.js、React 和 TypeScript，支持多会话聊天、SSE 流式回答、人工审核和 PDF 导出。

## 功能特性

- 文档入库：支持将本地文档切分为知识片段并写入向量库，同时保存标题、章节、页码等元数据
- 混合检索+专有词典：结合向量检索、关键词检索、Query 扩展和重排序返回证据片段，专有词典进行扩展和同义替换
- 结构化问答：输出结论、依据、引用和证据缺口等结构化内容
- 审核机制：根据证据数量、召回分数和来源一致性决定自动通过或进入人工审核
- 会话记忆：维护当前会话的主题、近期问题、已确认答案和摘要上下文
- 流式输出：通过 SSE 持续推送回答生成过程
- PDF 导出：支持将回答内容导出为 PDF

## 技术栈

- 后端：Python、FastAPI、LangGraph、LangChain、ChromaDB、Redis
- 前端：Next.js、React、TypeScript、Tailwind CSS
- 模型接入：OpenAI 兼容接口、OneAPI、Ollama

## 项目结构

```text
KnowledgeAssistant/
├─ backend/
│  ├─ app.py                    # FastAPI 服务入口
│  ├─ index_documents.py        # 文档入库脚本
│  ├─ chat_cli.py               # 终端多轮问答入口
│  ├─ config.py                 # 后端配置
│  ├─ retrieval/                # 入库、检索、重排、Query 扩展
│  ├─ workflows/                # LangGraph 工作流
│  ├─ orchestration/            # Prompt 链与编排逻辑
│  ├─ review/                   # 审核规则与审核任务
│  ├─ memory/                   # 会话记忆
│  ├─ cache/                    # Redis 缓存封装
│  ├─ tools/                    # PDF 导出等工具
│  ├─ models/                   # 数据模型
│  └─ data/
│     ├─ input/                 # 待入库文档
│     ├─ chroma/                # 向量库数据
│     ├─ memory/                # 会话记忆数据
│     ├─ observability/         # 运行观测数据
│     └─ reports/               # 导出的 PDF 文件
├─ frontend/
│  ├─ src/app/                  # Next.js 页面入口
│  ├─ src/components/           # 聊天、证据、记忆、审核界面
│  ├─ src/lib/                  # API、SSE、类型定义
│  └─ src/styles/               # 全局样式
└─ README.md
```

## 运行方式

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

后端至少需要配置模型与 Embedding 相关环境变量，常用项如下：

```bash
LLM_TYPE
ONEAPI_API_BASE
ONEAPI_API_KEY
ONEAPI_MODEL_NAME
EMBEDDING_API_BASE
EMBEDDING_API_KEY
EMBEDDING_MODEL_NAME
REDIS_URL
```

前端可按需配置后端地址：

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8014
```

### 3. 文档入库

将待入库文件放到 `backend/data/input/`，然后执行：

```bash
cd backend
python index_documents.py
```

### 4. 启动后端服务

```bash
cd backend
python app.py
```

默认地址：

```text
http://127.0.0.1:8014
```

### 5. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:3001
```

### 6. 使用终端模式

如果只想在终端里进行多轮问答，可以运行：

```bash
cd backend
python chat_cli.py
```

## 主要接口

- `POST /v1/assistant/run`：同步执行问答流程
- `GET /v1/assistant/run/stream`：SSE 流式执行问答流程
- `POST /v1/assistant/feedback`：提交人工审核结果
- `POST /v1/assistant/export-pdf`：导出回答为 PDF
- `GET /v1/memory/sessions/{session_id}`：获取会话记忆
