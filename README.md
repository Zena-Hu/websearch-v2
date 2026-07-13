# 🔎 联网搜索 Agent · Demo

一个使用 Streamlit 构建的联网搜索 Agent GUI，UI 参考 ChatGPT / Perplexity / Notion 风格。

完整链路（无 mock，Evidence-based Answer 四段式）：

```
GUI (app.py) -> agent.run_agent(query)
             -> agent.need_search(query)          # 关键词启发式，标注是否命中实时性问题
             -> agent.load_system_prompt()         # 读取 prompt.txt
             -> search.web_search(query)           # 真实调用百度千帆 AI 搜索 API（纯检索）
             -> evidence.build_evidence(...)       # 结构化证据构建（本地处理，不发起网络请求）
             -> llm.generate_answer(query, evidence, prompt)  # 真实调用百度千帆 LLM API，仅依据 Evidence 生成
             -> GUI 展示真实回答
```

`search`（检索）与 `llm`（生成）是两个独立的百度千帆接口调用；`evidence` 是介于两者之间的中间层，
把检索结果转成带 `evidence_id` 的结构化证据再交给 LLM，目的是约束 LLM 只能引用已提取的证据作答，
而不是绕开检索结果、用自身知识补充，从而降低幻觉与无来源事实。

## 配置 API Key

真实调用需要百度千帆 `BAIDU_QIANFAN_API_KEY`。

**本地开发**：复制 `.env.example` 为 `.env`，填入你的 key（`.env` 已在 `.gitignore` 中，不会被提交）：

```bash
cp .env.example .env
# 编辑 .env，填入真实 key
```

**Streamlit Community Cloud**：在 App 的 `Settings → Secrets` 中添加：

```toml
BAIDU_QIANFAN_API_KEY = "your_api_key_here"
```

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 项目结构

- `app.py` — Streamlit GUI，调用 `agent.run_agent()`，展示真实 pipeline 执行详情与最终回答
- `agent.py` — 统一入口：`need_search` 判断 + 加载 `prompt.txt` + 编排 `search -> evidence -> llm` 三步
- `search.py` — 真实调用百度千帆 AI 搜索接口（`v2/ai_search/web_search`，纯检索），API Key 从环境变量 / Secrets 读取
- `evidence.py` — Evidence Extraction / Builder：把搜索结果转成带 `evidence_id` 的结构化证据，纯本地处理
- `llm.py` — 真实调用百度千帆 LLM 接口（`v2/chat/completions`，纯生成），API Key 从环境变量 / Secrets 读取
- `prompt.txt` — 系统 Prompt，作为 system message 随每次请求一并发送给 LLM

## 部署到 Streamlit Community Cloud

见仓库根目录部署说明，或参考 [Streamlit Community Cloud 文档](https://docs.streamlit.io/deploy/streamlit-community-cloud)。

部署后即可获得形如 `https://<app-name>.streamlit.app` 的公网链接，直接分享给同事访问（记得先在 Secrets 中配置好 `BAIDU_QIANFAN_API_KEY`，否则线上会显示调用失败）。
