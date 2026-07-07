import json
import html
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "autosense.db"
STATIC_DIR = BASE_DIR / "static"
ENV_PATH = BASE_DIR / ".env"
MONITOR_PATH = BASE_DIR / "monitor_config.json"
PROFILE_PATH = BASE_DIR / "product_profile.json"
MONITOR_STATE = {"running": False, "last_run": None, "last_count": 0, "last_error": "", "thread": None}
LLM_STATE = {"last_call": None, "last_error": "", "call_count": 0}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_env_file():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip().lstrip("\ufeff"), value.strip().strip('"').strip("'").lstrip("\ufeff"))


def clean_secret(value):
    value = str(value or "").strip().strip('"').strip("'").lstrip("\ufeff")
    return "".join(ch for ch in value if ord(ch) < 128)


def valid_deepseek_key(value):
    value = clean_secret(value)
    return value.startswith("sk-") and len(value) >= 20


def read_config():
    load_env_file()
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    return {
        "llm_provider": provider,
        "deepseek_configured": valid_deepseek_key(os.getenv("DEEPSEEK_API_KEY")),
        "deepseek_base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "deepseek_model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "openai_model": os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini",
        "news_api_configured": bool(os.getenv("NEWS_API_KEY")),
        "bing_configured": bool(os.getenv("BING_SEARCH_API_KEY")),
        "serpapi_configured": bool(os.getenv("SERPAPI_KEY")),
        "jira_webhook_configured": bool(os.getenv("JIRA_WEBHOOK_URL")),
        "feishu_webhook_configured": bool(os.getenv("FEISHU_WEBHOOK_URL")),
        "crm_webhook_configured": bool(os.getenv("CRM_WEBHOOK_URL")),
        "slack_webhook_configured": bool(os.getenv("SLACK_WEBHOOK_URL")),
    }


def write_config(payload):
    existing = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.strip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                existing[key.strip()] = value.strip()
    allowed = {
        "LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "NEWS_API_KEY",
        "BING_SEARCH_API_KEY",
        "SERPAPI_KEY",
        "JIRA_WEBHOOK_URL",
        "FEISHU_WEBHOOK_URL",
        "CRM_WEBHOOK_URL",
        "SLACK_WEBHOOK_URL",
    }
    for key, value in payload.items():
        if key in allowed and value is not None:
            if key == "DEEPSEEK_API_KEY" and value and not valid_deepseek_key(value):
                continue
            existing[key] = str(value).strip()
            os.environ[key] = str(value).strip()
    lines = [
        "# AutoSense AI runtime configuration",
        "PORT=" + existing.get("PORT", os.getenv("PORT", "8765")),
        "LLM_PROVIDER=" + existing.get("LLM_PROVIDER", "deepseek"),
        "DEEPSEEK_API_KEY=" + existing.get("DEEPSEEK_API_KEY", ""),
        "DEEPSEEK_BASE_URL=" + existing.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "DEEPSEEK_MODEL=" + existing.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "OPENAI_API_KEY=" + existing.get("OPENAI_API_KEY", ""),
        "OPENAI_BASE_URL=" + existing.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "OPENAI_MODEL=" + existing.get("OPENAI_MODEL", "gpt-4o-mini"),
        "NEWS_API_KEY=" + existing.get("NEWS_API_KEY", ""),
        "BING_SEARCH_API_KEY=" + existing.get("BING_SEARCH_API_KEY", ""),
        "SERPAPI_KEY=" + existing.get("SERPAPI_KEY", ""),
        "JIRA_WEBHOOK_URL=" + existing.get("JIRA_WEBHOOK_URL", ""),
        "FEISHU_WEBHOOK_URL=" + existing.get("FEISHU_WEBHOOK_URL", ""),
        "CRM_WEBHOOK_URL=" + existing.get("CRM_WEBHOOK_URL", ""),
        "SLACK_WEBHOOK_URL=" + existing.get("SLACK_WEBHOOK_URL", ""),
    ]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return read_config()


def read_monitor_config():
    default = {
        "enabled": False,
        "interval_minutes": 30,
        "queries": [
            "automotive lidar ADAS L3 Europe",
            "LiDAR high level autonomous driving OEM design win",
            "车载 激光雷达 高阶智驾 定点 量产",
        ],
        "rss_urls": [],
        "web_urls": [],
        "push_threshold": 80,
        "push_channels": ["crm"],
    }
    if not MONITOR_PATH.exists():
        return default
    try:
        data = json.loads(MONITOR_PATH.read_text(encoding="utf-8"))
        default.update(data)
    except Exception:
        pass
    return default


def write_monitor_config(payload):
    config = read_monitor_config()
    for key in ["enabled", "interval_minutes", "queries", "rss_urls", "web_urls", "push_threshold", "push_channels"]:
        if key in payload:
            config[key] = payload[key]
    config["interval_minutes"] = max(5, int(config.get("interval_minutes") or 30))
    config["push_threshold"] = max(0, min(100, int(config.get("push_threshold") or 80)))
    for key in ["queries", "rss_urls", "web_urls", "push_channels"]:
        if isinstance(config.get(key), str):
            config[key] = [x.strip() for x in config[key].splitlines() if x.strip()]
    MONITOR_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def read_product_profile():
    default = {
        "company_name": "RoboSense 速腾聚创",
        "positioning": "面向汽车与机器人市场的AI驱动型机器人技术公司，提供数字化激光雷达、感知方案和核心组件。",
        "core_products": [
            {
                "name": "EM4",
                "type": "超高清长距数字化激光雷达",
                "target_scenarios": ["L3", "高阶智驾", "Robotaxi", "远距小目标识别"],
                "key_specs": ["2160线", "最高2160×1900分辨率", "300m@10%测距", "600m最远测距", "SPAD-SoC芯片", "全数字化架构"],
                "advantages": ["超长距探测", "2K高清三维感知", "小目标识别", "高阶智能驾驶安全冗余"],
            },
            {
                "name": "EMX",
                "type": "真192线车载高性能数字化激光雷达",
                "target_scenarios": ["高阶智驾", "主激光雷达", "城市NOA", "高速NOA"],
                "key_specs": ["192线", "车载高性能", "数字化架构"],
                "advantages": ["主雷达性能", "车载量产适配", "平台化数字架构"],
            },
            {
                "name": "E1",
                "type": "全固态补盲激光雷达",
                "target_scenarios": ["城市NOA", "泊车", "近距离补盲", "侧向感知"],
                "key_specs": ["120°×90°超广视场角", "25Hz刷新率", "30m@10%测距", "自研芯片"],
                "advantages": ["全固态", "补盲场景", "成本优势", "易集成"],
            },
            {
                "name": "M1 Plus",
                "type": "车规级MEMS激光雷达",
                "target_scenarios": ["量产车型", "L2+", "NOA", "前向感知"],
                "key_specs": ["车规级", "MEMS", "量产交付"],
                "advantages": ["量产经验", "车型搭载基础", "车规可靠性"],
            },
            {
                "name": "P6",
                "type": "感知系统方案",
                "target_scenarios": ["多传感器融合", "高阶智驾方案", "客户集成"],
                "key_specs": ["感知系统方案", "数据与算法闭环"],
                "advantages": ["方案级交付", "软硬结合", "客户项目适配"],
            },
        ],
        "target_customers": [
            {
                "segment": "国内外高阶智驾乘用车客户",
                "regions": ["China", "Europe", "North America", "Global"],
                "requirements": ["L2+/L3量产规划", "城市NOA", "高速NOA", "车规可靠性", "量产交付", "成本优化"],
                "decision_factors": ["性能", "成本", "可靠性", "量产时间", "已有供应商格局", "域控/算法适配"],
            },
            {
                "segment": "Robotaxi与自动驾驶方案商",
                "regions": ["China", "North America", "Global"],
                "requirements": ["高线数长距感知", "冗余安全", "点云质量", "感知系统方案"],
                "decision_factors": ["性能上限", "可靠性", "数据接口", "算法适配", "长期供货"],
            },
        ],
        "opportunity_keywords": ["RoboSense", "速腾聚创", "L3", "L2+", "NOA", "Robotaxi", "量产", "定点", "design win", "OEM", "ADAS", "LiDAR", "激光雷达", "车规", "功能安全", "Mercedes-Benz", "BYD", "Volvo", "NVIDIA DRIVE"],
        "exclusion_keywords": ["纯消费电子", "非车载", "无人机单点测绘"],
        "customer_required_fields": [
            "客户名称/地区",
            "车型平台与量产时间",
            "智驾等级与应用场景",
            "目标传感器类型",
            "关键性能指标",
            "成本目标",
            "可靠性/车规要求",
            "合规/功能安全要求",
            "竞品供应商状态",
            "交付物要求",
        ],
    }
    if not PROFILE_PATH.exists():
        return default
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        default.update(data)
    except Exception:
        pass
    return default


def write_product_profile(payload):
    profile = read_product_profile()
    for key, value in payload.items():
        if key in profile:
            profile[key] = value
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.executescript(
        """
        create table if not exists market_news (
            id text primary key,
            title text not null,
            source text,
            source_url text,
            published_at text,
            fetched_at text,
            region text,
            category text,
            summary text,
            entities text,
            opportunity_score integer,
            credibility_score integer,
            tags text,
            status text
        );
        create table if not exists competitors (
            id text primary key,
            company text,
            product_name text,
            technology_route text,
            wavelength text,
            detection_range text,
            fov_horizontal text,
            fov_vertical text,
            point_rate text,
            frame_rate text,
            power text,
            ip_rating text,
            temperature_range text,
            mass_production_status text,
            public_customers text,
            source_url text,
            updated_at text
        );
        create table if not exists requirements (
            id text primary key,
            customer_name text,
            region text,
            raw_input text,
            analysis text,
            priority text,
            confirmed_by_user integer,
            created_at text
        );
        create table if not exists proposals (
            id text primary key,
            requirement_id text,
            product_positioning text,
            target_scenarios text,
            key_specs text,
            selling_points text,
            development_tasks text,
            validation_metrics text,
            risks text,
            ai_generated_content text,
            human_review_status text,
            created_at text
        );
        create table if not exists documents (
            id text primary key,
            title text,
            source_url text,
            content text,
            chunks text,
            metadata text,
            created_at text
        );
        create table if not exists evaluations (
            id text primary key,
            task_type text,
            input_id text,
            model_name text,
            prompt_version text,
            output text,
            accuracy_score real,
            coverage_score real,
            traceability_score real,
            hallucination_flag integer,
            adoption_status text,
            reviewer_comment text,
            created_at text
        );
        create table if not exists integrations (
            id text primary key,
            integration_type text,
            target text,
            payload text,
            status text,
            response text,
            created_at text
        );
        """
    )
    conn.commit()
    cleanup_demo_news(conn)
    conn.close()


def cleanup_demo_news(conn):
    conn.execute("delete from market_news where source in ('Demo Intelligence', 'Mock Search', 'Local Fallback')")
    duplicate_ids = [
        row["id"]
        for row in conn.execute(
            """
            select m.id from market_news m
            where m.id not in (
                select min(id) from market_news group by title
            )
            """
        ).fetchall()
    ]
    if duplicate_ids:
        conn.executemany("delete from market_news where id=?", [(x,) for x in duplicate_ids])
    conn.commit()


def table_count(conn, table):
    return conn.execute(f"select count(*) as c from {table}").fetchone()["c"]


def seed_data(conn):
    if table_count(conn, "market_news") == 0:
        rows = [
            {
                "title": "欧洲车企加速L3车型规划，供应链寻求长距感知方案",
                "source": "Demo Intelligence",
                "source_url": "https://example.com/eu-l3-lidar",
                "published_at": "2026-06-28",
                "region": "Europe",
                "category": "客户机会",
                "summary": "欧洲主机厂继续推进L3量产规划，前向长距感知、功能安全和车规可靠性成为供应商评估重点。",
                "entities": ["Europe", "L3", "LiDAR", "OEM"],
                "opportunity_score": 88,
                "credibility_score": 72,
                "tags": ["L3", "海外市场", "前向长距"],
                "status": "已确认",
            },
            {
                "title": "低成本补盲激光雷达进入量产竞争阶段",
                "source": "Demo Intelligence",
                "source_url": "https://example.com/blind-spot-lidar",
                "published_at": "2026-06-25",
                "region": "China",
                "category": "竞品动态",
                "summary": "多家供应商围绕城市NOA和泊车场景推出低成本补盲方案，价格和集成便利性成为核心竞争变量。",
                "entities": ["城市NOA", "补盲雷达", "量产"],
                "opportunity_score": 76,
                "credibility_score": 70,
                "tags": ["补盲", "低成本", "城市NOA"],
                "status": "已确认",
            },
        ]
        for item in rows:
            insert_news(conn, item)
    if table_count(conn, "competitors") == 0:
        competitors = [
            ("cmp_hesai_at128", "Hesai", "AT128", "混合固态", "905nm", "200m+", "120deg", "25.4deg", "1.5M pts/s", "10Hz", "18W", "IP6K9K", "-40C~85C", "量产", ["理想", "集度"], "https://www.hesaitech.com/"),
            ("cmp_robosense_m1", "RoboSense", "M1", "MEMS", "905nm", "200m", "120deg", "25deg", "0.9M pts/s", "10Hz", "15W", "IP67", "-40C~85C", "量产", ["Lucid", "小鹏"], "https://www.robosense.ai/"),
            ("cmp_luminar_iris", "Luminar", "Iris", "1550nm", "1550nm", "250m+", "120deg", "26deg", "N/A", "10Hz", "N/A", "N/A", "-40C~85C", "定点/量产导入", ["Volvo", "Mercedes-Benz"], "https://www.luminartech.com/"),
            ("cmp_innoviz_two", "Innoviz", "InnovizTwo", "MEMS", "905nm", "300m claim", "120deg", "43deg", "N/A", "10-20Hz", "N/A", "IP6K9K", "-40C~85C", "定点", ["BMW", "VW Group"], "https://innoviz.tech/"),
        ]
        for c in competitors:
            conn.execute(
                """
                insert into competitors values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (*c[:14], json.dumps(c[14], ensure_ascii=False), c[15], now_iso()),
            )
        conn.commit()


def insert_news(conn, item):
    existing = None
    if item.get("source_url"):
        existing = conn.execute("select id from market_news where source_url=?", (item.get("source_url"),)).fetchone()
    if not existing and item.get("title"):
        existing = conn.execute("select id from market_news where title=?", (item.get("title"),)).fetchone()
    if existing:
        news_id = existing["id"]
        conn.execute(
            """
            update market_news
            set summary=?, entities=?, opportunity_score=?, credibility_score=?, tags=?, status=?, fetched_at=?
            where id=?
            """,
            (
                item.get("summary", ""),
                json.dumps(item.get("entities", []), ensure_ascii=False),
                int(item.get("opportunity_score", 50)),
                int(item.get("credibility_score", 60)),
                json.dumps(item.get("tags", []), ensure_ascii=False),
                item.get("status", "待审核"),
                item.get("fetched_at", now_iso()),
                news_id,
            ),
        )
        conn.commit()
        return news_id
    news_id = item.get("id") or "news_" + uuid.uuid4().hex[:10]
    conn.execute(
        """
        insert or replace into market_news values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            news_id,
            item.get("title", ""),
            item.get("source", ""),
            item.get("source_url", ""),
            item.get("published_at", ""),
            item.get("fetched_at", now_iso()),
            item.get("region", "Global"),
            item.get("category", "待分类"),
            item.get("summary", ""),
            json.dumps(item.get("entities", []), ensure_ascii=False),
            int(item.get("opportunity_score", 50)),
            int(item.get("credibility_score", 60)),
            json.dumps(item.get("tags", []), ensure_ascii=False),
            item.get("status", "待审核"),
        ),
    )
    conn.commit()
    return news_id


def rows_to_dicts(rows):
    out = []
    for row in rows:
        item = dict(row)
        for key in ["entities", "tags", "public_customers", "target_scenarios", "key_specs", "selling_points", "development_tasks", "validation_metrics", "risks"]:
            if key in item and isinstance(item[key], str):
                try:
                    item[key] = json.loads(item[key])
                except Exception:
                    pass
        if "analysis" in item and isinstance(item["analysis"], str) and item["analysis"]:
            try:
                item["analysis"] = json.loads(item["analysis"])
            except Exception:
                pass
        returnable = item
        out.append(returnable)
    return out


def opportunity_fit(news_item):
    profile = read_product_profile()
    text = f"{news_item.get('title', '')} {news_item.get('summary', '')} {' '.join(news_item.get('tags', []))}".lower()
    keywords = profile.get("opportunity_keywords", [])
    exclusions = profile.get("exclusion_keywords", [])
    matched = [kw for kw in keywords if kw.lower() in text]
    excluded = [kw for kw in exclusions if kw.lower() in text]
    matched_products = []
    for product in profile.get("core_products", []):
        product_terms = [product.get("type", ""), product.get("name", "")]
        product_terms.extend(product.get("target_scenarios", []))
        product_terms.extend(product.get("key_specs", []))
        hits = [term for term in product_terms if term and term.lower() in text]
        if hits:
            matched_products.append({"name": product.get("name"), "type": product.get("type"), "hits": hits[:5]})
    required = profile.get("customer_required_fields", [])
    available = []
    field_patterns = {
        "客户名称/地区": ["europe", "china", "us", "mercedes", "byd", "volvo", "bmw", "rivian", "oem", "车企", "欧洲", "北美", "中国"],
        "车型平台与量产时间": ["model", "models", "platform", "2027", "2026", "2028", "量产", "车型", "平台"],
        "智驾等级与应用场景": ["l3", "l2", "noa", "adas", "autonomous", "自动驾驶", "智驾"],
        "目标传感器类型": ["lidar", "激光雷达", "sensor", "传感器"],
        "关键性能指标": ["range", "fov", "resolution", "distance", "探测", "分辨率", "视场角"],
        "成本目标": ["cost", "price", "价格", "成本"],
        "可靠性/车规要求": ["automotive", "reliability", "车规", "可靠性", "ip67", "ip6k9k"],
        "合规/功能安全要求": ["safety", "regulation", "compliance", "功能安全", "合规", "法规"],
        "竞品供应商状态": ["supplier", "partner", "hesai", "robosense", "luminar", "innoviz", "供应商", "伙伴", "定点"],
        "交付物要求": ["report", "material", "test", "英文", "测试", "报告", "材料"],
    }
    for field in required:
        patterns = field_patterns.get(field, [field])
        if any(p.lower() in text for p in patterns):
            available.append(field)
    missing = [field for field in required if field not in available]
    completeness = int(round(len(available) / max(1, len(required)) * 100))
    return {
        "matched_keywords": matched,
        "excluded_keywords": excluded,
        "matched_products": matched_products,
        "customer_info_available": available,
        "customer_info_missing": missing,
        "customer_completeness": completeness,
        "recommended_action": "进入客户机会池并补齐缺失字段" if completeness < 80 else "可进入产品方案评审",
    }


def get_opportunities(limit=20):
    conn = db()
    rows = rows_to_dicts(
        conn.execute(
            "select * from market_news order by opportunity_score desc, fetched_at desc limit ?",
            (limit,),
        ).fetchall()
    )
    conn.close()
    for item in rows:
        item["fit"] = opportunity_fit(item)
    return rows


def analyze_opportunity(news_id):
    conn = db()
    row = conn.execute("select * from market_news where id=?", (news_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("opportunity not found")
    news = rows_to_dicts([row])[0]
    fit = opportunity_fit(news)
    raw_requirement = (
        f"市场情报标题：{news.get('title')}\n"
        f"摘要：{news.get('summary')}\n"
        f"来源：{news.get('source_url')}\n"
        f"机会分类：{news.get('category')}，机会评分：{news.get('opportunity_score')}。\n"
        f"请基于我方产品画像判断是否形成客户机会，并列出需补齐的客户信息。"
    )
    analysis = analyze_requirement(raw_requirement)
    analysis["customer_info_available"] = fit["customer_info_available"]
    analysis["customer_info_missing"] = fit["customer_info_missing"]
    analysis["customer_completeness"] = fit["customer_completeness"]
    rid = "req_" + uuid.uuid4().hex[:10]
    conn.execute(
        "insert into requirements values (?,?,?,?,?,?,?,?)",
        (
            rid,
            "由市场情报生成",
            news.get("region", "Global"),
            raw_requirement,
            json.dumps(analysis, ensure_ascii=False),
            "P1" if news.get("opportunity_score", 0) >= 80 else "P2",
            0,
            now_iso(),
        ),
    )
    conn.commit()
    competitors = rows_to_dicts(conn.execute("select * from competitors").fetchall())
    conn.close()
    proposal = generate_proposal({"id": rid, "raw_input": raw_requirement, "analysis": analysis}, competitors)
    return {
        "news": news,
        "fit": fit,
        "requirement_id": rid,
        "requirement_analysis": analysis,
        "proposal_preview": proposal,
    }


def realtime_competitor_analysis():
    competitor_queries = [
        "Hesai lidar Mercedes-Benz L3 supplier",
        "Luminar Innoviz Aeva automotive lidar design win",
        "RoboSense Hesai BYD lidar supplier price",
    ]
    articles = []
    for query in competitor_queries:
        try:
            articles.extend(fetch_search(query)[:6])
        except Exception as exc:
            MONITOR_STATE["last_error"] = f"竞品检索失败: {exc}"
    ids = ingest_articles(articles, use_llm=True, llm_limit=18) if articles else []
    competitor_names = ["hesai", "禾赛", "luminar", "innoviz", "aeva", "seyond", "robosense", "速腾", "robosense", "valeо", "valeo", "ouster"]
    conn = db()
    rows = rows_to_dicts(
        conn.execute("select * from market_news order by fetched_at desc, opportunity_score desc limit 80").fetchall()
    )
    conn.close()
    filtered = []
    for item in rows:
        text = f"{item.get('title','')} {item.get('summary','')} {' '.join(item.get('tags', []))}".lower()
        if any(name in text for name in competitor_names):
            item["fit"] = opportunity_fit(item)
            filtered.append(item)
    summary_prompt = (
        "你是车载激光雷达产品经理。请基于以下竞品资讯，输出JSON："
        "market_summary, competitor_threats, product_implications, recommended_actions。"
        "要求面向速腾聚创产品团队，重点分析EM4/EMX/E1/M1 Plus的影响。"
    )
    llm_summary = call_llm(
        [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": json.dumps(filtered[:12], ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    parsed = extract_json(llm_summary) if llm_summary else None
    return {
        "inserted": ids,
        "items": filtered[:12],
        "summary": parsed or {
            "market_summary": "已刷新竞品动态，详细结论需结合资讯列表判断。",
            "competitor_threats": [],
            "product_implications": [],
            "recommended_actions": [],
        },
    }


def build_evidence_chain(news_items):
    chain = []
    for item in news_items[:8]:
        fit = item.get("fit") or opportunity_fit(item)
        products = [p.get("name") for p in fit.get("matched_products", []) if p.get("name")]
        title = item.get("title", "")
        category = item.get("category", "市场信号")
        score = item.get("opportunity_score", 0)
        if score >= 85:
            impact_level = "高"
        elif score >= 70:
            impact_level = "中"
        else:
            impact_level = "观察"
        chain.append({
            "fact": title,
            "category": category,
            "source": item.get("source_url") or item.get("source") or "公开来源",
            "score": score,
            "inference": f"{category}可能影响{('、'.join(products) if products else 'EM4/EMX/E1/M1 Plus')}的产品定义或售前优先级。",
            "impact": f"{impact_level}影响：客户信息完整度{fit.get('customer_completeness', 0)}%，建议{fit.get('recommended_action', '进入机会池观察')}。",
            "next_question": "需要确认客户平台、量产时间、竞品供应商状态和关键性能口径。",
        })
    return chain


def build_battlecards(competitors):
    cards = []
    for c in competitors:
        company = c.get("company", "")
        product = c.get("product_name", "")
        route = c.get("technology_route", "")
        range_text = c.get("detection_range", "待确认")
        status = c.get("mass_production_status", "待确认")
        customers = c.get("public_customers", [])
        if not isinstance(customers, list):
            customers = [customers] if customers else []
        cards.append({
            "competitor": company,
            "product": product,
            "threat": f"{route}路线，公开探测距离{range_text}，状态为{status}。",
            "likely_customer_argument": f"客户可能关注{company}的量产状态、公开客户案例和参数口径。",
            "robosense_response": "用速腾产品画像进行场景匹配：长距主雷达优先对齐EM4/EMX，补盲和泊车优先对齐E1，方案级交付对齐P6。",
            "proof_needed": [
                "同一反射率条件下的探测距离对比",
                "FOV、帧率、功耗和温度范围口径",
                "车规验证、功能安全和客户项目状态",
                "公开客户案例：" + ("、".join(customers) if customers else "待补充"),
            ],
        })
    return cards


def build_requirement_prioritization(requirements):
    out = []
    for r in requirements[:8]:
        analysis = r.get("analysis") or {}
        missing = analysis.get("customer_info_missing") or []
        scenarios = analysis.get("application_scenarios") or []
        scenario_text = " ".join(map(str, scenarios)).lower()
        score = 55
        if any(k in scenario_text for k in ["l3", "高速", "noa", "robotaxi"]):
            score += 18
        if not missing:
            score += 15
        else:
            score += max(0, 15 - len(missing) * 2)
        if "海外" in json.dumps(analysis, ensure_ascii=False) or "Europe" in r.get("region", ""):
            score += 7
        score = max(0, min(100, score))
        out.append({
            "requirement_id": r.get("id"),
            "customer": r.get("customer_name", "未知客户"),
            "region": r.get("region", "Global"),
            "priority_score": score,
            "why_now": "场景涉及高阶智驾/量产机会，且可与速腾产品线形成匹配。" if score >= 75 else "需要继续补齐客户字段后再进入正式产品定义。",
            "missing_fields": missing,
            "next_action": "进入产品方案评审" if score >= 80 else "补齐客户信息并安排售前确认",
        })
    return out


def build_roadmap_actions(news_items, requirements, proposals, battlecards):
    actions = []
    if news_items:
        top = news_items[0]
        actions.append({
            "action": "建立高机会客户线索卡",
            "owner": "产品经理/售前",
            "evidence": top.get("title", ""),
            "urgency": "P0" if top.get("opportunity_score", 0) >= 85 else "P1",
            "output": "客户字段完整性表、待确认问题清单",
        })
    if battlecards:
        actions.append({
            "action": "生成竞品作战卡并用于售前技术交流",
            "owner": "产品经理/销售工程师",
            "evidence": f"{battlecards[0].get('competitor')} {battlecards[0].get('product')}",
            "urgency": "P1",
            "output": "参数对比、反击点、证明材料清单",
        })
    if requirements:
        actions.append({
            "action": "把最新需求转成研发验证任务",
            "owner": "产品经理/研发负责人",
            "evidence": requirements[0].get("raw_input", "")[:120],
            "urgency": "P1",
            "output": "光机电评审、DV/PV测试项、功能安全待确认项",
        })
    if proposals:
        actions.append({
            "action": "组织产品方案评审",
            "owner": "产品经理/测试/质量/商务",
            "evidence": proposals[0].get("product_positioning", ""),
            "urgency": "P1",
            "output": "方案版本、验收指标、风险矩阵",
        })
    actions.append({
        "action": "沉淀可追溯证据库",
        "owner": "产品经理",
        "evidence": "市场新闻、竞品公开资料、客户需求和AI评测记录",
        "urgency": "P2",
        "output": "可引用结论、RAG资料和AI质量看板",
    })
    return actions


def build_capability_roadmap(news_items, requirements, competitors, proposals):
    has_news = bool(news_items)
    has_requirements = bool(requirements)
    has_competitors = bool(competitors)
    has_proposals = bool(proposals)
    return {
        "p0": [
            {"name": "引用型AI结论", "source": "AlphaSense", "value": "每条结论保留事实、推断、来源和待确认问题，降低幻觉风险。", "status": "已上线" if has_news else "待数据", "next_action": "继续提高来源覆盖率和引用可读性。"},
            {"name": "高机会事件中心", "source": "Dataminr", "value": "把新闻列表升级为机会池，按机会评分和推送阈值管理。", "status": "已上线" if has_news else "待刷新", "next_action": "增加高风险事件的独立提醒规则。"},
            {"name": "客户信息完整性检查", "source": "Productboard/Klue", "value": "先识别缺失客户字段，再进入方案生成，避免需求不完整。", "status": "已上线" if has_requirements else "待生成需求", "next_action": "增加人工确认和负责人字段。"},
            {"name": "竞品作战卡", "source": "Crayon/Klue", "value": "把竞品动态转成客户交流、反击点和证明材料清单。", "status": "已上线" if has_competitors else "待补充竞品", "next_action": "增加客户场景化话术。"},
            {"name": "产品线匹配", "source": "垂直化差异点", "value": "围绕EM4、EMX、E1、M1 Plus、P6判断机会是否适合我方。", "status": "已上线", "next_action": "接入更多真实产品手册和测试资料。"},
        ],
        "p1": [
            {"name": "市场地图", "source": "CB Insights", "value": "把客户、竞品、应用场景和风险分层展示，形成管理层可读视角。", "status": "本次新增", "next_action": "加入更多区域和供应链角色。"},
            {"name": "情报周报/月报", "source": "Feedly/Meltwater", "value": "自动汇总机会、风险、竞品变化和建议动作，降低汇报成本。", "status": "本次新增", "next_action": "增加导出和定时推送。"},
            {"name": "Win/Loss复盘", "source": "Klue", "value": "沉淀客户为什么选择或拒绝某个方案，反哺产品定义。", "status": "本次新增", "next_action": "接入销售和售前反馈。"},
            {"name": "竞品趋势图", "source": "Similarweb", "value": "从单条竞品资讯升级为趋势和威胁判断。", "status": "本次新增", "next_action": "接入更多公开信号和时间序列。"},
            {"name": "Roadmap视图", "source": "Aha!", "value": "把机会转成研发、测试、售前和商务动作。", "status": "已上线" if has_proposals else "基础版", "next_action": "增加版本和里程碑管理。"},
        ],
        "p2": [
            {"name": "内部知识库融合", "source": "AlphaSense", "value": "把产品手册、测试报告、客户纪要纳入RAG依据。", "status": "基础版", "next_action": "建立资料分级和来源可信度。"},
            {"name": "多源告警", "source": "Dataminr/Meltwater", "value": "合并RSS、搜索API、官网和法规页面，形成风险提醒。", "status": "基础版", "next_action": "增加告警订阅和去重策略。"},
            {"name": "CRM/Jira/飞书深度集成", "source": "CB Insights/Aha!/Klue", "value": "让产品动作进入真实企业协同流。", "status": "本地队列", "next_action": "配置真实Webhook和回写状态。"},
            {"name": "角色权限和审计", "source": "Productboard/Aha!", "value": "支持产品、销售、研发、测试、管理层不同视角。", "status": "规划中", "next_action": "设计角色权限和操作日志。"},
            {"name": "供应商评分卡", "source": "CB Insights", "value": "支持战略、采购和客户定点判断。", "status": "本次新增", "next_action": "补齐财务、交付、质量和客户证据。"},
        ],
    }


def build_market_map(news_items, competitors, profile):
    customer_segments = profile.get("target_customers", [])
    regions = sorted({item.get("region", "Global") for item in news_items[:12] if item.get("region")}) or ["Global"]
    scenario_terms = []
    for product in profile.get("core_products", []):
        scenario_terms.extend(product.get("target_scenarios", []))
    return [
        {"layer": "目标客户", "summary": "国内外高阶智驾乘用车、Robotaxi与自动驾驶方案商。", "items": [x.get("segment", "") for x in customer_segments]},
        {"layer": "重点区域", "summary": "按公开情报和目标客户区域聚合。", "items": regions},
        {"layer": "应用场景", "summary": "围绕L2+/L3、城市NOA、高速NOA、Robotaxi、补盲和泊车。", "items": sorted(set(scenario_terms))[:8]},
        {"layer": "竞品阵营", "summary": "监控公开激光雷达供应商的量产、定点和技术路线。", "items": [f"{c.get('company')} {c.get('product_name')}" for c in competitors[:8]]},
        {"layer": "风险变量", "summary": "重点关注参数口径、量产节奏、车规验证、成本目标和海外合规。", "items": ["参数口径", "量产节奏", "车规验证", "成本目标", "海外合规"]},
    ]


def build_briefing(news_items, roadmap_actions):
    top = news_items[:3]
    risks = []
    for item in news_items[:8]:
        if item.get("category") in ["竞品动态", "政策法规"] or item.get("opportunity_score", 0) >= 75:
            risks.append(item.get("title", ""))
    return {
        "title": "本轮情报简报",
        "summary": f"本轮识别{len(news_items)}条重点情报，优先关注{top[0].get('title') if top else '待刷新市场情报'}。",
        "top_opportunities": [x.get("title", "") for x in top],
        "risk_signals": risks[:4],
        "recommended_actions": [x.get("action", "") for x in roadmap_actions[:4]],
    }


def build_win_loss(requirements, competitors):
    competitor_names = [c.get("company", "") for c in competitors[:4]]
    return [
        {"stage": "Win因素", "insight": "我方优势来自产品线覆盖、车规量产经验、长距/补盲组合和方案级交付。", "evidence": "EM4/EMX/E1/M1 Plus/P6产品画像", "action": "把产品线匹配和证明材料前置到售前交流。"},
        {"stage": "Loss风险", "insight": "客户可能因竞品已有定点、参数口径不一致、成本目标不清而延后决策。", "evidence": "竞品公开客户与量产状态", "action": "补齐同条件参数对比、成本拆解和车规证明。"},
        {"stage": "客户异议", "insight": "典型问题会集中在探测距离反射率条件、FOV、功耗、可靠性和交付周期。", "evidence": "需求缺失字段与待确认问题", "action": "把待确认问题转成售前问卷和研发评审项。"},
        {"stage": "复盘沉淀", "insight": f"当前已沉淀{len(requirements)}条需求，竞品关注对象包括{'、'.join([x for x in competitor_names if x])}。", "evidence": "需求池与竞品库", "action": "后续接入CRM反馈，形成真实Win/Loss记录。"},
    ]


def build_supplier_scorecards(competitors):
    cards = []
    for c in competitors[:8]:
        customers = c.get("public_customers", [])
        if not isinstance(customers, list):
            customers = [customers] if customers else []
        score = 60
        status = c.get("mass_production_status", "")
        if "量产" in status:
            score += 15
        if customers:
            score += 10
        if c.get("ip_rating") or c.get("temperature_range"):
            score += 5
        cards.append({
            "supplier": c.get("company"),
            "product": c.get("product_name"),
            "score": min(95, score),
            "strength": f"{c.get('technology_route', '技术路线待确认')}，{status or '量产状态待确认'}。",
            "risk": "公开参数需要统一测试条件，客户案例需要确认项目阶段。",
            "evidence_needed": ["同条件参数对比", "车规验证材料", "量产客户证据", "成本与交付周期"],
        })
    return cards


def decision_center():
    profile = read_product_profile()
    conn = db()
    news_items = rows_to_dicts(
        conn.execute("select * from market_news order by opportunity_score desc, fetched_at desc limit 12").fetchall()
    )
    competitors = rows_to_dicts(conn.execute("select * from competitors order by company").fetchall())
    requirements = rows_to_dicts(conn.execute("select * from requirements order by created_at desc limit 8").fetchall())
    proposals = rows_to_dicts(conn.execute("select * from proposals order by created_at desc limit 5").fetchall())
    evaluations = rows_to_dicts(conn.execute("select * from evaluations order by created_at desc limit 8").fetchall())
    conn.close()
    for item in news_items:
        item["fit"] = opportunity_fit(item)
    evidence_chain = build_evidence_chain(news_items)
    battlecards = build_battlecards(competitors)
    requirement_prioritization = build_requirement_prioritization(requirements)
    roadmap_actions = build_roadmap_actions(news_items, requirements, proposals, battlecards)
    capability_roadmap = build_capability_roadmap(news_items, requirements, competitors, proposals)
    market_map = build_market_map(news_items, competitors, profile)
    briefing = build_briefing(news_items, roadmap_actions)
    win_loss = build_win_loss(requirements, competitors)
    supplier_scorecards = build_supplier_scorecards(competitors)
    differentiation = [
        {
            "title": "更快判断机会",
            "proof": "系统会把市场情报和速腾产品画像放在一起看，帮助团队判断是否值得进入需求池。",
            "borrowed_from": "产品价值",
        },
        {
            "title": "结论有依据",
            "proof": "关键结论会保留来源、影响判断和待确认问题，便于团队复核和对齐。",
            "borrowed_from": "产品价值",
        },
        {
            "title": "竞品应对更清楚",
            "proof": "竞品信息会整理成客户可能关心的问题、我方回应和需要准备的证明材料。",
            "borrowed_from": "产品价值",
        },
        {
            "title": "需求不再漏项",
            "proof": "系统会检查车型平台、量产时间、成本、车规、竞品供应商和交付物等关键字段。",
            "borrowed_from": "产品价值",
        },
        {
            "title": "下一步动作明确",
            "proof": "机会可以继续转成研发验证、测试验收、售前材料和客户确认动作。",
            "borrowed_from": "产品价值",
        },
    ]
    executive_answer = (
        "本轮判断会结合市场证据、竞品变化、客户字段完整性和速腾产品画像，帮助团队回答三个问题："
        "这条变化是否值得跟进、和哪些产品线相关、下一步应该补齐什么信息或推进什么动作。"
    )
    return {
        "company": profile.get("company_name"),
        "positioning": profile.get("positioning"),
        "differentiation": differentiation,
        "evidence_chain": evidence_chain,
        "battlecards": battlecards,
        "requirement_prioritization": requirement_prioritization,
        "roadmap_actions": roadmap_actions,
        "capability_roadmap": capability_roadmap,
        "market_map": market_map,
        "briefing": briefing,
        "win_loss": win_loss,
        "supplier_scorecards": supplier_scorecards,
        "evaluations": evaluations,
        "executive_answer": executive_answer,
    }


def simple_entities(text):
    terms = ["L2", "L2+", "L3", "NOA", "AEB", "FMCW", "1550nm", "905nm", "LiDAR", "激光雷达", "毫米波雷达", "Robotaxi", "Europe", "China", "US", "欧盟", "车规"]
    found = [t for t in terms if t.lower() in text.lower()]
    companies = re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", text)
    return sorted(set(found + companies[:8]))


def llm_enrich_article(article, profile):
    title = article.get("title", "")
    text = article.get("text", "") or article.get("summary", "")
    if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")):
        return None
    compact_profile = {
        "positioning": profile.get("positioning"),
        "core_products": profile.get("core_products", []),
        "target_customers": profile.get("target_customers", []),
        "opportunity_keywords": profile.get("opportunity_keywords", []),
        "exclusion_keywords": profile.get("exclusion_keywords", []),
    }
    prompt = (
        "你是车载智驾传感器产品经理的市场情报分析助手。"
        "请基于我方产品画像判断这条公开资讯是否构成市场机会。"
        "只输出JSON，不要Markdown。字段：category, summary, opportunity_score, "
        "credibility_score, tags, matched_products, reason, recommended_action。"
        "category只能是：客户机会、竞品动态、政策法规、技术趋势、行业动态。"
        "opportunity_score为0-100整数，必须结合我方产品匹配度、客户相关度、时间紧迫度和来源可信度。"
        "如果不是车载智驾/激光雷达相关，分数应低。"
    )
    user = json.dumps(
        {
            "company_profile": compact_profile,
            "article": {
                "title": title,
                "source": article.get("source", ""),
                "source_url": article.get("source_url", ""),
                "published_at": article.get("published_at", ""),
                "text": local_summary(text, 1200),
            },
        },
        ensure_ascii=False,
    )
    raw = call_llm([{"role": "system", "content": prompt}, {"role": "user", "content": user}], temperature=0.1)
    parsed = extract_json(raw) if raw else None
    if not isinstance(parsed, dict):
        return None
    return {
        "category": parsed.get("category") or classify_news(title, text),
        "summary": parsed.get("summary") or local_summary(text or title),
        "opportunity_score": int(parsed.get("opportunity_score") or 50),
        "credibility_score": int(parsed.get("credibility_score") or (75 if article.get("source_url") else 50)),
        "tags": to_string_list(parsed.get("tags"))[:8],
        "matched_products": to_string_list(parsed.get("matched_products"))[:5],
        "reason": parsed.get("reason", ""),
        "recommended_action": parsed.get("recommended_action", ""),
    }


def to_string_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(item.get("name") or item.get("type") or json.dumps(item, ensure_ascii=False))
            else:
                out.append(str(item))
        return [x for x in out if x]
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[,，、\n]", value) if x.strip()]
    return [str(value)]


def classify_news(title, text):
    merged = f"{title} {text}".lower()
    if any(x in merged for x in ["design win", "confirmed supplier", "strategic partner", "exclusive deal", "supply products", "定点", "供应商", "战略伙伴", "客户合作"]):
        return "客户机会"
    if any(x in merged for x in ["launch", "发布", "competitor", "竞品", "低成本", "prices", "price", "market report", "supplier says"]):
        return "竞品动态"
    if any(x in merged for x in ["regulation", "法规", "合规", "eu regulation", "欧盟法规", "policy"]):
        return "政策法规"
    if any(x in merged for x in ["oem", "车企", "量产", "客户"]):
        return "客户机会"
    if any(x in merged for x in ["fmcw", "1550", "技术", "算法", "端到端"]):
        return "技术趋势"
    return "行业动态"


def score_opportunity(title, text, category):
    merged = f"{title} {text}".lower()
    score = 45
    for kw in ["l3", "noa", "量产", "定点", "海外", "europe", "oem", "激光雷达", "lidar"]:
        if kw in merged:
            score += 6
    if category in ["客户机会", "政策法规"]:
        score += 8
    return max(0, min(95, score))


def local_summary(text, max_len=160):
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + "..."


def call_llm(messages, temperature=0.2):
    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
    if provider == "deepseek" or (os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY")):
        api_key = clean_secret(os.getenv("DEEPSEEK_API_KEY"))
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    else:
        api_key = clean_secret(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"))
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
    if not api_key:
        return None
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        resp.raise_for_status()
        LLM_STATE["last_call"] = now_iso()
        LLM_STATE["last_error"] = ""
        LLM_STATE["call_count"] += 1
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        LLM_STATE["last_error"] = str(exc)
        return json.dumps({"error": f"LLM调用失败，已降级本地规则: {exc}"}, ensure_ascii=False)


def analyze_requirement(raw_input):
    prompt = (
        "你是车载智驾传感器产品经理。请把客户需求拆解为JSON，字段包括"
        "business_goal, application_scenarios, product_type, performance_requirements,"
        "reliability_requirements, compliance_requirements, deliverables, risks,"
        "questions_to_confirm。必须区分明确事实和待确认项，不要编造硬件参数。"
    )
    llm = call_llm([{"role": "system", "content": prompt}, {"role": "user", "content": raw_input}])
    if llm:
        parsed = extract_json(llm)
        if parsed:
            return parsed
    text = raw_input
    scenarios = []
    for s in ["高速NOA", "城市NOA", "拥堵自动驾驶", "泊车", "Robotaxi", "L3", "L2+"]:
        if s.lower() in text.lower():
            scenarios.append(s)
    if "NOA" in text.upper() and not any("NOA" in s for s in scenarios):
        scenarios.append("NOA")
    if "高速" in text and "高速NOA" not in scenarios:
        scenarios.append("高速NOA")
    if "拥堵" in text and "拥堵自动驾驶" not in scenarios:
        scenarios.append("拥堵自动驾驶")
    is_lidar = any(k in text for k in ["激光雷达", "雷达", "LiDAR", "lidar", "长距", "前向"])
    is_overseas = any(k in text for k in ["海外", "欧洲", "欧盟", "北美", "Europe", "EU", "US"])
    return {
        "business_goal": "待确认，原始需求中可能涉及量产/定点/平台规划",
        "application_scenarios": scenarios or ["待确认"],
        "product_type": "前向长距激光雷达" if is_lidar else "车载智驾传感器方案",
        "performance_requirements": {
            "detection_range": "待确认，需明确反射率条件",
            "frame_rate": "待确认",
            "fov": "待确认",
            "power": "低功耗" if any(k in text for k in ["低功耗", "功耗"]) else "待确认",
        },
        "reliability_requirements": ["车规可靠性"] if any(k in text for k in ["车规", "可靠性", "DV", "PV"]) else ["待确认"],
        "compliance_requirements": ["海外法规", "功能安全"] if is_overseas else ["待确认"],
        "deliverables": ["技术方案", "测试报告", "英文材料"] if any(k in text for k in ["英文", "海外", "欧洲", "测试报告"]) else ["技术方案"],
        "risks": ["量产周期", "成本目标", "认证周期", "竞品定点"],
        "questions_to_confirm": [
            "目标探测距离对应的反射率条件是什么？",
            "整车平台对安装空间、功耗和散热的限制是多少？",
            "客户是否已有竞品供应商进入定点流程？",
        ],
    }


def extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def retrieve_docs(query, limit=4):
    conn = db()
    docs = rows_to_dicts(conn.execute("select * from documents order by created_at desc").fetchall())
    conn.close()
    q_terms = set(re.findall(r"[\w\u4e00-\u9fff]+", query.lower()))
    scored = []
    for doc in docs:
        content = doc.get("content", "")
        d_terms = set(re.findall(r"[\w\u4e00-\u9fff]+", content.lower()))
        score = len(q_terms & d_terms)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:limit]]


def generate_proposal(requirement, competitors):
    analysis = requirement.get("analysis") or analyze_requirement(requirement.get("raw_input", ""))
    profile = read_product_profile()
    context = json.dumps({"company_profile": profile, "requirement": analysis, "competitors": competitors[:4]}, ensure_ascii=False)
    prompt = (
        "你是车载激光雷达产品经理。基于需求拆解和竞品信息，生成产品方案JSON。字段："
        "product_positioning,target_scenarios,key_specs,selling_points,development_tasks,"
        "validation_metrics,risks,ai_generated_content。关键参数必须注明建议/待确认，不得伪造成已验证事实。"
    )
    llm = call_llm([{"role": "system", "content": prompt}, {"role": "user", "content": context}])
    parsed = extract_json(llm) if llm else None
    if parsed:
        return parsed
    scenarios = analysis.get("application_scenarios", ["高速NOA"])
    return {
        "product_positioning": "面向海外L2+/L3高阶智驾的前向长距激光雷达方案",
        "target_scenarios": scenarios,
        "key_specs": {
            "detection_range": "建议250m级别，需研发确认反射率条件",
            "fov_horizontal": "建议100deg至120deg",
            "fov_vertical": "建议25deg至30deg",
            "frame_rate": "建议10Hz至20Hz",
            "reliability": "IP67/IP6K9K、-40C~85C、车规验证",
        },
        "selling_points": ["远距感知", "车规可靠性", "低功耗设计", "海外客户材料支持", "可追溯竞品对比"],
        "development_tasks": ["光机电方案评审", "感知算法接口定义", "样机DV/PV测试", "车规和功能安全材料准备", "成本拆解"],
        "validation_metrics": ["探测距离", "角分辨率", "帧率稳定性", "功耗", "温度循环", "振动", "防水防尘", "误检/漏检率"],
        "risks": ["参数口径需与竞品对齐", "低功耗与远距性能存在权衡", "海外认证周期可能影响定点", "客户需求变更会影响研发排期"],
        "ai_generated_content": "本方案为AI生成初稿，关键硬件参数需研发、测试和质量团队确认后才能对外承诺。",
    }


def fetch_search(query):
    news_key = os.getenv("NEWS_API_KEY")
    bing_key = os.getenv("BING_SEARCH_API_KEY")
    serp_key = os.getenv("SERPAPI_KEY")
    if news_key:
        url = "https://newsapi.org/v2/everything"
        resp = requests.get(url, params={"q": query, "language": "en", "pageSize": 10, "sortBy": "publishedAt", "apiKey": news_key}, timeout=25)
        resp.raise_for_status()
        return [
            {
                "title": a.get("title") or "",
                "source": (a.get("source") or {}).get("name", "NewsAPI"),
                "source_url": a.get("url") or "",
                "published_at": a.get("publishedAt") or "",
                "text": a.get("description") or a.get("content") or "",
            }
            for a in resp.json().get("articles", [])
        ]
    if bing_key:
        resp = requests.get(
            "https://api.bing.microsoft.com/v7.0/news/search",
            headers={"Ocp-Apim-Subscription-Key": bing_key},
            params={"q": query, "count": 10, "mkt": "en-US"},
            timeout=25,
        )
        resp.raise_for_status()
        return [
            {
                "title": a.get("name", ""),
                "source": ((a.get("provider") or [{}])[0]).get("name", "Bing"),
                "source_url": a.get("url", ""),
                "published_at": a.get("datePublished", ""),
                "text": a.get("description", ""),
            }
            for a in resp.json().get("value", [])
        ]
    if serp_key:
        resp = requests.get("https://serpapi.com/search.json", params={"engine": "google_news", "q": query, "api_key": serp_key}, timeout=25)
        resp.raise_for_status()
        return [
            {
                "title": a.get("title", ""),
                "source": a.get("source", "SerpAPI"),
                "source_url": a.get("link", ""),
                "published_at": a.get("date", ""),
                "text": a.get("snippet", ""),
            }
            for a in resp.json().get("news_results", [])
        ]
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        return fetch_rss_articles(rss_url, limit=10)
    except Exception:
        return [
            {
                "title": f"{query} 市场情报样例：海外车企推进高阶智驾传感器方案评估",
                "source": "Local Fallback",
                "source_url": "https://example.com/mock-search",
                "published_at": now_iso(),
                "text": "公开新闻RSS不可用时的本地兜底样例。配置NewsAPI、Bing或SerpAPI后可使用商业搜索源。",
            }
        ]


def clean_feed_text(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"<a[^>]+href=\"([^\"]+)\"[^>]*>.*?</a>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ingest_articles(articles, use_llm=True, llm_limit=30):
    conn = db()
    ids = []
    profile = read_product_profile()
    for idx, article in enumerate(articles):
        title = clean_feed_text(article.get("title", ""))
        text = clean_feed_text(article.get("text", "") or article.get("summary", ""))
        llm_result = llm_enrich_article(article, profile) if use_llm and idx < llm_limit else None
        category = llm_result.get("category") if llm_result else classify_news(title, text)
        score = llm_result.get("opportunity_score") if llm_result else score_opportunity(title, text, category)
        merged = f"{title} {text}".lower()
        matched_profile_terms = [kw for kw in profile.get("opportunity_keywords", []) if kw.lower() in merged]
        excluded_terms = [kw for kw in profile.get("exclusion_keywords", []) if kw.lower() in merged]
        if not llm_result:
            score = min(98, score + min(20, len(matched_profile_terms) * 4))
            if excluded_terms:
                score = max(0, score - 30)
        tags = llm_result.get("tags", []) if llm_result else []
        tags = (tags + simple_entities(f"{title} {text}") + matched_profile_terms)[:10]
        if llm_result:
            tags = ["DeepSeek分析"] + tags
        summary = llm_result.get("summary") if llm_result else local_summary(text or title)
        if llm_result and llm_result.get("reason"):
            summary = f"{summary} 分析依据：{llm_result.get('reason')}"
        item = {
            "title": title,
            "source": article.get("source", ""),
            "source_url": article.get("source_url", ""),
            "published_at": article.get("published_at", ""),
            "region": article.get("region", "Global"),
            "category": category,
            "summary": summary,
            "entities": simple_entities(f"{title} {text}"),
            "opportunity_score": score,
            "credibility_score": llm_result.get("credibility_score") if llm_result else (75 if article.get("source_url") else 50),
            "tags": tags,
            "status": "待审核",
        }
        ids.append(insert_news(conn, item))
    conn.close()
    return ids


def crawl_url(url):
    resp = requests.get(url, headers={"User-Agent": "AutoSenseAI/0.1"}, timeout=25)
    resp.raise_for_status()
    html = resp.text
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else url
    text = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return {"title": title, "source": urlparse(url).netloc, "source_url": url, "published_at": now_iso(), "text": text[:5000]}


def save_document(title, content, source_url="", metadata=None):
    chunks = [content[i : i + 900] for i in range(0, len(content), 900)]
    doc_id = "doc_" + uuid.uuid4().hex[:10]
    conn = db()
    conn.execute(
        "insert into documents values (?,?,?,?,?,?,?)",
        (doc_id, title, source_url, content, json.dumps(chunks, ensure_ascii=False), json.dumps(metadata or {}, ensure_ascii=False), now_iso()),
    )
    conn.commit()
    conn.close()
    return doc_id


def delete_document(doc_id):
    conn = db()
    conn.execute("delete from documents where id=?", (doc_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "id": doc_id}


def evaluate_output(task_type, input_id, output, reviewer_comment=""):
    required = {
        "requirement": ["business_goal", "application_scenarios", "risks", "questions_to_confirm"],
        "proposal": ["product_positioning", "key_specs", "validation_metrics", "risks"],
        "news": ["summary", "category", "opportunity_score"],
    }.get(task_type, [])
    output_text = json.dumps(output, ensure_ascii=False) if not isinstance(output, str) else output
    coverage = sum(1 for k in required if k in output_text) / max(1, len(required)) * 100
    hallucination = bool(re.search(r"保证|绝对|100%|已认证", output_text))
    trace = 70 if "source" in output_text or "来源" in output_text else 45
    accuracy = max(40, min(92, coverage - (20 if hallucination else 0) + 10))
    eid = "eval_" + uuid.uuid4().hex[:10]
    conn = db()
    conn.execute(
        "insert into evaluations values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            eid,
            task_type,
            input_id,
            os.getenv("OPENAI_MODEL") or "local-rules",
            "v0.1",
            output_text,
            accuracy,
            coverage,
            trace,
            1 if hallucination else 0,
            "待人工确认",
            reviewer_comment,
            now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return eid


def create_integration(integration_type, target, payload):
    status = "queued_local"
    response = "未配置真实集成Webhook，已创建本地待推送任务。"
    webhook = os.getenv(f"{integration_type.upper()}_WEBHOOK_URL")
    if webhook:
        try:
            resp = requests.post(webhook, json=payload, timeout=20)
            status = "sent" if resp.ok else "failed"
            response = resp.text[:1000]
        except Exception as exc:
            status = "failed"
            response = str(exc)
    iid = "int_" + uuid.uuid4().hex[:10]
    conn = db()
    conn.execute(
        "insert into integrations values (?,?,?,?,?,?,?)",
        (iid, integration_type, target, json.dumps(payload, ensure_ascii=False), status, response, now_iso()),
    )
    conn.commit()
    conn.close()
    return {"id": iid, "status": status, "response": response}


def run_auto_analysis(payload):
    search_query = payload.get("search_query") or "automotive lidar ADAS L3 Europe"
    source_url = payload.get("source_url", "").strip()
    doc_title = payload.get("doc_title") or "用户补充行业资料"
    doc_content = payload.get("doc_content", "").strip()
    raw_requirement = payload.get("raw_requirement", "").strip()
    customer_name = payload.get("customer_name") or "匿名目标客户"
    region = payload.get("region") or "Europe"

    news_ids = []
    if search_query:
        news_ids.extend(ingest_articles(fetch_search(search_query)))
    if source_url:
        article = crawl_url(source_url)
        news_ids.extend(ingest_articles([article]))
        save_document(article["title"], article["text"], article["source_url"], {"type": "webpage"})
    if doc_content:
        save_document(doc_title, doc_content, payload.get("doc_source_url", ""), {"type": "manual"})

    if not raw_requirement:
        raw_requirement = (
            "欧洲某车企计划在2027年量产L3车型，需要一款适配高速NOA和拥堵自动驾驶场景的"
            "前向长距激光雷达，要求远距离探测、低功耗、满足车规可靠性，并希望供应商提供"
            "英文技术材料和测试报告。"
        )

    analysis = analyze_requirement(raw_requirement)
    rid = "req_" + uuid.uuid4().hex[:10]
    conn = db()
    conn.execute(
        "insert into requirements values (?,?,?,?,?,?,?,?)",
        (
            rid,
            customer_name,
            region,
            raw_requirement,
            json.dumps(analysis, ensure_ascii=False),
            payload.get("priority", "P1"),
            0,
            now_iso(),
        ),
    )
    conn.commit()
    competitors = rows_to_dicts(conn.execute("select * from competitors").fetchall())
    req_d = {
        "id": rid,
        "customer_name": customer_name,
        "region": region,
        "raw_input": raw_requirement,
        "analysis": analysis,
    }
    proposal = generate_proposal(req_d, competitors)
    pid = "prop_" + uuid.uuid4().hex[:10]
    conn.execute(
        "insert into proposals values (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            pid,
            rid,
            proposal.get("product_positioning", ""),
            json.dumps(proposal.get("target_scenarios", []), ensure_ascii=False),
            json.dumps(proposal.get("key_specs", {}), ensure_ascii=False),
            json.dumps(proposal.get("selling_points", []), ensure_ascii=False),
            json.dumps(proposal.get("development_tasks", []), ensure_ascii=False),
            json.dumps(proposal.get("validation_metrics", []), ensure_ascii=False),
            json.dumps(proposal.get("risks", []), ensure_ascii=False),
            proposal.get("ai_generated_content", ""),
            "待评审",
            now_iso(),
        ),
    )
    conn.commit()
    latest_news = rows_to_dicts(
        conn.execute(
            "select * from market_news order by opportunity_score desc, fetched_at desc limit 5"
        ).fetchall()
    )
    conn.close()
    eval_req = evaluate_output("requirement", rid, analysis)
    eval_prop = evaluate_output("proposal", pid, proposal)
    return {
        "news_ids": news_ids,
        "requirement_id": rid,
        "proposal_id": pid,
        "market_opportunities": latest_news,
        "requirement_analysis": analysis,
        "competitor_evidence": competitors[:4],
        "proposal": proposal,
        "evaluation_ids": [eval_req, eval_prop],
        "interview_summary": {
            "project_value": "把市场情报、客户需求和竞品参数转化为可执行的车载智驾传感器产品方案。",
            "pm_capability": ["行业调研", "需求分析", "产品定义", "研发协同", "测试验收", "售前支持"],
            "ai_capability": ["DeepSeek需求拆解", "RAG资料问答", "AI输出评测", "人工确认闭环"],
            "hardware_capability": ["L2+/L3", "高速NOA", "激光雷达参数", "车规可靠性", "量产风险"],
        },
    }


def fetch_rss_articles(url, limit=20):
    resp = requests.get(url, timeout=25)
    resp.raise_for_status()
    items = re.findall(r"<item\b.*?</item>", resp.text, flags=re.I | re.S)[:limit]
    articles = []
    for item in items:
        title = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, flags=re.I | re.S)
        link = re.search(r"<link>(.*?)</link>", item, flags=re.I | re.S)
        desc = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>", item, flags=re.I | re.S)
        source = re.search(r"<source[^>]*>(.*?)</source>", item, flags=re.I | re.S)
        raw_desc = clean_feed_text(desc.group(1) or desc.group(2) if desc else "")
        clean_title = clean_feed_text(title.group(1) or title.group(2) if title else "RSS item")
        articles.append({
            "title": clean_title,
            "source": (source.group(1).strip() if source else urlparse(url).netloc),
            "source_url": link.group(1).strip() if link else url,
            "published_at": now_iso(),
            "text": raw_desc or clean_title,
        })
    return articles


def run_monitor_once():
    config = read_monitor_config()
    articles = []
    for query in config.get("queries", []):
        try:
            articles.extend(fetch_search(query))
        except Exception as exc:
            MONITOR_STATE["last_error"] = f"搜索失败: {exc}"
    for rss in config.get("rss_urls", []):
        try:
            articles.extend(fetch_rss_articles(rss, limit=15))
        except Exception as exc:
            MONITOR_STATE["last_error"] = f"RSS失败: {exc}"
    for url in config.get("web_urls", []):
        try:
            articles.append(crawl_url(url))
        except Exception as exc:
            MONITOR_STATE["last_error"] = f"网页抓取失败: {exc}"
    ids = ingest_articles(articles) if articles else []
    conn = db()
    high = rows_to_dicts(
        conn.execute(
            "select * from market_news where opportunity_score >= ? order by fetched_at desc, opportunity_score desc limit 10",
            (int(config.get("push_threshold", 80)),),
        ).fetchall()
    )
    conn.close()
    for item in high[:3]:
        payload = {
            "title": item["title"],
            "category": item["category"],
            "opportunity_score": item["opportunity_score"],
            "summary": item["summary"],
            "source_url": item["source_url"],
            "recommended_action": "进入客户机会池，评估是否生成产品方案或售前材料。",
        }
        for channel in config.get("push_channels", ["crm"]):
            create_integration(channel, "AutoSense Monitor", payload)
    MONITOR_STATE["last_run"] = now_iso()
    MONITOR_STATE["last_count"] = len(ids)
    return {"inserted": ids, "count": len(ids), "pushed": len(high[:3]), "high_opportunities": high[:3]}


def monitor_loop():
    while MONITOR_STATE["running"]:
        try:
            run_monitor_once()
            MONITOR_STATE["last_error"] = ""
        except Exception as exc:
            MONITOR_STATE["last_error"] = str(exc)
        interval = read_monitor_config().get("interval_minutes", 30) * 60
        for _ in range(max(1, int(interval))):
            if not MONITOR_STATE["running"]:
                break
            time.sleep(1)


def start_monitor():
    config = read_monitor_config()
    write_monitor_config({**config, "enabled": True})
    if MONITOR_STATE["running"]:
        return monitor_status()
    MONITOR_STATE["running"] = True
    thread = threading.Thread(target=monitor_loop, daemon=True)
    MONITOR_STATE["thread"] = thread
    thread.start()
    return monitor_status()


def stop_monitor():
    write_monitor_config({**read_monitor_config(), "enabled": False})
    MONITOR_STATE["running"] = False
    return monitor_status()


def monitor_status():
    config = read_monitor_config()
    return {
        "running": MONITOR_STATE["running"],
        "enabled": config.get("enabled", False),
        "last_run": MONITOR_STATE["last_run"],
        "last_count": MONITOR_STATE["last_count"],
        "last_error": MONITOR_STATE["last_error"],
        "config": config,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, status=200, body=None, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if body is None:
            body = {}
        if content_type == "application/json":
            self.wfile.write(json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8"))
        else:
            self.wfile.write(body if isinstance(body, bytes) else str(body).encode("utf-8"))

    def do_OPTIONS(self):
        self._send(204)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/" or path == "/index.html":
                return self.serve_static("index.html")
            if path.startswith("/static/"):
                return self.serve_static(path.replace("/static/", "", 1))
            if path == "/api/health":
                cfg = read_config()
                return self._send(body={
                    "ok": True,
                    "time": now_iso(),
                    "llm": cfg["deepseek_configured"] or cfg["openai_configured"],
                    "llm_provider": cfg["llm_provider"],
                    "news_api": bool(os.getenv("NEWS_API_KEY") or os.getenv("BING_SEARCH_API_KEY") or os.getenv("SERPAPI_KEY")),
                    "market_source": "commercial_api" if bool(os.getenv("NEWS_API_KEY") or os.getenv("BING_SEARCH_API_KEY") or os.getenv("SERPAPI_KEY")) else "public_rss",
                    "llm_state": LLM_STATE,
                    "database": str(DB_PATH),
                })
            if path == "/api/config":
                return self._send(body=read_config())
            if path == "/api/monitor":
                return self._send(body=monitor_status())
            if path == "/api/product-profile":
                return self._send(body=read_product_profile())
            if path == "/api/opportunities":
                limit = int(query.get("limit", ["20"])[0])
                return self._send(body=get_opportunities(limit))
            if path == "/api/decision-center":
                return self._send(body=decision_center())
            if path == "/api/news":
                conn = db()
                rows = conn.execute("select * from market_news order by opportunity_score desc, fetched_at desc").fetchall()
                conn.close()
                return self._send(body=rows_to_dicts(rows))
            if path == "/api/competitors":
                conn = db()
                rows = conn.execute("select * from competitors order by company").fetchall()
                conn.close()
                return self._send(body=rows_to_dicts(rows))
            if path == "/api/requirements":
                conn = db()
                rows = conn.execute("select * from requirements order by created_at desc").fetchall()
                conn.close()
                return self._send(body=rows_to_dicts(rows))
            if path == "/api/proposals":
                conn = db()
                rows = conn.execute("select * from proposals order by created_at desc").fetchall()
                conn.close()
                return self._send(body=rows_to_dicts(rows))
            if path == "/api/documents":
                conn = db()
                rows = conn.execute("select id,title,source_url,metadata,created_at from documents order by created_at desc").fetchall()
                conn.close()
                return self._send(body=rows_to_dicts(rows))
            if path == "/api/evaluations":
                conn = db()
                rows = conn.execute("select * from evaluations order by created_at desc").fetchall()
                conn.close()
                return self._send(body=rows_to_dicts(rows))
            if path == "/api/search":
                q = query.get("q", ["automotive lidar ADAS L3"])[0]
                articles = fetch_search(q)
                return self._send(body=articles)
            return self._send(404, {"error": "not found"})
        except Exception as exc:
            return self._send(500, {"error": str(exc)})

    def serve_static(self, name):
        target = STATIC_DIR / name
        if not target.exists() or not target.is_file():
            return self._send(404, {"error": "static file not found"})
        suffix = target.suffix.lower()
        content_type = "text/html" if suffix == ".html" else "text/css" if suffix == ".css" else "application/javascript"
        return self._send(200, target.read_bytes(), content_type)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/news/ingest-search":
                articles = fetch_search(payload.get("query", "automotive lidar ADAS"))
                ids = ingest_articles(articles)
                return self._send(body={"inserted": ids, "count": len(ids)})
            if path == "/api/config":
                cfg = write_config(payload)
                return self._send(body=cfg)
            if path == "/api/ai/test":
                content = call_llm(
                    [
                        {"role": "system", "content": "你是AutoSense AI的连接测试助手。"},
                        {"role": "user", "content": "请用一句中文回复：DeepSeek接口连接成功，并说明你可以用于智驾产品需求拆解。"},
                    ],
                    temperature=0.1,
                )
                if not content:
                    return self._send(body={"ok": False, "message": "未配置可用的大模型API Key，当前仍可使用本地规则兜底。"})
                return self._send(body={"ok": "失败" not in content and "error" not in content.lower(), "message": content})
            if path == "/api/news/ingest-rss":
                # Lightweight RSS parsing without extra dependencies.
                url = payload.get("url", "")
                resp = requests.get(url, timeout=25)
                resp.raise_for_status()
                items = re.findall(r"<item\b.*?</item>", resp.text, flags=re.I | re.S)[:20]
                articles = []
                for item in items:
                    title = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, flags=re.I | re.S)
                    link = re.search(r"<link>(.*?)</link>", item, flags=re.I | re.S)
                    desc = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>", item, flags=re.I | re.S)
                    articles.append({
                        "title": (title.group(1) or title.group(2) if title else "RSS item").strip(),
                        "source": urlparse(url).netloc,
                        "source_url": link.group(1).strip() if link else url,
                        "published_at": now_iso(),
                        "text": re.sub(r"<[^>]+>", " ", (desc.group(1) or desc.group(2) if desc else "")),
                    })
                ids = ingest_articles(articles)
                return self._send(body={"inserted": ids, "count": len(ids)})
            if path == "/api/crawl":
                article = crawl_url(payload.get("url", ""))
                ids = ingest_articles([article])
                save_document(article["title"], article["text"], article["source_url"], {"type": "crawl"})
                return self._send(body={"news_ids": ids, "article": article})
            if path == "/api/documents":
                doc_id = save_document(payload.get("title", "Untitled"), payload.get("content", ""), payload.get("source_url", ""), payload.get("metadata", {}))
                return self._send(body={"id": doc_id})
            if path == "/api/documents/delete":
                return self._send(body=delete_document(payload.get("id", "")))
            if path == "/api/rag/query":
                docs = retrieve_docs(payload.get("query", ""))
                prompt = "基于检索文档回答问题，必须说明依据，不确定就说待确认。"
                context = json.dumps(docs, ensure_ascii=False)
                llm = call_llm([{"role": "system", "content": prompt}, {"role": "user", "content": payload.get("query", "") + "\n文档:\n" + context}])
                answer = llm or ("基于本地检索，找到相关文档：" + "；".join([d["title"] for d in docs]) if docs else "未检索到相关文档。")
                return self._send(body={"answer": answer, "sources": docs})
            if path == "/api/requirements":
                rid = "req_" + uuid.uuid4().hex[:10]
                analysis = analyze_requirement(payload.get("raw_input", ""))
                conn = db()
                conn.execute(
                    "insert into requirements values (?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        payload.get("customer_name", "匿名客户"),
                        payload.get("region", "Global"),
                        payload.get("raw_input", ""),
                        json.dumps(analysis, ensure_ascii=False),
                        payload.get("priority", "P1"),
                        0,
                        now_iso(),
                    ),
                )
                conn.commit()
                conn.close()
                evaluate_output("requirement", rid, analysis)
                return self._send(body={"id": rid, "analysis": analysis})
            if path == "/api/proposals":
                requirement_id = payload.get("requirement_id")
                conn = db()
                req = conn.execute("select * from requirements where id=?", (requirement_id,)).fetchone()
                competitors = rows_to_dicts(conn.execute("select * from competitors").fetchall())
                if not req:
                    conn.close()
                    return self._send(404, {"error": "requirement not found"})
                req_d = rows_to_dicts([req])[0]
                proposal = generate_proposal(req_d, competitors)
                pid = "prop_" + uuid.uuid4().hex[:10]
                conn.execute(
                    "insert into proposals values (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        pid,
                        requirement_id,
                        proposal.get("product_positioning", ""),
                        json.dumps(proposal.get("target_scenarios", []), ensure_ascii=False),
                        json.dumps(proposal.get("key_specs", {}), ensure_ascii=False),
                        json.dumps(proposal.get("selling_points", []), ensure_ascii=False),
                        json.dumps(proposal.get("development_tasks", []), ensure_ascii=False),
                        json.dumps(proposal.get("validation_metrics", []), ensure_ascii=False),
                        json.dumps(proposal.get("risks", []), ensure_ascii=False),
                        proposal.get("ai_generated_content", ""),
                        "待评审",
                        now_iso(),
                    ),
                )
                conn.commit()
                conn.close()
                evaluate_output("proposal", pid, proposal)
                return self._send(body={"id": pid, **proposal})
            if path == "/api/evaluations":
                eid = evaluate_output(payload.get("task_type", "manual"), payload.get("input_id", ""), payload.get("output", ""), payload.get("reviewer_comment", ""))
                return self._send(body={"id": eid})
            if path == "/api/integrations/send":
                result = create_integration(payload.get("integration_type", "jira"), payload.get("target", ""), payload.get("payload", {}))
                return self._send(body=result)
            if path == "/api/auto/analyze":
                return self._send(body=run_auto_analysis(payload))
            if path == "/api/monitor/config":
                return self._send(body=write_monitor_config(payload))
            if path == "/api/monitor/run":
                return self._send(body=run_monitor_once())
            if path == "/api/monitor/start":
                return self._send(body=start_monitor())
            if path == "/api/monitor/stop":
                return self._send(body=stop_monitor())
            if path == "/api/product-profile":
                return self._send(body=write_product_profile(payload))
            if path == "/api/opportunities/analyze":
                return self._send(body=analyze_opportunity(payload.get("news_id", "")))
            if path == "/api/competitors/realtime":
                return self._send(body=realtime_competitor_analysis())
            return self._send(404, {"error": "not found"})
        except Exception as exc:
            return self._send(500, {"error": str(exc)})


def main():
    load_env_file()
    init_db()
    if read_monitor_config().get("enabled"):
        start_monitor()
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AutoSense AI running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
