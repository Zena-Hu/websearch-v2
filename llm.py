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

# ===== 百度千帆 LLM 对话接口（纯生成，不含检索） =====
CHAT_URL = "https://qianfan.baidubce.com/v2/chat/completions"
CHAT_MODEL = "ernie-4.5-turbo-128k"


class LLMError(Exception):
    """百度千帆 LLM 接口调用失败或返回结构不符合预期时抛出。"""


def _headers() -> dict:
    if not API_KEY:
        raise LLMError(
            "未配置 BAIDU_QIANFAN_API_KEY 环境变量，无法调用真实 LLM 接口。"
            "本地请在 .env 中设置，Streamlit Cloud 请在 App Settings → Secrets 中配置。"
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def chat_completion(query: str, system_prompt: str, evidence_context: str) -> dict:
    """
    调用百度千帆 LLM 对话接口，基于 system_prompt + evidence_context 生成回答，返回原始响应。
    evidence_context 由 evidence.build_evidence_context() 生成，作为 user message 中的
    web_context 注入，供 prompt.txt 中约束的"仅依据 web_context 回答"规则使用。
    """
    headers = _headers()

    user_content = query if not evidence_context else f"{query}\n\n[web_context]\n{evidence_context}"

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
        # evidence_context 可能包含上万字符的检索内容，实测生成耗时可达 60s+，超时留足余量
        res = requests.post(CHAT_URL, headers=headers, json=payload, timeout=120)
        res.raise_for_status()
    except requests.HTTPError as exc:
        raise LLMError(f"调用百度千帆 LLM API 失败（HTTP {res.status_code}）: {res.text}") from exc
    except requests.RequestException as exc:
        raise LLMError(f"调用百度千帆 LLM API 失败: {exc}") from exc

    data = res.json()
    if not isinstance(data, dict):
        raise LLMError(f"LLM 接口返回了非预期的数据类型: {type(data)}")
    if "choices" not in data and "code" in data:
        raise LLMError(
            f"LLM 接口返回错误: code={data.get('code')} message={data.get('message')}"
        )

    return data


def extract_answer(chat_data: dict) -> str:
    try:
        return chat_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"LLM 接口返回结构不符合预期，无法提取 content 字段: {exc}") from exc
