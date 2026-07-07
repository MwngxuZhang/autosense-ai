# AutoSense AI 竞品功能补齐与差异化技术文档

## 1. 产品目标

AutoSense AI 不做泛行业市场情报工具，而做面向 RoboSense 速腾聚创车载智驾传感器产品团队的垂直产品决策工作台。

目标是把公开市场信号、竞品动态、客户线索、我方产品画像和 AI 分析连接成一个可运行闭环：

市场信号发现 -> 证据链分析 -> 客户需求拆解 -> 竞品作战卡 -> 我方产品匹配 -> 产品方案 -> 验收指标 -> 路线图动作。

## 2. 可对外说明的差异化亮点

### 2.1 垂直行业上下文

竞品平台通常面向泛行业市场研究或通用产品管理。AutoSense AI 内置车载激光雷达和高阶智驾语义，包括 L2+/L3、NOA、Robotaxi、补盲、车规可靠性、功能安全、量产定点、OEM 供应链等字段。

对外说明时可解释为：系统不是简单总结新闻，而是知道产品经理需要判断客户场景、量产节奏、关键规格、研发风险和验收指标。

### 2.2 证据链产品结论

借鉴 AlphaSense 的可引用答案能力，但输出不是普通摘要，而是把每条结论拆成：

1. 市场事实
2. 产品推断
3. 对速腾产品线影响
4. 待确认问题
5. 来源链接

这样可以降低 AI 幻觉风险，也方便产品经理向研发、销售和管理层解释依据。

### 2.3 智驾传感器竞品作战卡

借鉴 Crayon 和 Klue 的 Battlecard，但不是销售话术工具，而是围绕车载传感器产品竞争：

1. 竞品关键参数
2. 公开客户和量产状态
3. 技术路线威胁
4. 我方可反击点
5. 售前技术交流建议
6. 需要研发确认的风险

### 2.4 客户信息完整性门禁

借鉴 Productboard 的客户反馈归类，但增加硬件产品经理必须关注的客户字段门禁。

当信息不完整时，系统不会直接生成确定方案，而是先指出缺失字段，例如车型平台、量产时间、目标成本、可靠性要求、竞品供应商状态、交付物要求。

### 2.5 产品路线图动作

借鉴 Aha! 的路线图能力，但输出不是通用 Roadmap，而是面向激光雷达产品生命周期：

1. 研发验证动作
2. 测试验收动作
3. 售前资料动作
4. 商务风险动作
5. 客户确认动作

## 3. 功能补齐范围

### P0 本次实现

1. 新增“差异化亮点”页面，清晰展示产品特殊性和可讲述理由。
2. 新增“决策中心”页面，把机会、需求、竞品、方案整合为一张产品决策看板。
3. 新增后端 `/api/decision-center`，生成：
   - evidence_chain
   - battlecards
   - requirement_prioritization
   - roadmap_actions
   - differentiation
4. 优化竞品页，增加 Battlecard 和对速腾影响。
5. 优化方案页，增加方案生成依据和路线图动作。
6. 优化评测页，突出证据链、可追溯率、客户字段完整性。

### P1 后续增强

1. 商业搜索 API 接入后，补充更多官网、财报、专利和招聘数据源。
2. 增加客户需求池的人工确认状态和协同负责人。
3. 增加路线图版本管理。
4. 增加导出 PRD、售前 Battlecard、评审纪要。

### P2 生产化方向

1. 接入 CRM、Jira、飞书、Slack 的真实 webhook。
2. 增加定时推送订阅规则。
3. 增加多角色权限。
4. 增加 AI 输出人工采纳率和反馈学习。

## 4. 后端设计

### 4.1 `/api/decision-center`

方法：GET

输出字段：

```json
{
  "differentiation": [],
  "evidence_chain": [],
  "battlecards": [],
  "requirement_prioritization": [],
  "roadmap_actions": [],
  "executive_answer": ""
}
```

### 4.2 Evidence Chain

每条证据链基于市场新闻生成：

1. fact：新闻事实
2. inference：产品推断
3. impact：对速腾产品影响
4. source：来源
5. next_question：下一步确认问题

### 4.3 Battlecard

基于 competitors 表生成：

1. competitor
2. product
3. threat
4. likely_customer_argument
5. robosense_response
6. proof_needed

### 4.4 Requirement Prioritization

基于 requirements 表生成优先级卡片：

1. requirement_id
2. customer
3. priority_score
4. why_now
5. missing_fields
6. next_action

### 4.5 Roadmap Actions

基于最新需求、方案和竞品生成产品动作：

1. action
2. owner
3. evidence
4. urgency
5. output

## 5. 前端设计

### 5.1 新增导航

1. 决策中心
2. 差异化亮点

### 5.2 决策中心页面

页面结构：

1. 产品价值说明卡：这个产品特殊在哪里？
2. 证据链市场结论
3. 竞品 Battlecard
4. 需求优先级
5. 路线图动作

### 5.3 差异化亮点页面

页面结构：

1. 泛市场情报工具 vs AutoSense AI
2. 通用产品管理工具 vs AutoSense AI
3. 普通 AI 摘要 vs AutoSense AI
4. 我们的不可替代点

## 6. 验收标准

1. 网页不出现个人求职相关字样作为主产品文案。
2. 用户打开首页即可看到自动情报和产品决策闭环。
3. 决策中心无需用户手工输入网页即可生成内容。
4. 竞品页能展示结构化 Battlecard。
5. 差异化页面能清晰回答“为什么不是普通 AI 摘要工具”。
6. 后端 API 在无 DeepSeek Key 时仍可基于规则生成稳定结果。
7. 有 DeepSeek Key 时，市场情报、需求拆解和方案生成继续使用真实接口。
