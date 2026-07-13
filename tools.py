import os

import requests
from dotenv import load_dotenv

load_dotenv()

# ===== API KEY（兼容本地.env 和 Streamlit Cloud Secrets）=====
API_KEY = (
    st.secrets["BAIDU_QIANFAN_API_KEY"]
    if "BAIDU_QIANFAN_API_KEY" in st.secrets
    else os.environ.get("BAIDU_QIANFAN_API_KEY")
)

# ===== 百度千帆：搜索与 LLM 两个独立接口 =====
SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"
CHAT_URL = "https://qianfan.baidubce.com/v2/chat/completions"
CHAT_MODEL = "ernie-4.5-turbo-128k"

# web_search 接口要求 query 长度不超过 72 个字符
SEARCH_QUERY_MAX_LEN = 72


class WebSearchError(Exception):
    """百度千帆搜索/LLM 调用失败或返回结构不符合预期时抛出。"""


def _headers() -> dict:
    if not API_KEY:
        raise WebSearchError(
            "未配置 BAIDU_QIANFAN_API_KEY 环境变量，无法调用真实搜索/LLM接口。"
            "本地请在 .env 中设置，Streamlit Cloud 请在 App Settings → Secrets 中配置。"
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


# ===== 1. 百度千帆 AI 搜索接口（纯检索，不含 LLM 生成） =====
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
        raise WebSearchError(f"调用百度千帆搜索 API 失败（HTTP {res.status_code}）: {res.text}") from exc
    except requests.RequestException as exc:
        raise WebSearchError(f"调用百度千帆搜索 API 失败: {exc}") from exc

    data = res.json()
    if not isinstance(data, dict):
        raise WebSearchError(f"搜索接口返回了非预期的数据类型: {type(data)}")
    if "references" not in data and "code" in data:
        raise WebSearchError(
            f"搜索接口返回错误: code={data.get('code')} message={data.get('message')}"
        )

    return data


def build_web_context(references: list[dict]) -> str:
    """把 references 拼接为 LLM 可读的 web_context 文本。"""
    if not references:
        return ""

    blocks = []
    for i, ref in enumerate(references, start=1):
        title = ref.get("title", "")
        url = ref.get("url", "")
        date = ref.get("date", "")
        content = ref.get("content") or ref.get("snippet") or ""
        blocks.append(f"[{i}] 标题：{title}\n链接：{url}\n日期：{date}\n内容：{content}")
    return "\n\n".join(blocks)


# ===== 2. 百度千帆 LLM 对话接口（纯生成，不含检索） =====
def chat_completion(query: str, system_prompt: str, web_context: str) -> dict:
    """
    调用百度千帆 LLM 对话接口，基于 system_prompt + web_context 生成回答，返回原始响应。
    """
    headers = _headers()

    user_content = query if not web_context else f"{query}\n\n[web_context]\n{web_context}"

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2000,
        "stream": False,
        "response_format": {"type": "text"},
    }

    try:
        # web_context 可能包含上万字符的检索内容，实测生成耗时可达 60s+，超时留足余量
        res = requests.post(CHAT_URL, headers=headers, json=payload, timeout=120)
        res.raise_for_status()
    except requests.HTTPError as exc:
        raise WebSearchError(f"调用百度千帆 LLM API 失败（HTTP {res.status_code}）: {res.text}") from exc
    except requests.RequestException as exc:
        raise WebSearchError(f"调用百度千帆 LLM API 失败: {exc}") from exc

    data = res.json()
    if not isinstance(data, dict):
        raise WebSearchError(f"LLM 接口返回了非预期的数据类型: {type(data)}")
    if "choices" not in data and "code" in data:
        raise WebSearchError(
            f"LLM 接口返回错误: code={data.get('code')} message={data.get('message')}"
        )

    return data


def extract_answer(chat_data: dict) -> str:
    try:
        return chat_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise WebSearchError(f"LLM 接口返回结构不符合预期，无法提取 content 字段: {exc}") from exc
