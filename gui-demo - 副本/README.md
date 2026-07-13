# 🔎 联网搜索 Agent · Demo

一个使用 Streamlit 构建的联网搜索 Agent GUI，UI 参考 ChatGPT / Perplexity / Notion 风格。

完整链路（无 mock）：

```
GUI (app.py) -> agent.run_agent(query)
             -> agent.need_search(query)        # 关键词启发式，标注是否命中实时性问题
             -> agent.load_system_prompt()       # 读取 prompt.txt
             -> tools.web_search(query, prompt)  # 真实调用百度千帆 AI 搜索 API
             -> GUI 展示真实回答
```

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
- `agent.py` — 统一入口：`need_search` 判断 + 加载 `prompt.txt` + 调用 `tools.web_search`
- `tools.py` — 真实调用百度千帆 AI 搜索接口（搜索 + LLM 融合调用），API Key 从环境变量读取
- `prompt.txt` — 系统 Prompt，作为 system message 随每次请求一并发送给 LLM

## 部署到 Streamlit Community Cloud

见仓库根目录部署说明，或参考 [Streamlit Community Cloud 文档](https://docs.streamlit.io/deploy/streamlit-community-cloud)。

部署后即可获得形如 `https://<app-name>.streamlit.app` 的公网链接，直接分享给同事访问（记得先在 Secrets 中配置好 `BAIDU_QIANFAN_API_KEY`，否则线上会显示调用失败）。
