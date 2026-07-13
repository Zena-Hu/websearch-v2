# agent.py
# 统一入口：query -> need_search -> 加载 prompt.txt -> tools.web_search（检索）-> tools.chat_completion（生成）-> 结构化结果
#
# 与之前的差异：百度千帆的"搜索 + LLM 融合接口"被拆成两个独立调用：
#   1) tools.web_search()      纯检索，返回 references
#   2) tools.chat_completion() 纯生成，把 references 拼成 web_context 注入 system_prompt 之后的 user message
# 两步分别可能失败，因此分别捕获异常，便于在 GUI 上定位是检索失败还是生成失败。

from pathlib import Path

import tools

PROMPT_PATH = Path(__file__).parent / "prompt.txt"

SEARCH_KEYWORDS = [
    "汇率", "价格", "最新", "今天", "现在", "当前", "年",
    "是否", "新闻", "规定", "合规", "正确", "verify",
]


def need_search(query: str) -> bool:
    return any(k in query for k in SEARCH_KEYWORDS)


def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"未找到系统 Prompt 文件: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def run_agent(query: str) -> dict:
    """
    query -> need_search() -> load prompt.txt -> tools.web_search()（检索）-> tools.chat_completion()（生成）-> 结构化结果

    每个 query 都会先发起一次真实检索，再把检索结果作为 web_context 交给 LLM 生成回答；
    need_search() 的判断结果作为可解释性元数据一并返回，用于 GUI 展示"系统是否判断该问题
    具有实时性 / 需要联网核实"，而不是决定是否发起调用的开关。
    """
    should_search = need_search(query)
    system_prompt = load_system_prompt()

    base = {
        "query": query,
        "need_search": should_search,
        "system_prompt": system_prompt,
    }

    try:
        search_data = tools.web_search(query)
    except tools.WebSearchError as exc:
        return {
            **base,
            "success": False,
            "error": f"联网搜索失败：{exc}",
            "answer": None,
            "references": [],
            "raw": None,
        }

    references = search_data.get("references", [])
    web_context = tools.build_web_context(references)

    try:
        chat_data = tools.chat_completion(query, system_prompt, web_context)
        answer = tools.extract_answer(chat_data)
    except tools.WebSearchError as exc:
        return {
            **base,
            "success": False,
            "error": f"LLM 生成失败：{exc}",
            "answer": None,
            "references": references,
            "raw": {"web_search": search_data},
        }

    return {
        **base,
        "success": True,
        "error": None,
        "answer": answer,
        "references": references,
        "raw": {"web_search": search_data, "chat_completion": chat_data},
    }
