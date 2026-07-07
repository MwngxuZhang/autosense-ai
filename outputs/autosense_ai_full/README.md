# AutoSense AI 动态应用

这是 AutoSense AI 的完整可运行版本，包含 Python 后端、SQLite 数据库、前端工作台、市场抓取、DeepSeek API 调用、资料依据库和协同接口。

## 运行

```powershell
python server.py
```

打开：

```text
http://127.0.0.1:8765
```

## 用户自配 API

页面 `API配置` 支持用户填写自己的 DeepSeek Key。Key 只保存在当前浏览器，请求时通过请求头临时传给后端，不会写入仓库或公共服务端配置。

本地开发也可以复制 `.env.example` 为 `.env`，配置服务端专用 Key：

```powershell
Copy-Item .env.example .env
```

## 已实现能力

1. 工作台：展示产品经理最常用的判断入口、当前机会和推荐动作。
2. 市场雷达：抓取公开市场信号，完成摘要、分类、标签和机会评分。
3. 决策中心：整合证据链、市场地图、竞品威胁和产品动作。
4. 需求分析：把市场线索或客户表达拆解为可执行产品需求。
5. 竞品对比：维护竞品参数、公开客户、技术路线和 Battlecard。
6. 产品方案：基于需求、竞品、资料依据库和我方产品画像生成方案草案。
7. 资料依据库：沉淀产品手册、测试说明、客户纪要和方案备忘录。
8. 产品画像：支持产品线和目标客户画像的模块化新增、删除和保存。
9. 协同推进：支持 Jira、飞书、CRM、Slack Webhook；未配置时进入本地待推送队列。

## 主要接口

```text
GET  /api/health
GET  /api/config
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
