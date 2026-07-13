import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _load_api_key() -> str | None:
    # 本地没有 .streamlit/secrets.toml 时，st.secrets 在访问时会直接抛
    # StreamlitSecretNotFoundError（不是返回空字典），所以必须 try/except
    # 而不能用 "in st.secrets" 判断，否则纯 .env 的本地开发环境会在 import 时崩溃。
    try:
        return st.secrets["BAIDU_QIANFAN_API_KEY"]
    except Exception:
        return os.environ.get("BAIDU_QIANFAN_API_KEY")


# ===== API KEY（兼容本地 .env 和 Streamlit Cloud Secrets）=====
API_KEY = _load_api_key()

# ===== 百度千帆 AI 搜索接口（纯检索，不含 LLM 生成） =====
SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"

# web_search 接口要求 query 长度不超过 72 个字符
SEARCH_QUERY_MAX_LEN = 72


class SearchError(Exception):
    """百度千帆搜索接口调用失败或返回结构不符合预期时抛出。"""


def _headers() -> dict:
    if not API_KEY:
        raise SearchError(
            "未配置 BAIDU_QIANFAN_API_KEY 环境变量，无法调用真实搜索接口。"
            "本地请在 .env 中设置，Streamlit Cloud 请在 App Settings → Secrets 中配置。"
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def web_search(query: str) -> dict:
    """
    调用百度千帆 AI 搜索接口，仅做全网检索，返回原始响应（含 references 列表）。
    """
    headers = _headers()
    payload = {
        "messages": [{"role": "user", "content": query[:SEARCH_QUERY_MAX_LEN]}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 10}],
    }

    try:
        res = requests.post(SEARCH_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
    except requests.HTTPError as exc:
        raise SearchError(f"调用百度千帆搜索 API 失败（HTTP {res.status_code}）: {res.text}") from exc
    except requests.RequestException as exc:
        raise SearchError(f"调用百度千帆搜索 API 失败: {exc}") from exc

    data = res.json()
    if not isinstance(data, dict):
        raise SearchError(f"搜索接口返回了非预期的数据类型: {type(data)}")
    if "references" not in data and "code" in data:
        raise SearchError(
            f"搜索接口返回错误: code={data.get('code')} message={data.get('message')}"
        )

    return data
