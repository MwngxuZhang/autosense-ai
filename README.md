# AutoSense AI

面向车载激光雷达产品团队的 AI 产品决策工作台。

AutoSense AI 服务产品经理、战略市场、售前方案和研发协同场景，将公开市场情报、竞品动态、客户字段完整性和我方产品画像整合起来，帮助团队完成机会判断、需求拆解、竞品应对、产品方案生成和协同推进。

## 项目入口

应用代码位于：

```text
outputs/autosense_ai_full
```

运行方式：

```powershell
cd outputs/autosense_ai_full
python server.py
```

打开：

```text
http://127.0.0.1:8765
```

## 核心模块

- 工作台：核心使用路径、当前重点机会、产品动作入口。
- 市场雷达：公开市场情报抓取、摘要、分类和机会评分。
- 决策中心：证据链结论、市场地图、情报简报、Win/Loss 复盘、供应商评分卡。
- 需求分析：客户信息完整性、应用场景、性能需求、风险和待确认问题。
- 竞品对比：竞品技术路线、感知能力、车规可靠性、公开客户和 Battlecard。
- 产品方案：产品定位、研发任务、验收指标和风险提示。
- 资料依据库：保存产品手册、测试说明、客户纪要和方案备忘录，支持基于资料问答。
- 产品画像：产品线和目标客户模块化维护。
- 协同推进：支持 Jira、飞书、CRM、Slack Webhook。

## 相关文档

- `outputs/AutoSense_AI_项目调研报告.md`
- `outputs/AutoSense_AI_类比竞品调研报告.md`
- `outputs/AutoSense_AI_真实运行版技术文档.md`
- `outputs/AutoSense_AI_P0_P1_P2能力补齐技术文档.md`
- `outputs/AutoSense_AI_产品经理简历项目包装.md`

## 安全说明

真实 API Key 只应写入本地 `.env`，不要提交到 GitHub。仓库中提供 `.env.example` 作为配置模板。

