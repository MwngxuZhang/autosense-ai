const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
};

const state = { news: [], competitors: [], requirements: [], proposals: [], evaluations: [], documents: [], config: {}, monitor: {}, profile: {}, opportunities: [], decision: {} };

function goView(view) {
  const btn = document.querySelector(`.nav[data-view="${view}"]`);
  if (btn) btn.click();
}

document.querySelectorAll(".nav").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $(btn.dataset.view).classList.add("active");
    const titles = {
      dashboard: ["工作台", "面向智驾传感器产品团队的市场机会与产品决策工作台。"],
      decision: ["决策中心", "把证据链、竞品作战卡、客户需求和路线图动作整合成产品判断。"],
      intel: ["市场雷达", "自动检索公开市场信号，识别客户机会、竞品动态和政策风险。"],
      requirements: ["需求分析", "把客户口语化需求拆成产品、研发和测试可执行结构。"],
      competitors: ["竞品对比", "结构化管理车载激光雷达关键参数和来源。"],
      differentiation: ["产品价值", "说明系统如何帮助团队完成机会判断、方案准备和协同推进。"],
      capabilities: ["版本规划", "展示当前可用、增强中和后续规划的能力。"],
      profile: ["产品画像", "维护我方产品线、目标客户、机会关键词和客户信息要求。"],
      proposals: ["产品方案", "基于需求、竞品和知识库生成方案草案。"],
      rag: ["资料依据库", "保存产品资料、测试口径和客户纪要，让AI基于资料回答。"],
      evals: ["AI评测", "持续观察准确性、覆盖率、可追溯率和幻觉风险。"],
      system: ["系统说明", "说明系统覆盖范围、AI工作机制、速腾业务上下文和使用边界。"],
      config: ["API配置", "配置DeepSeek、新闻搜索和外部协同接口。"],
      integrations: ["协同推进", "把产品动作推送到研发、售前、CRM或团队协同工具。"],
    };
    $("pageTitle").textContent = titles[btn.dataset.view][0];
    $("pageDesc").textContent = titles[btn.dataset.view][1];
  });
});

function cardNews(n) {
  return `<article class="card">
    <h2>${escapeHtml(n.title)}</h2>
    <div class="meta"><span>${escapeHtml(n.category || "")}</span><span>${escapeHtml(n.region || "")}</span><span class="score">机会 ${n.opportunity_score}</span></div>
    <p>${escapeHtml(n.summary || "")}</p>
    <div>${(n.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
    <button onclick="analyzeOpportunity('${escapeHtml(n.id)}')">生成客户机会分析</button>
  </article>`;
}

function item(title, body) {
  return `<div class="item"><strong>${escapeHtml(title)}</strong><div>${body}</div></div>`;
}

function kvList(obj) {
  const labelMap = {
    detection_range: "探测距离",
    fov_horizontal: "水平视场角",
    fov_vertical: "垂直视场角",
    frame_rate: "刷新率",
    reliability: "可靠性",
    power: "功耗",
    fov: "视场角",
  };
  return Object.entries(obj || {}).map(([k, v]) => `<div class="kv"><span>${escapeHtml(labelMap[k] || k)}</span><strong>${escapeHtml(displayValue(v))}</strong></div>`).join("");
}

function chips(arr) {
  return toArray(arr).map((x) => `<span class="tag">${escapeHtml(displayValue(x))}</span>`).join("");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));
}

function toArray(value) {
  if (Array.isArray(value)) return value;
  if (value == null || value === "") return [];
  if (typeof value === "object") {
    if (Array.isArray(value.suggested_tasks)) return value.suggested_tasks;
    if (Array.isArray(value.suggested_metrics)) return value.suggested_metrics;
    if (Array.isArray(value.suggested_risks)) return value.suggested_risks;
    if (Array.isArray(value.suggested_selling_points)) return value.suggested_selling_points;
    if (value.fact || value.to_confirm) return [value.fact, value.to_confirm].filter(Boolean);
    return Object.entries(value).flatMap(([k, v]) => {
      const text = displayValue(v);
      return text ? [`${friendlyLabel(k)}：${text}`] : [];
    });
  }
  return [value];
}

function friendlyLabel(key) {
  const map = {
    detection_range: "探测距离",
    fov_horizontal: "水平视场角",
    fov_vertical: "垂直视场角",
    frame_rate: "刷新率",
    reliability: "可靠性",
    power: "功耗",
    fov: "视场角",
    market_summary: "市场概览",
    product_positioning: "产品定位",
  };
  return map[key] || String(key).replace(/_/g, " ");
}

function displayValue(value) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.map(displayValue).join("、");
  if (typeof value === "object") {
    if (value.name && value.description) return `${value.name}: ${value.description}`;
    if (value.metric_name && value.target) return `${value.metric_name}: ${value.target}`;
    if (value.risk_id && value.description) return `${value.risk_id}: ${value.description}`;
    if (value.fact && value.to_confirm) return `${value.fact}；待确认：${value.to_confirm}`;
    if (value.fact) return value.fact;
    return Object.entries(value).map(([k, v]) => `${friendlyLabel(k)}：${displayValue(v)}`).filter(Boolean).join("；");
  }
  return value;
}

async function refreshAll() {
  const [health, config, monitor, profile, opportunities, decision, news, competitors, requirements, proposals, evaluations, documents] = await Promise.all([
    api("/api/health"),
    api("/api/config"),
    api("/api/monitor"),
    api("/api/product-profile"),
    api("/api/opportunities?limit=12"),
    api("/api/decision-center"),
    api("/api/news"),
    api("/api/competitors"),
    api("/api/requirements"),
    api("/api/proposals"),
    api("/api/evaluations"),
    api("/api/documents"),
  ]);
  Object.assign(state, { config, monitor, profile, opportunities, decision, news, competitors, requirements, proposals, evaluations, documents });
  const marketSource = health.market_source === "commercial_api" ? "商业新闻API" : "公开RSS";
  $("health").textContent = `${health.llm_provider || "LLM"} ${health.llm ? "已接入" : "本地规则兜底"} · 市场源 ${marketSource}`;
  $("mNews").textContent = news.filter((n) => n.opportunity_score >= 70).length;
  $("mCmp").textContent = competitors.length;
  $("mReq").textContent = requirements.length;
  if ($("mEval")) $("mEval").textContent = evaluations.length;
  if ($("homeRoadmapCount")) $("homeRoadmapCount").textContent = (decision.roadmap_actions || []).length;
  $("topNews").innerHTML = news.slice(0, 3).map((n) => item(n.title, `${n.summary}<br><span class="score">机会评分 ${n.opportunity_score}</span>`)).join("");
  $("newsList").innerHTML = news.map(cardNews).join("");
  renderCompetitors();
  renderRequirements();
  renderRequirementInsight();
  renderProposals();
  renderDocs();
  renderEvaluations();
  renderConfig(config);
  renderMonitor(monitor);
  renderProfile(profile);
  renderOpsStatus(health, monitor, profile);
  renderOpportunityPool(opportunities);
  renderHomeFocus(opportunities, decision);
  renderDecisionCenter(decision);
}

function renderHomeFocus(opportunities, decision = {}) {
  if (!$("homeFocus")) return;
  const top = (opportunities || [])[0];
  const action = (decision.roadmap_actions || [])[0];
  if (!top) {
    $("homeFocus").innerHTML = `
      <strong>先刷新市场雷达</strong>
      <p>系统会自动抓取公开情报，并识别客户机会、竞品动态和政策风险。</p>
      <button onclick="runMonitorNow()">开始刷新</button>`;
    return;
  }
  const fit = top.fit || {};
  $("homeFocus").innerHTML = `
    <strong>${escapeHtml(top.title)}</strong>
    <p>${escapeHtml(top.category)} · 机会评分 ${escapeHtml(top.opportunity_score)} · 客户信息完整度 ${escapeHtml(fit.customer_completeness || 0)}%</p>
    <p>${escapeHtml(action?.action || "建议进入需求拆解，补齐客户字段。")}</p>
    <div class="button-row">
      <button onclick="analyzeOpportunity('${escapeHtml(top.id)}')">分析这条机会</button>
      <button class="secondary" onclick="goView('decision')">查看依据</button>
    </div>`;
}

function renderOpsStatus(health, monitor, profile) {
  const productCount = (profile.core_products || []).length;
  const customerCount = (profile.target_customers || []).length;
  const monitorText = monitor.running ? "运行中" : "未启动";
  const sourceText = health.market_source === "commercial_api" ? "商业新闻API" : "公开RSS";
  $("opsStatus").innerHTML = `
    <div class="ops-row"><span>我方产品画像</span><strong>${productCount} 条产品线 / ${customerCount} 类客户</strong></div>
    <div class="ops-row"><span>市场数据源</span><strong>${sourceText}</strong></div>
    <div class="ops-row"><span>大模型</span><strong>${health.llm_provider} ${health.llm ? "已接入" : "未接入"}</strong></div>
    <div class="ops-row"><span>DeepSeek最近调用</span><strong>${health.llm_state?.last_call || "本轮尚未调用"} / ${health.llm_state?.call_count || 0} 次</strong></div>
    <div class="ops-row"><span>定时监控</span><strong>${monitorText}</strong></div>
    <div class="ops-row"><span>客户字段要求</span><strong>${(profile.customer_required_fields || []).length} 项</strong></div>`;
}

function renderOpportunityPool(opportunities) {
  $("opportunityPool").innerHTML = opportunities.slice(0, 6).map((n) => {
    const fit = n.fit || {};
    const products = (fit.matched_products || []).map((p) => p.name).filter(Boolean);
    return `<div class="opportunity-row">
      <div>
        <strong>${escapeHtml(n.title)}</strong>
        <p>${escapeHtml(n.category)} · 评分 ${escapeHtml(n.opportunity_score)} · 客户信息完整度 ${escapeHtml(fit.customer_completeness || 0)}%</p>
        <div>${chips(products.length ? products : ["待匹配产品"])}</div>
      </div>
      <button onclick="analyzeOpportunity('${escapeHtml(n.id)}')">分析</button>
    </div>`;
  }).join("");
}

function renderMonitor(monitor) {
  const cfg = monitor.config || {};
  $("monitorStatus").innerHTML = `
    <strong>${monitor.running ? "定时监控运行中" : "定时监控未启动"}</strong>
    <span>上次运行：${escapeHtml(monitor.last_run || "尚未运行")}</span>
    <span>新增情报：${escapeHtml(monitor.last_count ?? 0)}</span>
    <span>间隔：${escapeHtml(cfg.interval_minutes || 30)} 分钟</span>
    ${monitor.last_error ? `<span class="danger">错误：${escapeHtml(monitor.last_error)}</span>` : ""}`;
  if ($("monitorQueries")) $("monitorQueries").value = (cfg.queries || []).join("\n");
  if ($("monitorRss")) $("monitorRss").value = (cfg.rss_urls || []).join("\n");
  if ($("monitorUrls")) $("monitorUrls").value = (cfg.web_urls || []).join("\n");
  if ($("monitorInterval")) $("monitorInterval").value = cfg.interval_minutes || 30;
  if ($("pushThreshold")) $("pushThreshold").value = cfg.push_threshold || 80;
  if ($("pushChannels")) $("pushChannels").value = (cfg.push_channels || ["crm"]).join(",");
}

function renderProfile(profile) {
  $("profileCompany").value = profile.company_name || "";
  $("profilePositioning").value = profile.positioning || "";
  $("profileKeywords").value = (profile.opportunity_keywords || []).join("\n");
  $("profileExclusions").value = (profile.exclusion_keywords || []).join("\n");
  $("customerRequiredFields").value = (profile.customer_required_fields || []).join("\n");
  renderProductEditor(profile.core_products || []);
  renderCustomerEditor(profile.target_customers || []);
}

function csv(value) {
  return toArray(value).join("、");
}

function splitList(value) {
  return String(value || "").split(/[,，、\n]+/).map((x) => x.trim()).filter(Boolean);
}

function renderProductEditor(products) {
  if (!$("productEditor")) return;
  $("productEditor").innerHTML = (products || []).map((p, i) => `<article class="module-card product-module" data-index="${i}">
    <div class="module-card-head">
      <strong>${escapeHtml(p.name || "未命名产品")}</strong>
      <button class="secondary" onclick="removeProductLine(${i})">删除</button>
    </div>
    <div class="module-grid">
      <label>产品名称<input class="product-name" value="${escapeHtml(p.name || "")}"></label>
      <label>产品类型<input class="product-type" value="${escapeHtml(p.type || "")}"></label>
      <label>目标场景<textarea class="product-scenarios" placeholder="用顿号、逗号或换行分隔">${escapeHtml(csv(p.target_scenarios))}</textarea></label>
      <label>关键规格<textarea class="product-specs" placeholder="如：192线、车规级、低功耗">${escapeHtml(csv(p.key_specs))}</textarea></label>
      <label>主要优势<textarea class="product-advantages" placeholder="如：量产经验、成本优势">${escapeHtml(csv(p.advantages))}</textarea></label>
    </div>
  </article>`).join("") || `<div class="empty-state">暂无产品线，点击“添加产品”开始维护。</div>`;
}

function renderCustomerEditor(customers) {
  if (!$("customerEditor")) return;
  $("customerEditor").innerHTML = (customers || []).map((c, i) => `<article class="module-card customer-module" data-index="${i}">
    <div class="module-card-head">
      <strong>${escapeHtml(c.segment || "未命名客户类型")}</strong>
      <button class="secondary" onclick="removeTargetCustomer(${i})">删除</button>
    </div>
    <div class="module-grid">
      <label>客户类型<input class="customer-segment" value="${escapeHtml(c.segment || "")}"></label>
      <label>重点区域<textarea class="customer-regions" placeholder="China、Europe、North America">${escapeHtml(csv(c.regions))}</textarea></label>
      <label>典型需求<textarea class="customer-requirements" placeholder="L3量产、城市NOA、成本优化">${escapeHtml(csv(c.requirements))}</textarea></label>
      <label>决策因素<textarea class="customer-factors" placeholder="性能、成本、可靠性、量产时间">${escapeHtml(csv(c.decision_factors))}</textarea></label>
    </div>
  </article>`).join("") || `<div class="empty-state">暂无目标客户，点击“添加客户类型”开始维护。</div>`;
}

function collectProducts() {
  return Array.from(document.querySelectorAll(".product-module")).map((el) => ({
    name: el.querySelector(".product-name").value.trim(),
    type: el.querySelector(".product-type").value.trim(),
    target_scenarios: splitList(el.querySelector(".product-scenarios").value),
    key_specs: splitList(el.querySelector(".product-specs").value),
    advantages: splitList(el.querySelector(".product-advantages").value),
  })).filter((p) => p.name || p.type);
}

function collectCustomers() {
  return Array.from(document.querySelectorAll(".customer-module")).map((el) => ({
    segment: el.querySelector(".customer-segment").value.trim(),
    regions: splitList(el.querySelector(".customer-regions").value),
    requirements: splitList(el.querySelector(".customer-requirements").value),
    decision_factors: splitList(el.querySelector(".customer-factors").value),
  })).filter((c) => c.segment);
}

function addProductLine() {
  const products = collectProducts();
  products.push({ name: "新产品", type: "", target_scenarios: [], key_specs: [], advantages: [] });
  renderProductEditor(products);
}

function removeProductLine(index) {
  const products = collectProducts();
  products.splice(index, 1);
  renderProductEditor(products);
}

function addTargetCustomer() {
  const customers = collectCustomers();
  customers.push({ segment: "新客户类型", regions: [], requirements: [], decision_factors: [] });
  renderCustomerEditor(customers);
}

function removeTargetCustomer(index) {
  const customers = collectCustomers();
  customers.splice(index, 1);
  renderCustomerEditor(customers);
}

async function saveProfile() {
  const coreProducts = collectProducts();
  const targetCustomers = collectCustomers();
  const payload = {
    company_name: $("profileCompany").value,
    positioning: $("profilePositioning").value,
    core_products: coreProducts,
    target_customers: targetCustomers,
    opportunity_keywords: $("profileKeywords").value.split(/\n+/).map((x) => x.trim()).filter(Boolean),
    exclusion_keywords: $("profileExclusions").value.split(/\n+/).map((x) => x.trim()).filter(Boolean),
    customer_required_fields: $("customerRequiredFields").value.split(/\n+/).map((x) => x.trim()).filter(Boolean),
  };
  const profile = await api("/api/product-profile", { method: "POST", body: JSON.stringify(payload) });
  renderProfile(profile);
  alert("产品画像已保存，后续情报评分和方案生成会使用这些信息。");
}

async function analyzeOpportunity(newsId) {
  goView("intel");
  const target = $("opportunityAnalysis");
  if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  $("opportunityAnalysis").innerHTML = `<div class="item">正在基于产品画像和客户字段要求分析机会...</div>`;
  let result;
  try {
    result = await api("/api/opportunities/analyze", { method: "POST", body: JSON.stringify({ news_id: newsId }) });
  } catch (err) {
    $("opportunityAnalysis").innerHTML = `<div class="item"><strong>分析失败</strong><p>${escapeHtml(err.message)}</p></div>`;
    return;
  }
  const fit = result.fit || {};
  const analysis = result.requirement_analysis || {};
  const proposal = result.proposal_preview || {};
  $("opportunityAnalysis").innerHTML = `
    <div class="result-band">
      <div>
        <h2>客户机会分析完成</h2>
        <p>已生成需求拆解，并检查客户信息完整性。</p>
      </div>
      <button onclick="goView('requirements')">查看需求池</button>
    </div>
    <div class="grid">
      <article class="card">
        <h2>机会来源</h2>
        <p><strong>${escapeHtml(result.news.title)}</strong></p>
        <p>${escapeHtml(result.news.summary)}</p>
        <span class="score">机会评分 ${escapeHtml(result.news.opportunity_score)}</span>
      </article>
      <article class="card">
        <h2>我方匹配</h2>
        <h3>命中关键词</h3>${chips(fit.matched_keywords)}
        <h3>匹配产品</h3>${chips((fit.matched_products || []).map((p) => p.name))}
      </article>
      <article class="card">
        <h2>客户信息完整性</h2>
        <div class="meter"><span style="width:${fit.customer_completeness || 0}%"></span></div>
        <p>${escapeHtml(fit.customer_completeness || 0)}%</p>
        <h3>已识别字段</h3>${chips(fit.customer_info_available)}
        <h3>缺失字段</h3>${chips(fit.customer_info_missing)}
      </article>
      <article class="card">
        <h2>需求拆解</h2>
        <h3>场景</h3>${chips(analysis.application_scenarios)}
        <h3>待确认问题</h3>${chips(analysis.questions_to_confirm)}
      </article>
      <article class="card">
        <h2>方案预览</h2>
        <p><strong>${escapeHtml(displayValue(proposal.product_positioning || ""))}</strong></p>
        <h3>关键规格</h3>${kvList(proposal.key_specs)}
      </article>
    </div>`;
  await refreshAll();
  goView("intel");
  $("opportunityAnalysis").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCompetitors() {
  $("competitorTable").innerHTML = `<div class="competitor-cards">
    ${state.competitors.map((c) => `<article class="competitor-card">
      <div class="competitor-title">
        <div>
          <h2>${escapeHtml(c.company)} ${escapeHtml(c.product_name)}</h2>
          <p>${escapeHtml(c.mass_production_status || "状态待确认")}</p>
        </div>
        <span>${escapeHtml(c.technology_route || "技术路线待确认")}</span>
      </div>
      <div class="spec-grid">
        <div><strong>感知能力</strong><p>${escapeHtml(c.detection_range || "待确认")} · ${escapeHtml(c.fov_horizontal || "-")} × ${escapeHtml(c.fov_vertical || "-")} · ${escapeHtml(c.frame_rate || "帧率待确认")}</p></div>
        <div><strong>工程约束</strong><p>${escapeHtml(c.wavelength || "波长待确认")} · ${escapeHtml(c.power || "功耗待确认")}</p></div>
        <div><strong>车规可靠性</strong><p>${escapeHtml(c.ip_rating || "防护待确认")} · ${escapeHtml(c.temperature_range || "温度待确认")}</p></div>
        <div><strong>公开客户</strong><p>${(c.public_customers || []).map(escapeHtml).join("、") || "待补充"}</p></div>
      </div>
    </article>`).join("")}
  </div>`;
}

function renderDecisionCenter(decision = state.decision || {}) {
  state.decision = decision || {};
  const evidence = decision.evidence_chain || [];
  const battlecards = decision.battlecards || [];
  const reqs = decision.requirement_prioritization || [];
  const roadmap = decision.roadmap_actions || [];
  if ($("decisionAnswer")) $("decisionAnswer").textContent = decision.executive_answer || "系统正在等待市场情报、竞品和需求数据。";
  if ($("dEvidence")) $("dEvidence").textContent = evidence.length;
  if ($("dBattle")) $("dBattle").textContent = battlecards.length;
  if ($("dReq")) $("dReq").textContent = reqs.length;
  if ($("dRoadmap")) $("dRoadmap").textContent = roadmap.length;
  if ($("evidenceChain")) {
    $("evidenceChain").innerHTML = evidence.map((e) => `<article class="evidence-card">
      <div class="evidence-score">${escapeHtml(e.score)}</div>
      <div>
        <h2>${escapeHtml(e.fact)}</h2>
        <p><strong>产品推断：</strong>${escapeHtml(e.inference)}</p>
        <p><strong>影响判断：</strong>${escapeHtml(e.impact)}</p>
        <p><strong>待确认：</strong>${escapeHtml(e.next_question)}</p>
        ${e.source ? `<a href="${escapeHtml(e.source)}" target="_blank" rel="noreferrer">查看来源</a>` : ""}
      </div>
    </article>`).join("") || `<div class="item">暂无证据链，请先刷新市场情报。</div>`;
  }
  const battleHtml = battlecards.slice(0, 8).map((b) => `<article class="battle-card">
    <h2>${escapeHtml(b.competitor)} ${escapeHtml(b.product)}</h2>
    <p><strong>威胁：</strong>${escapeHtml(b.threat)}</p>
    <p><strong>客户可能会问：</strong>${escapeHtml(b.likely_customer_argument)}</p>
    <p><strong>我方回应：</strong>${escapeHtml(b.robosense_response)}</p>
    <h3>需要证明</h3>${chips(b.proof_needed)}
  </article>`).join("") || `<div class="item">暂无竞品作战卡。</div>`;
  if ($("battlecards")) $("battlecards").innerHTML = battleHtml;
  if ($("competitorBattlecards")) $("competitorBattlecards").innerHTML = battleHtml;
  if ($("requirementPriority")) {
    $("requirementPriority").innerHTML = reqs.map((r) => `<div class="priority-row">
      <div class="priority-score">${escapeHtml(r.priority_score)}</div>
      <div>
        <strong>${escapeHtml(r.customer)} · ${escapeHtml(r.region)}</strong>
        <p>${escapeHtml(r.why_now)}</p>
        <p><strong>下一步：</strong>${escapeHtml(r.next_action)}</p>
        <div>${chips(r.missing_fields)}</div>
      </div>
    </div>`).join("") || `<div class="item">暂无需求优先级，请先从机会池生成需求。</div>`;
  }
  if ($("roadmapActions")) {
    $("roadmapActions").innerHTML = roadmap.map((r) => `<div class="roadmap-row">
      <span>${escapeHtml(r.urgency)}</span>
      <div>
        <strong>${escapeHtml(r.action)}</strong>
        <p>${escapeHtml(r.owner)} · ${escapeHtml(r.output)}</p>
        <small>${escapeHtml(r.evidence)}</small>
      </div>
    </div>`).join("");
  }
  if ($("differentiationList")) {
    $("differentiationList").innerHTML = (decision.differentiation || []).map((d) => `<article class="diff-card">
      <span>可用价值</span>
      <h2>${escapeHtml(d.title)}</h2>
      <p>${escapeHtml(d.proof)}</p>
    </article>`).join("");
  }
  renderCapabilities(decision.capability_roadmap || {});
  renderMarketMap(decision.market_map || []);
  renderBriefing(decision.briefing || {});
  renderWinLoss(decision.win_loss || []);
  renderSupplierScorecards(decision.supplier_scorecards || []);
}

async function refreshDecisionCenter() {
  const decision = await api("/api/decision-center");
  renderDecisionCenter(decision);
}

function renderCapabilities(roadmap) {
  const render = (items) => (items || []).map((x) => `<article class="capability-card">
    <div class="capability-top"><strong>${escapeHtml(x.name)}</strong><span>${escapeHtml(x.status)}</span></div>
    <p>${escapeHtml(x.value)}</p>
    <em>${escapeHtml(x.next_action)}</em>
  </article>`).join("");
  if ($("capP0")) $("capP0").innerHTML = render(roadmap.p0);
  if ($("capP1")) $("capP1").innerHTML = render(roadmap.p1);
  if ($("capP2")) $("capP2").innerHTML = render(roadmap.p2);
}

function renderMarketMap(items) {
  if (!$("marketMap")) return;
  $("marketMap").innerHTML = items.map((x) => `<div class="map-row">
    <strong>${escapeHtml(x.layer)}</strong>
    <p>${escapeHtml(x.summary)}</p>
    <div>${chips(x.items)}</div>
  </div>`).join("");
}

function renderBriefing(briefing) {
  if (!$("briefingPanel")) return;
  $("briefingPanel").innerHTML = `<div class="briefing">
    <h3>${escapeHtml(briefing.title || "本轮情报简报")}</h3>
    <p>${escapeHtml(briefing.summary || "暂无简报，请先刷新市场情报。")}</p>
    <h3>重点机会</h3>${chips(briefing.top_opportunities)}
    <h3>风险信号</h3>${chips(briefing.risk_signals)}
    <h3>建议动作</h3>${chips(briefing.recommended_actions)}
  </div>`;
}

function renderWinLoss(items) {
  if (!$("winLossPanel")) return;
  $("winLossPanel").innerHTML = items.map((x) => `<div class="item">
    <strong>${escapeHtml(x.stage)}</strong>
    <p>${escapeHtml(x.insight)}</p>
    <p><span class="muted-label">依据</span>${escapeHtml(x.evidence)}</p>
    <p><span class="muted-label">动作</span>${escapeHtml(x.action)}</p>
  </div>`).join("");
}

function renderSupplierScorecards(items) {
  if (!$("supplierScorecards")) return;
  $("supplierScorecards").innerHTML = items.map((x) => `<div class="supplier-row">
    <div class="priority-score">${escapeHtml(x.score)}</div>
    <div>
      <strong>${escapeHtml(x.supplier)} ${escapeHtml(x.product)}</strong>
      <p>${escapeHtml(x.strength)}</p>
      <p>${escapeHtml(x.risk)}</p>
      <div>${chips(x.evidence_needed)}</div>
    </div>
  </div>`).join("");
}

async function refreshCompetitorIntel() {
  $("competitorIntel").innerHTML = `<div class="item">正在检索竞品公开动态并调用DeepSeek分析...</div>`;
  const result = await api("/api/competitors/realtime", { method: "POST", body: JSON.stringify({}) });
  const summary = result.summary || {};
  $("competitorIntel").innerHTML = `
    <div class="grid">
      <article class="card">
        <h2>市场概览</h2>
        <p>${escapeHtml(displayValue(summary.market_summary))}</p>
      </article>
      <article class="card">
        <h2>竞品威胁</h2>
        ${chips(summary.competitor_threats)}
      </article>
      <article class="card">
        <h2>对速腾产品影响</h2>
        ${chips(summary.product_implications)}
      </article>
      <article class="card">
        <h2>建议动作</h2>
        ${chips(summary.recommended_actions)}
      </article>
    </div>
    <div class="grid">
      ${(result.items || []).slice(0, 8).map((n) => `<article class="card">
        <h2>${escapeHtml(n.title)}</h2>
        <div class="meta"><span>${escapeHtml(n.category)}</span><span class="score">机会 ${escapeHtml(n.opportunity_score)}</span></div>
        <p>${escapeHtml(n.summary)}</p>
        <div>${chips(n.tags)}</div>
      </article>`).join("")}
    </div>`;
  await refreshAll();
}

function renderRequirements() {
  $("requirementList").innerHTML = state.requirements.map((r) => item(
    `${r.customer_name} · ${r.region}`,
    `<p>${escapeHtml(r.raw_input)}</p>
     <div class="mini-grid">
       <div><h3>应用场景</h3>${chips(r.analysis?.application_scenarios)}</div>
       <div><h3>缺失客户字段</h3>${chips(r.analysis?.customer_info_missing)}</div>
       <div><h3>待确认问题</h3>${chips(r.analysis?.questions_to_confirm)}</div>
     </div>`
  )).join("");
}

function renderRequirementInsight() {
  const latest = state.requirements[0];
  if (!latest) {
    $("requirementInsight").innerHTML = `<article class="card"><h2>暂无自动需求</h2><p class="hint">系统会从高机会池生成需求拆解，也可以先刷新市场情报。</p></article>`;
    return;
  }
  const a = latest.analysis || {};
  $("requirementInsight").innerHTML = `
    <article class="card requirement-hero">
      <h2>这条需求在解决什么问题</h2>
      <p>${escapeHtml(displayValue(a.business_goal) || "基于市场机会判断潜在客户需求，并明确下一步要补齐的信息。")}</p>
      <div class="requirement-flow">
        <span>机会线索</span><span>客户字段</span><span>需求拆解</span><span>产品匹配</span><span>方案评审</span>
      </div>
    </article>
    <article class="card">
      <h2>来源</h2>
      <p>${escapeHtml(latest.customer_name)} · ${escapeHtml(latest.region)}</p>
      <p class="hint">${escapeHtml(latest.raw_input)}</p>
    </article>
    <article class="card">
      <h2>客户信息完整性</h2>
      <div class="meter"><span style="width:${a.customer_completeness || 0}%"></span></div>
      <p>${escapeHtml(a.customer_completeness || 0)}%</p>
      <h3>缺失字段</h3>${chips(a.customer_info_missing)}
    </article>
    <article class="card">
      <h2>需求拆解地图</h2>
      <div class="req-map">
        <div><strong>应用场景</strong>${chips(a.application_scenarios)}</div>
        <div><strong>产品类型</strong><p>${escapeHtml(displayValue(a.product_type))}</p></div>
        <div><strong>性能需求</strong>${chips(a.performance_requirements)}</div>
        <div><strong>可靠性</strong>${chips(a.reliability_requirements)}</div>
        <div><strong>合规要求</strong>${chips(a.compliance_requirements)}</div>
        <div><strong>交付物</strong>${chips(a.deliverables)}</div>
      </div>
    </article>
    <article class="card">
      <h2>风险与下一步确认</h2>
      <h3>风险</h3>${chips(a.risks)}
      <h3>待确认问题</h3>
      ${chips(a.questions_to_confirm)}
    </article>`;
}

function renderProposals() {
  $("proposalList").innerHTML = state.proposals.map((p) => item(
    displayValue(p.product_positioning),
    `<div>${chips(p.selling_points)}</div>
     <div class="mini-grid">
       <div><h3>关键规格</h3>${kvList(p.key_specs)}</div>
       <div><h3>验收指标</h3>${chips(p.validation_metrics)}</div>
       <div><h3>风险</h3>${chips(p.risks)}</div>
     </div>`
  )).join("");
}

function renderDocs() {
  $("docList").innerHTML = state.documents.map((d) => `<article class="module-card doc-card">
    <div class="module-card-head">
      <strong>${escapeHtml(cleanDocTitle(d.title))}</strong>
      <button class="secondary" onclick="deleteDoc('${escapeHtml(d.id)}')">删除</button>
    </div>
    <p>${escapeHtml(d.source_url || "本地资料")} · ${escapeHtml(formatDate(d.created_at))}</p>
  </article>`).join("") || `<div class="empty-state">暂无资料。保存资料后，它会出现在这里。</div>`;
}

function cleanDocTitle(title) {
  const text = String(title || "").trim();
  if (!text || /\?{4,}/.test(text)) return "未命名资料";
  return text;
}

function formatDate(value) {
  if (!value) return "";
  return String(value).replace("T", " ").replace(/\.\d+.*$/, "");
}

function renderEvaluations() {
  $("evalList").innerHTML = state.evaluations.map((e) => item(
    `${e.task_type} · ${e.model_name}`,
    `准确性 ${Number(e.accuracy_score).toFixed(1)} · 覆盖率 ${Number(e.coverage_score).toFixed(1)} · 可追溯 ${Number(e.traceability_score).toFixed(1)} · 幻觉风险 ${e.hallucination_flag ? "有" : "无"}`
  )).join("");
}

async function ingestSearch() {
  const data = await api("/api/news/ingest-search", { method: "POST", body: JSON.stringify({ query: $("searchQuery").value }) });
  alert(`已采集 ${data.count} 条`);
  refreshAll();
}

async function runDemoFlow() {
  try {
    $("health").textContent = "正在运行完整链路...";
    await api("/api/news/ingest-search", { method: "POST", body: JSON.stringify({ query: $("searchQuery").value || "automotive lidar ADAS L3 Europe" }) });
    const req = await api("/api/requirements", {
      method: "POST",
      body: JSON.stringify({
        customer_name: $("customerName").value || "匿名欧洲车企",
        region: $("region").value || "Europe",
        raw_input: $("rawRequirement").value,
      }),
    });
    const prop = await api("/api/proposals", { method: "POST", body: JSON.stringify({ requirement_id: req.id }) });
    $("requirementResult").innerHTML = `<div class="result-summary"><strong>需求拆解完成</strong><p>已识别应用场景、缺失字段和待确认问题。</p></div>`;
    $("proposalResult").innerHTML = `<div class="result-summary"><strong>${escapeHtml(displayValue(prop.product_positioning || "产品方案已生成"))}</strong><p>已生成目标场景、关键规格、研发任务和验收指标。</p></div>`;
    await refreshAll();
    goView("proposals");
  } catch (err) {
    alert(err.message);
  }
}

async function analyzeTopOpportunity() {
  if (!state.opportunities.length) {
    await runMonitorNow();
  }
  const top = state.opportunities[0];
  if (!top) {
    alert("暂无可分析机会，系统会先刷新情报。");
    return;
  }
  goView("intel");
  await analyzeOpportunity(top.id);
}

async function saveMonitorConfig(silent = false) {
  if (!$("monitorQueries")) return;
  const payload = {
    queries: $("monitorQueries").value.split(/\n+/).map((x) => x.trim()).filter(Boolean),
    rss_urls: $("monitorRss").value.split(/\n+/).map((x) => x.trim()).filter(Boolean),
    web_urls: $("monitorUrls").value.split(/\n+/).map((x) => x.trim()).filter(Boolean),
    interval_minutes: Number($("monitorInterval").value || 30),
    push_threshold: Number($("pushThreshold").value || 80),
    push_channels: $("pushChannels").value.split(/[,，\n]+/).map((x) => x.trim()).filter(Boolean),
  };
  await api("/api/monitor/config", { method: "POST", body: JSON.stringify(payload) });
  await refreshAll();
  if (!silent) alert("监控配置已保存");
}

async function runMonitorNow() {
  $("monitorStatus").textContent = "正在抓取并分析...";
  const result = await api("/api/monitor/run", { method: "POST", body: JSON.stringify({}) });
  renderMonitorResult(result);
  await refreshAll();
}

async function startMonitor() {
  if ($("monitorQueries")) await saveMonitorConfig(true);
  await api("/api/monitor/start", { method: "POST", body: JSON.stringify({}) });
  await refreshAll();
}

async function stopMonitor() {
  await api("/api/monitor/stop", { method: "POST", body: JSON.stringify({}) });
  await refreshAll();
}

function renderMonitorResult(result) {
  const high = result.high_opportunities || [];
  $("executiveResult").innerHTML = `
    <div class="result-band">
      <div>
        <h2>本轮情报分析完成</h2>
        <p>新增 ${escapeHtml(result.count || 0)} 条情报，高机会推送 ${escapeHtml(result.pushed || 0)} 条。</p>
      </div>
      <button onclick="goView('intel')">查看情报池</button>
    </div>
    <div class="grid">
      ${high.map((n) => `<article class="card">
        <h2>${escapeHtml(n.category)}</h2>
        <p><strong>${escapeHtml(n.title)}</strong></p>
        <p>${escapeHtml(n.summary)}</p>
        <span class="score">机会评分 ${escapeHtml(n.opportunity_score)}</span>
        <h3>建议动作</h3>
        <p>进入客户机会池，关联竞品与目标场景，评估是否生成产品方案或售前材料。</p>
      </article>`).join("") || `<article class="card"><h2>暂无高机会事件</h2><p class="hint">可以增加关键词、RSS源或降低推送阈值。</p></article>`}
    </div>`;
}

async function runAutoAnalysis() {
  try {
    $("health").textContent = "正在自动分析...";
    $("executiveResult").innerHTML = `<div class="panel"><h2>自动分析中</h2><p class="hint">正在采集情报、拆解需求、检索竞品并生成方案。</p></div>`;
    const result = await api("/api/auto/analyze", {
      method: "POST",
      body: JSON.stringify({
        search_query: "automotive lidar ADAS L3 Europe",
        source_url: "",
        customer_name: "匿名目标客户",
        region: "Europe",
        raw_requirement: "欧洲某车企计划在2027年量产L3车型，需要一款适配高速NOA和拥堵自动驾驶场景的前向长距激光雷达，要求远距离探测、低功耗、满足车规可靠性，并希望供应商提供英文技术材料和测试报告。",
        doc_title: "L3前向激光雷达需求备忘录",
        doc_content: "L3高速NOA场景需要关注前向长距探测、低反射率目标识别、功能安全、车规可靠性、功耗和安装空间。关键参数必须标注测试条件和来源。",
      }),
    });
    renderExecutiveResult(result);
    await refreshAll();
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    $("executiveResult").innerHTML = `<div class="panel"><h2>分析失败</h2><p>${escapeHtml(err.message)}</p></div>`;
  }
}

function renderExecutiveResult(result) {
  const proposal = result.proposal || {};
  const analysis = result.requirement_analysis || {};
  const news = result.market_opportunities || [];
  const comps = result.competitor_evidence || [];
  $("executiveResult").innerHTML = `
    <div class="result-band">
      <div>
        <h2>自动分析结果</h2>
        <p>已生成面向产品决策的结论、依据和下一步动作。</p>
      </div>
      <button onclick="goView('decision')">查看决策中心</button>
    </div>
    <div class="grid">
      <article class="card">
        <h2>0. 我方产品匹配前提</h2>
        <p><strong>${escapeHtml(state.profile.company_name || "AutoSense Mobility")}</strong></p>
        <p>${escapeHtml(state.profile.positioning || "")}</p>
        <h3>客户信息完整性字段</h3>
        ${chips(state.profile.customer_required_fields || [])}
      </article>
      <article class="card">
        <h2>1. 市场机会判断</h2>
        ${news.slice(0, 3).map((n) => `<div class="opportunity">
          <strong>${escapeHtml(n.title)}</strong>
          <p>${escapeHtml(n.summary)}</p>
          <span class="score">机会评分 ${escapeHtml(n.opportunity_score)}</span>
        </div>`).join("")}
      </article>
      <article class="card">
        <h2>2. 客户需求拆解</h2>
        <h3>应用场景</h3>${chips(analysis.application_scenarios)}
        <h3>产品类型</h3><p>${escapeHtml(analysis.product_type)}</p>
        <h3>待确认问题</h3>${chips(analysis.questions_to_confirm)}
      </article>
      <article class="card">
        <h2>3. 竞品依据</h2>
        ${comps.slice(0, 4).map((c) => `<div class="cmp-line">
          <strong>${escapeHtml(c.company)} ${escapeHtml(c.product_name)}</strong>
          <span>${escapeHtml(c.technology_route)} · ${escapeHtml(c.detection_range)} · ${escapeHtml(c.mass_production_status)}</span>
        </div>`).join("")}
      </article>
      <article class="card">
        <h2>4. 产品定义建议</h2>
        <p><strong>${escapeHtml(displayValue(proposal.product_positioning))}</strong></p>
        <h3>目标场景</h3>${chips(proposal.target_scenarios)}
        <h3>核心卖点</h3>${chips(proposal.selling_points)}
      </article>
      <article class="card">
        <h2>5. 关键规格</h2>
        ${kvList(proposal.key_specs)}
      </article>
      <article class="card">
        <h2>6. 研发与验收</h2>
        <h3>研发任务</h3>${chips(proposal.development_tasks)}
        <h3>验收指标</h3>${chips(proposal.validation_metrics)}
      </article>
      <article class="card">
        <h2>7. 风险与边界</h2>
        ${chips(proposal.risks)}
        <p class="hint">${escapeHtml(proposal.ai_generated_content || "关键参数需研发和测试团队确认后再对外承诺。")}</p>
      </article>
      <article class="card">
        <h2>8. 决策价值</h2>
        <p>${escapeHtml(result.interview_summary?.project_value || "")}</p>
        <h3>能力覆盖</h3>
        ${chips([...(result.interview_summary?.pm_capability || []), ...(result.interview_summary?.ai_capability || []), ...(result.interview_summary?.hardware_capability || [])])}
      </article>
    </div>`;
}

async function ingestRss() {
  const data = await api("/api/news/ingest-rss", { method: "POST", body: JSON.stringify({ url: $("rssUrl").value }) });
  alert(`已采集 ${data.count} 条`);
  refreshAll();
}

async function crawlPage() {
  const data = await api("/api/crawl", { method: "POST", body: JSON.stringify({ url: $("crawlUrl").value }) });
  alert(`已抓取：${data.article.title}`);
  refreshAll();
}

async function createRequirement() {
  const data = await api("/api/requirements", {
    method: "POST",
    body: JSON.stringify({ customer_name: $("customerName").value, region: $("region").value, raw_input: $("rawRequirement").value }),
  });
  const a = data.analysis || {};
  $("requirementResult").innerHTML = `<div class="result-summary">
    <strong>需求拆解完成</strong>
    <p>${escapeHtml(displayValue(a.business_goal) || "已生成结构化需求。")}</p>
    <h3>应用场景</h3>${chips(a.application_scenarios)}
    <h3>待确认问题</h3>${chips(a.questions_to_confirm)}
  </div>`;
  await refreshAll();
  return data;
}

async function generateProposal() {
  const created = state.requirements.length ? null : await createRequirement();
  const latest = created ? { id: created.id } : state.requirements[0];
  const data = await api("/api/proposals", { method: "POST", body: JSON.stringify({ requirement_id: latest.id }) });
  $("proposalResult").innerHTML = `<div class="result-summary">
    <strong>${escapeHtml(displayValue(data.product_positioning || "产品方案已生成"))}</strong>
    <h3>目标场景</h3>${chips(data.target_scenarios)}
    <h3>核心卖点</h3>${chips(data.selling_points)}
    <h3>研发任务</h3>${chips(data.development_tasks)}
    <h3>验收指标</h3>${chips(data.validation_metrics)}
    <p class="hint">${escapeHtml(data.ai_generated_content || "关键参数需研发、测试和质量团队确认。")}</p>
  </div>`;
  refreshAll();
}

async function saveDoc() {
  const data = await api("/api/documents", { method: "POST", body: JSON.stringify({ title: $("docTitle").value, content: $("docContent").value }) });
  alert("资料已保存");
  refreshAll();
}

async function deleteDoc(id) {
  await api("/api/documents/delete", { method: "POST", body: JSON.stringify({ id }) });
  await refreshAll();
}

async function askRag() {
  const data = await api("/api/rag/query", { method: "POST", body: JSON.stringify({ query: $("ragQuery").value }) });
  $("ragAnswer").innerHTML = `<div class="result-summary">
    <strong>知识库回答</strong>
    <p>${escapeHtml(data.answer || "暂无回答")}</p>
    <h3>参考资料</h3>${chips((data.sources || []).map((x) => x.title || x.source_url || "资料"))}
  </div>`;
}

async function sendIntegration() {
  let payload = {};
  try { payload = JSON.parse($("integrationPayload").value); } catch { payload = { text: $("integrationPayload").value }; }
  const data = await api("/api/integrations/send", {
    method: "POST",
    body: JSON.stringify({ integration_type: $("integrationType").value, target: $("integrationTarget").value, payload }),
  });
  $("integrationResult").innerHTML = `<div class="result-summary">
    <strong>协同任务已创建</strong>
    <p>渠道：${escapeHtml(data.integration_type || $("integrationType").value)} · 状态：${escapeHtml(data.status || "已进入本地队列")}</p>
    <p>${escapeHtml(data.response || "等待外部系统配置后推送。")}</p>
  </div>`;
}

function renderConfig(config) {
  $("deepseekBaseUrl").value = config.deepseek_base_url || "https://api.deepseek.com";
  $("deepseekModel").value = config.deepseek_model || "deepseek-v4-flash";
  const rows = [
    ["大模型", config.deepseek_configured ? "DeepSeek已接入" : "本地规则兜底"],
    ["新闻搜索", config.news_api_configured || config.bing_configured || config.serpapi_configured ? "商业搜索已接入" : "公开RSS与本地规则"],
    ["研发协同", config.jira_webhook_configured ? "Jira已接入" : "本地待推送"],
    ["团队通知", config.feishu_webhook_configured || config.slack_webhook_configured ? "通知渠道已接入" : "待配置Webhook"],
    ["客户机会", config.crm_webhook_configured ? "CRM已接入" : "本地机会队列"],
  ];
  $("configStatus").innerHTML = rows.map(([name, value]) => `<div class="status-card"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

async function saveConfig() {
  const payload = {
    LLM_PROVIDER: "deepseek",
    DEEPSEEK_BASE_URL: $("deepseekBaseUrl").value || "https://api.deepseek.com",
    DEEPSEEK_MODEL: $("deepseekModel").value || "deepseek-v4-flash",
  };
  const deepseekKey = $("deepseekKey").value.trim();
  if (deepseekKey) {
    if (!deepseekKey.startsWith("sk-")) {
      alert("DeepSeek API Key格式不正确，应以 sk- 开头。");
      return;
    }
    payload.DEEPSEEK_API_KEY = deepseekKey;
  }
  if ($("newsApiKey").value.trim()) payload.NEWS_API_KEY = $("newsApiKey").value.trim();
  if ($("bingKey").value.trim()) payload.BING_SEARCH_API_KEY = $("bingKey").value.trim();
  if ($("serpKey").value.trim()) payload.SERPAPI_KEY = $("serpKey").value.trim();
  const cfg = await api("/api/config", { method: "POST", body: JSON.stringify(payload) });
  renderConfig(cfg);
  $("health").textContent = `deepseek ${cfg.deepseek_configured ? "已接入" : "本地规则兜底"} · 新闻源 ${cfg.news_api_configured || cfg.bing_configured || cfg.serpapi_configured ? "商业API已接入" : "公开RSS"}`;
  alert("配置已保存");
}

async function testLLM() {
  await saveConfig();
  const result = await api("/api/ai/test", { method: "POST", body: JSON.stringify({}) });
  $("configStatus").innerHTML = `<div class="status-card wide"><span>DeepSeek连接测试</span><strong>${result.ok ? "连接成功" : "需要检查配置"}</strong><p>${escapeHtml(result.message || "")}</p></div>`;
}

refreshAll().catch((err) => {
  $("health").textContent = err.message;
});
