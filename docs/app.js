const $ = (id) => document.getElementById(id);

const profile = {
  company: "RoboSense 速腾聚创",
  products: [
    { name: "EM4", type: "超高清长距数字化激光雷达", scenes: ["L3", "高阶智驾", "Robotaxi"], advantages: ["超长距探测", "2K高清三维感知", "小目标识别"] },
    { name: "EMX", type: "车载高性能数字化激光雷达", scenes: ["城市NOA", "高速NOA", "主激光雷达"], advantages: ["主雷达性能", "车载量产适配"] },
    { name: "E1", type: "全固态补盲激光雷达", scenes: ["泊车", "近距离补盲", "侧向感知"], advantages: ["全固态", "补盲场景", "易集成"] },
    { name: "M1 Plus", type: "车规级MEMS激光雷达", scenes: ["L2+", "NOA", "前向感知"], advantages: ["量产经验", "车规可靠性"] },
    { name: "P6", type: "感知系统方案", scenes: ["多传感器融合", "高阶智驾方案"], advantages: ["软硬结合", "客户项目适配"] },
  ],
};

const sampleOpportunity = {
  title: "Luminar 经营风险与海外客户机会",
  summary: "竞品经营变化可能影响海外客户的供应商评估，前向长距和高阶智驾方案可能出现替换窗口。",
  category: "竞品动态",
  score: 82,
};

document.querySelectorAll(".nav").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".view").forEach((x) => x.classList.remove("active"));
    btn.classList.add("active");
    $(btn.dataset.view).classList.add("active");
    const titles = {
      workbench: ["工作台", "面向车载激光雷达产品团队的 AI 产品决策体验版。"],
      decision: ["决策中心", "查看机会判断、证据链、需求缺口和下一步动作。"],
      profile: ["产品画像", "查看内置产品线和目标场景。"],
      config: ["API配置", "在本浏览器保存自己的 API Key。"],
    };
    $("pageTitle").textContent = titles[btn.dataset.view][0];
    $("pageDesc").textContent = titles[btn.dataset.view][1];
  });
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));
}

function chips(items) {
  return (items || []).map((x) => `<span class="tag">${escapeHtml(x)}</span>`).join("");
}

function localAnalysis() {
  return {
    source: "本地规则体验",
    opportunity: "值得进入机会池观察",
    productFit: "优先关联 EM4 / EMX，用于海外 L2+/L3 前向长距感知场景。",
    missingFields: ["客户名称/地区", "车型平台与量产时间", "成本目标", "车规/功能安全要求", "竞品供应商状态"],
    nextActions: ["补齐客户字段", "准备竞品替换作战卡", "对齐同条件探测距离与FOV口径", "形成售前技术交流材料"],
  };
}

async function callUserApi() {
  const key = localStorage.getItem("autosense_api_key");
  const baseUrl = localStorage.getItem("autosense_base_url") || "https://api.deepseek.com";
  const model = localStorage.getItem("autosense_model") || "deepseek-v4-flash";
  if (!key) return null;
  const prompt = `请作为车载激光雷达产品经理，基于以下机会输出JSON：opportunity, productFit, missingFields, nextActions。机会：${sampleOpportunity.title}。摘要：${sampleOpportunity.summary}。我方产品：EM4, EMX, E1, M1 Plus, P6。`;
  const res = await fetch(baseUrl.replace(/\/$/, "") + "/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model,
      temperature: 0.2,
      messages: [
        { role: "system", content: "你是车载激光雷达产品经理，只输出JSON。" },
        { role: "user", content: prompt },
      ],
    }),
  });
  if (!res.ok) throw new Error(`接口返回 ${res.status}`);
  const text = (await res.json()).choices?.[0]?.message?.content || "";
  const match = text.match(/\{[\s\S]*\}/);
  return match ? JSON.parse(match[0]) : { opportunity: text };
}

function renderAnalysis(data) {
  const result = data || localAnalysis();
  $("apiState").textContent = result.source || "用户 API 分析";
  $("result").innerHTML = `<div class="result-card">
    <h2>${escapeHtml(result.opportunity || "机会判断完成")}</h2>
    <p>${escapeHtml(result.productFit || "")}</p>
    <h3>待补齐信息</h3>${chips(result.missingFields)}
    <h3>下一步动作</h3>${chips(result.nextActions)}
  </div>`;
  $("decisionCards").innerHTML = [
    ["机会判断", result.opportunity],
    ["产品匹配", result.productFit],
    ["待补齐信息", (result.missingFields || []).join("、")],
    ["下一步动作", (result.nextActions || []).join("、")],
  ].map(([title, body]) => `<article class="card"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(body)}</p></article>`).join("");
}

async function runAnalysis() {
  $("result").innerHTML = `<div class="result-card">正在分析机会...</div>`;
  try {
    const apiResult = await callUserApi();
    renderAnalysis(apiResult || localAnalysis());
  } catch (err) {
    const fallback = localAnalysis();
    fallback.source = "用户 API 调用失败，已切换本地规则";
    fallback.nextActions = [...fallback.nextActions, `接口提示：${err.message}`];
    renderAnalysis(fallback);
  }
}

function saveApiConfig() {
  const key = $("apiKey").value.trim();
  if (key && !key.startsWith("sk-")) {
    $("configResult").innerHTML = `<div class="result-card">API Key 通常应以 sk- 开头，请检查后再保存。</div>`;
    return;
  }
  localStorage.setItem("autosense_api_key", key);
  localStorage.setItem("autosense_base_url", $("baseUrl").value.trim() || "https://api.deepseek.com");
  localStorage.setItem("autosense_model", $("modelName").value.trim() || "deepseek-v4-flash");
  $("apiState").textContent = key ? "已保存用户 API" : "本地规则体验";
  $("configResult").innerHTML = `<div class="result-card">配置已保存到当前浏览器。</div>`;
}

function clearApiConfig() {
  localStorage.removeItem("autosense_api_key");
  localStorage.removeItem("autosense_base_url");
  localStorage.removeItem("autosense_model");
  $("apiKey").value = "";
  $("apiState").textContent = "本地规则体验";
  $("configResult").innerHTML = `<div class="result-card">已清除本浏览器配置。</div>`;
}

async function testApi() {
  saveApiConfig();
  await runAnalysis();
  goView("workbench");
}

function goView(view) {
  document.querySelector(`.nav[data-view="${view}"]`)?.click();
}

function init() {
  $("apiKey").value = localStorage.getItem("autosense_api_key") || "";
  $("baseUrl").value = localStorage.getItem("autosense_base_url") || "https://api.deepseek.com";
  $("modelName").value = localStorage.getItem("autosense_model") || "deepseek-v4-flash";
  $("apiState").textContent = $("apiKey").value ? "已保存用户 API" : "本地规则体验";
  $("profileCards").innerHTML = profile.products.map((p) => `<article class="card">
    <h2>${escapeHtml(p.name)}</h2>
    <p>${escapeHtml(p.type)}</p>
    <h3>目标场景</h3>${chips(p.scenes)}
    <h3>主要优势</h3>${chips(p.advantages)}
  </article>`).join("");
  renderAnalysis(localAnalysis());
}

init();
