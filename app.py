"""
产品级联网搜索 Agent GUI Demo
Streamlit + 现代化 UI（ChatGPT / Perplexity / Notion 风格）

运行方式：
    streamlit run app.py

说明：
    - GUI 直接调用 agent.run_agent(query)，完整链路为 Evidence-based Answer 四段式：
      query -> agent.need_search() -> 加载 prompt.txt
            -> search.web_search()（百度千帆 AI 搜索 API，纯检索）
            -> evidence.build_evidence()（结构化证据构建，产出带 evidence_id 的 Evidence 列表）
            -> llm.generate_answer(query, evidence)（百度千帆 LLM API，基于 Evidence 生成，约束禁止用自身知识补充）-> GUI。
    - search / llm 是两个独立的百度千帆接口调用；evidence 是纯本地处理，不发起网络请求。
    - 需要在 .env（本地）或 Streamlit Cloud Secrets（云端）中配置 BAIDU_QIANFAN_API_KEY，
      详见 README.md。
"""

import json
import os
import time

import streamlit as st

import agent

# ============================================================
# 页面基础配置
# ============================================================
st.set_page_config(
    page_title="联网搜索 Agent · Demo",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Streamlit Cloud 的 Secrets 桥接到环境变量（search.py / llm.py 会优先读 st.secrets，这里是兜底）
if not os.environ.get("BAIDU_QIANFAN_API_KEY"):
    try:
        os.environ["BAIDU_QIANFAN_API_KEY"] = st.secrets["BAIDU_QIANFAN_API_KEY"]
    except Exception:
        pass

# ============================================================
# 全局样式（现代化卡片风格）
# ============================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    /* 页面整体背景：浅灰白 */
    .stApp {
        background: linear-gradient(180deg, #f7f8fa 0%, #f2f3f6 100%);
    }

    /* 隐藏默认的 Streamlit 装饰元素，去掉"老旧后台"感 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    /* 卡片容器（st.container(border=True) 渲染出的外层元素） */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
        box-shadow: 0 4px 18px rgba(15, 23, 42, 0.05);
        background: #ffffff;
    }

    /* 标题渐变色 */
    .hero-title {
        text-align: center;
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem;
        background: linear-gradient(90deg, #4f46e5, #7c3aed 55%, #2563eb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero-sub {
        text-align: center;
        color: #6b7280;
        font-size: 0.95rem;
        margin-bottom: 0;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #ecfdf5;
        color: #059669;
        border: 1px solid #a7f3d0;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.1rem;
    }
    .section-caption {
        color: #9ca3af;
        font-size: 0.82rem;
        margin-bottom: 0.6rem;
    }

    /* 输入框样式 */
    .stTextInput > div > div > input {
        border-radius: 14px !important;
        border: 1.5px solid #e5e7eb !important;
        padding: 0.75rem 1rem !important;
        font-size: 1rem !important;
        background: #f9fafb !important;
        transition: all 0.15s ease-in-out;
    }
    .stTextInput > div > div > input:focus {
        border-color: #7c3aed !important;
        box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.12) !important;
        background: #ffffff !important;
    }

    /* 主按钮：渐变现代风格 */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        color: #ffffff;
        border: none;
        border-radius: 999px;
        padding: 0.6rem 1.6rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        box-shadow: 0 6px 16px rgba(124, 58, 237, 0.3);
        transition: all 0.15s ease-in-out;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(124, 58, 237, 0.38);
    }
    div[data-testid="stButton"] > button[kind="primary"]:disabled {
        background: linear-gradient(90deg, #a5a6f6, #c4b5fd);
        box-shadow: none;
        transform: none;
        color: #f5f3ff;
    }

    /* 次要按钮（示例 chips） */
    div[data-testid="stButton"] > button[kind="secondary"] {
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        color: #4b5563;
        font-size: 0.8rem;
        padding: 0.25rem 0.9rem;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        border-color: #a5b4fc;
        color: #4f46e5;
        background: #eef2ff;
    }

    /* 代码块（Agent 输入）圆角处理 */
    div[data-testid="stCodeBlock"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid #1f2937;
    }

    /* 结果小卡片 */
    .result-card {
        border: 1px solid #eef0f3;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.65rem;
        background: #fcfcfd;
        transition: all 0.15s ease-in-out;
    }
    .result-card:hover {
        border-color: #c7d2fe;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.08);
    }
    .result-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: #1d4ed8;
        margin-bottom: 2px;
    }
    .result-url {
        font-size: 0.75rem;
        color: #9ca3af;
        margin-bottom: 4px;
    }
    .result-snippet {
        font-size: 0.85rem;
        color: #4b5563;
        line-height: 1.5;
    }

    /* 信息不足降级策略：回答等级徽标 */
    .confidence-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 0.7rem;
    }
    .confidence-badge.sufficient { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
    .confidence-badge.partial    { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
    .confidence-badge.none       { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .confidence-badge.conflict   { background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; }
    .confidence-badge.unknown    { background: #f3f4f6; color: #6b7280; border: 1px solid #e5e7eb; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Session State 初始化
# ============================================================
defaults = {
    "is_searching": False,
    "query_text": "",
    "pending_query": "",
    "pipeline_result": None,
    "last_query": "",
    "elapsed": 0.0,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

EXAMPLE_QUERIES = ["2026 年 AI Agent 发展趋势", "Streamlit 最佳实践", "RAG 与联网搜索结合方案"]

# 信息不足降级策略：回答等级 -> (图标, CSS 修饰类, 展示文案)，档位名称需与 prompt.txt 保持一致
CONFIDENCE_BADGES = {
    "检索充分": ("🟢", "sufficient", "检索充分 · 正常回答"),
    "部分支持": ("🟡", "partial", "部分支持 · 已标注缺失信息"),
    "没有支持": ("🔴", "none", "没有支持 · 明确无法确认"),
    "来源冲突": ("🟠", "conflict", "来源冲突 · 已并列展示"),
}
CONFIDENCE_BADGE_UNKNOWN = ("⚪", "unknown", "未标注回答等级")

# ============================================================
# 顶部：标题 + 状态说明
# ============================================================
st.markdown('<div class="hero-title">🔎 联网搜索 Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">输入问题，自动联网检索并整理为 Agent 可用的结构化上下文</div>',
    unsafe_allow_html=True,
)

col_a, col_b, col_c = st.columns([1, 1, 1])
with col_b:
    st.markdown(
        '<div style="text-align:center; margin-top:0.6rem;">'
        '<span class="status-pill">🟢 搜索引擎就绪 · Agent 引擎在线</span>'
        "</div>",
        unsafe_allow_html=True,
    )

st.write("")
st.divider()

# ============================================================
# 中间：输入卡片（居中，宽度 ~60%）
# ============================================================
left_pad, center, right_pad = st.columns([1, 3, 1])
with center:
    with st.container(border=True):
        st.markdown('<div class="section-title">💬 提出你的问题</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-caption">系统会联网搜索相关资料，并交给 Agent 整理成结构化输入</div>',
            unsafe_allow_html=True,
        )

        query_input = st.text_input(
            "搜索内容",
            key="query_text",
            placeholder="例如：2026 年大模型 Agent 的落地方向有哪些？",
            label_visibility="collapsed",
            disabled=st.session_state.is_searching,
        )

        # 示例问题 chips
        chip_cols = st.columns(len(EXAMPLE_QUERIES))
        for i, eq in enumerate(EXAMPLE_QUERIES):
            with chip_cols[i]:
                if st.button(f"✨ {eq}", key=f"chip_{i}", disabled=st.session_state.is_searching):
                    st.session_state.query_text = eq
                    st.rerun()

        st.write("")
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1.3, 1])
        with btn_col2:
            search_clicked = st.button(
                "🔎 搜索中..." if st.session_state.is_searching else "🚀 开始搜索",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.is_searching,
            )

        if search_clicked and query_input.strip():
            st.session_state.pending_query = query_input.strip()
            st.session_state.is_searching = True
            st.rerun()
        elif search_clicked and not query_input.strip():
            st.warning("⚠️ 请先输入搜索内容")

# ============================================================
# 执行真实 Agent Pipeline（two-run 状态机，确保按钮 loading 状态可见）
# query -> agent.need_search() -> 加载 prompt.txt
#       -> search.web_search()（百度千帆搜索 API）
#       -> evidence.build_evidence()（结构化证据构建，本地处理）
#       -> llm.generate_answer(query, evidence)（百度千帆 LLM API，基于证据生成）
# ============================================================
if st.session_state.is_searching:
    q = st.session_state.pending_query
    t0 = time.time()
    with st.container():
        _, mid, _ = st.columns([1, 3, 1])
        with mid:
            with st.status(f"🔍 正在执行 Agent Pipeline「{q}」...", expanded=True) as status:
                st.write("🧠 Query Understanding：判断是否命中实时性关键词（need_search）...")
                st.write("📜 加载系统 Prompt（prompt.txt）...")
                st.write("🌐 Step 1/3：调用百度千帆 AI 搜索接口（web_search，纯检索）...")
                st.write("🧩 Step 2/3：Evidence Extraction / Builder（结构化证据抽取，本地处理）...")
                st.write("🤖 Step 3/3：调用百度千帆 LLM 接口（chat/completions，基于 Evidence 生成）...")

                status.update(label="🌐 正在执行 Search → Evidence → LLM 三段式 Pipeline（ernie-4.5-turbo-128k）...", state="running")
                try:
                    result = agent.run_agent(q)
                except Exception as exc:  # 兜底：配置缺失 / prompt.txt 缺失等意外错误也要在 UI 上可见，不允许静默失败
                    result = {
                        "query": q,
                        "need_search": None,
                        "system_prompt": None,
                        "success": False,
                        "error": f"Agent Pipeline 执行异常: {exc}",
                        "answer": None,
                        "answer_level": None,
                        "references": [],
                        "evidence": [],
                        "raw": None,
                    }

                if result["success"]:
                    st.write("✅ 已获取真实 LLM 回答")
                    status.update(label="✅ Pipeline 执行完成", state="complete", expanded=False)
                else:
                    st.write(f"❌ {result['error']}")
                    status.update(label="❌ Pipeline 执行失败", state="error", expanded=True)

    st.session_state.pipeline_result = result
    st.session_state.last_query = q
    st.session_state.elapsed = round(time.time() - t0, 2)
    st.session_state.is_searching = False
    st.rerun()

# ============================================================
# 下方：结果区域（左右分栏）
# ============================================================
result = st.session_state.pipeline_result
if result:
    st.write("")
    st.divider()

    meta_col1, meta_col2, meta_col3 = st.columns([2, 1, 1])
    with meta_col1:
        st.markdown(f"##### 📌 查询：`{st.session_state.last_query}`")
    with meta_col2:
        st.caption(f"⏱ 耗时 {st.session_state.elapsed}s")
    with meta_col3:
        st.caption("✅ 真实 Pipeline" if result["success"] else "❌ 调用失败")

    if not result["success"]:
        st.error(f"Agent Pipeline 未能获取到结果：{result['error']}")
        st.caption("请检查 BAIDU_QIANFAN_API_KEY 是否已在 .env / Streamlit Cloud Secrets 中正确配置。")
    else:
        st.write("")
        result_left, result_right = st.columns(2)

        # ---- 左侧：真实检索来源 + Pipeline 执行详情（白盒） ----
        with result_left:
            with st.container(border=True):
                references = result.get("references") or []
                st.markdown('<div class="section-title">📚 检索到的真实来源</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="section-caption">百度联网检索返回 {len(references)} 条引用来源</div>',
                    unsafe_allow_html=True,
                )
                if references:
                    for ref in references:
                        st.markdown(
                            f"""
                            <div class="result-card">
                                <div class="result-title">🔗 {ref.get('title', '（无标题）')}</div>
                                <div class="result-url">{ref.get('url', '')} · {ref.get('website', '')} · {ref.get('date', '')}</div>
                                <div class="result-snippet">{(ref.get('content') or '')[:160]}…</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("本次回答未附带引用来源（模型判断无需检索或检索为空）。")

            # ---- 新增：Evidence 内容（search -> evidence 结构化证据构建的产出，LLM 的唯一事实来源） ----
            with st.container(border=True):
                evidence_list = result.get("evidence") or []
                st.markdown('<div class="section-title">🧩 Evidence（结构化证据）</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="section-caption">从 {len(references)} 条检索结果中提取出 {len(evidence_list)} 条 Evidence，'
                    f"每条带 evidence_id，LLM 只能依据这份 Evidence 作答，不得用自身知识补充</div>",
                    unsafe_allow_html=True,
                )
                if evidence_list:
                    for ev in evidence_list:
                        st.markdown(
                            f"""
                            <div class="result-card">
                                <div class="result-title">🏷️ [{ev.get('evidence_id', '')}] {ev.get('title', '（无标题）')}</div>
                                <div class="result-url">{ev.get('url', '')} · {ev.get('source', '')}</div>
                                <div class="result-snippet">{(ev.get('content') or '')[:160]}…</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with st.expander(f"查看 Evidence 原始 JSON（{len(evidence_list)} 条）"):
                        st.code(json.dumps(evidence_list, ensure_ascii=False, indent=2), language="json")
                else:
                    st.caption("本次未构建出可用 Evidence（检索结果为空，或检索结果均无正文内容）。")

            with st.container(border=True):
                st.markdown('<div class="section-title">🧭 Pipeline 执行详情</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="section-caption">query -&gt; need_search -&gt; prompt.txt -&gt; search.web_search -&gt; evidence.build_evidence -&gt; llm.generate_answer</div>',
                    unsafe_allow_html=True,
                )

                hit_label = "🟢 命中" if result["need_search"] else "⚪ 未命中"
                level_icon, _, level_text = CONFIDENCE_BADGES.get(result.get("answer_level"), CONFIDENCE_BADGE_UNKNOWN)
                st.markdown(
                    f"""
                    <div class="result-card">
                        <div class="result-title">1️⃣ Query Understanding（need_search）</div>
                        <div class="result-snippet">{hit_label} 实时性关键词判断，用于可解释性标注（不作为是否调用 LLM 的开关）</div>
                    </div>
                    <div class="result-card">
                        <div class="result-title">2️⃣ Evidence Extraction / Builder</div>
                        <div class="result-snippet">从 {len(references)} 条检索结果中提取出 {len(evidence_list)} 条结构化证据（evidence_id / source / title / url / content），详见上方「Evidence（结构化证据）」卡片</div>
                    </div>
                    <div class="result-card">
                        <div class="result-title">3️⃣ 信息不足降级策略（回答等级判定）</div>
                        <div class="result-snippet">{level_icon} {level_text} —— LLM 依据 Evidence 支持程度自评档位，决定采用「正常回答 / 标注缺失 / 明确无法确认 / 展示冲突」中的哪种输出策略</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("查看 prompt.txt 内容（system message）"):
                    st.code(result["system_prompt"], language="text")
                with st.expander("查看原始 API 响应（raw JSON）"):
                    st.code(json.dumps(result["raw"], ensure_ascii=False, indent=2), language="json")

        # ---- 右侧：Agent 最终回答 ----
        with result_right:
            with st.container(border=True):
                st.markdown('<div class="section-title">🤖 Agent 最终回答</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="section-caption">百度千帆 LLM 基于结构化 Evidence 生成的回答（真实调用，非模拟）</div>',
                    unsafe_allow_html=True,
                )
                icon, css_cls, badge_text = CONFIDENCE_BADGES.get(result.get("answer_level"), CONFIDENCE_BADGE_UNKNOWN)
                st.markdown(
                    f'<span class="confidence-badge {css_cls}">{icon} {badge_text}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(result["answer"])
else:
    st.write("")
    st.divider()
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            '<div style="text-align:center; color:#9ca3af; padding: 1.5rem 0;">'
            "🕊️ 还没有搜索记录，输入问题并点击「开始搜索」试试看"
            "</div>",
            unsafe_allow_html=True,
        )
