# AutoSense AI

AutoSense AI 是一个面向车载激光雷达产品团队的 AI 产品决策工作台，服务产品经理、战略市场、售前方案和研发协同场景。系统将公开市场情报、竞品动态、客户字段完整性和我方产品画像整合起来，帮助团队完成机会判断、需求拆解、竞品应对、产品方案生成和协同推进。

## 运行

```powershell
cd C:\Users\ADMIN\Documents\Codex\2026-07-02\new-chat\outputs\autosense_ai_full
python server.py
```

打开：

```text
http://127.0.0.1:8765
```

## API Key配置

方式一：在页面左侧打开“API配置”，直接填写 DeepSeek API Key，然后点击“保存配置”和“测试连接”。

方式二：复制 `.env.example` 为 `.env`，按需填写：

```powershell
Copy-Item .env.example .env
```

支持：

- `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`：DeepSeek API，兼容OpenAI格式。
- `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`：OpenAI或其他兼容网关。
- `NEWS_API_KEY`：NewsAPI。
- `BING_SEARCH_API_KEY`：Bing News Search。
- `SERPAPI_KEY`：SerpAPI Google News。
- `JIRA_WEBHOOK_URL`、`FEISHU_WEBHOOK_URL`、`CRM_WEBHOOK_URL`、`SLACK_WEBHOOK_URL`：外部协同Webhook。

没有配置 Key 时，系统会自动使用本地规则兜底，核心页面仍能跑通。

## 已实现功能

1. 工作台：首页聚合核心使用路径、当前重点机会、产品动作入口和运行快照。
2. 市场雷达：支持公开 RSS、搜索 API 和重点页面抓取，结合 AI/规则进行分类、摘要和机会评分。
3. 决策中心：输出证据链市场结论、市场地图、情报简报、Win/Loss 复盘、供应商评分卡和路线图动作。
4. 需求分析：将高机会线索拆解为客户信息完整性、应用场景、性能需求、风险和待确认问题。
5. 竞品对比：以产品化卡片展示竞品技术路线、感知能力、车规可靠性、公开客户和 Battlecard。
6. 产品方案：基于产品画像、客户需求、竞品证据和资料依据库生成产品定位、研发任务、验收指标和风险。
7. 资料依据库：沉淀产品手册、测试说明、客户纪要和方案备忘录，并支持基于资料问答。
8. 产品画像：支持产品线和目标客户模块化维护，可添加、删除和保存。
9. 协同推进：支持 Jira、飞书、CRM、Slack Webhook；未配置时进入本地待推送队列。

## 主要接口

```text
GET  /api/health
GET  /api/config
POST /api/config
POST /api/ai/test
GET  /api/monitor
POST /api/monitor/config
POST /api/monitor/run
POST /api/monitor/start
POST /api/monitor/stop
GET  /api/news
POST /api/news/ingest-search
POST /api/news/ingest-rss
POST /api/crawl
GET  /api/competitors
GET  /api/requirements
POST /api/requirements
GET  /api/proposals
POST /api/proposals
POST /api/documents
POST /api/documents/delete
POST /api/rag/query
GET  /api/evaluations
POST /api/integrations/send
```

## 项目亮点

- 面向真实产品团队的工作流，而不是单纯的信息流或 AI 摘要页面。
- 将市场机会、竞品应对、客户字段完整性、产品方案和协同动作串成闭环。
- 支持 DeepSeek API 接入，同时提供本地规则兜底，降低演示和运行风险。
- 页面信息架构按照“判断机会 -> 形成依据 -> 输出方案 -> 推进协同”组织，降低上手成本。
