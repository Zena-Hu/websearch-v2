# agent.py
# 统一入口：query -> need_search -> 加载 prompt.txt
#        -> search.web_search（检索）-> evidence.extract_evidence（结构化证据抽取）
#        -> llm.chat_completion（基于证据生成）-> 结构化结果
#
# Evidence-based Answer 流程：
#   User Query -> Search -> Evidence Extraction / Evidence Builder -> LLM Answer Generation -> Final Answer
# 相比"检索结果直接拼给 LLM"，中间插入 evidence.py 把 references 转成带 evidence_id 的
# 结构化证据，目的是约束 LLM 只能引用已提取的证据作答，而不是绕开检索结果用自身知识补充，
# 从而降低幻觉与无来源事实。

from pathlib import Path

import evidence
import llm
import search

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
    query -> need_search() -> load prompt.txt
          -> search.web_search()（检索）-> evidence.extract_evidence()（证据抽取）
          -> llm.chat_completion()（基于证据生成）-> 结构化结果

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
        search_data = search.web_search(query)
    except search.SearchError as exc:
        return {
            **base,
            "success": False,
            "error": f"联网搜索失败：{exc}",
            "answer": None,
            "references": [],
            "evidence": [],
            "raw": None,
        }

    references = search_data.get("references", [])
    evidence_list = evidence.extract_evidence(search_data)
    evidence_context = evidence.build_evidence_context(evidence_list)

    try:
        chat_data = llm.chat_completion(query, system_prompt, evidence_context)
        answer = llm.extract_answer(chat_data)
    except llm.LLMError as exc:
        return {
            **base,
            "success": False,
            "error": f"LLM 生成失败：{exc}",
            "answer": None,
            "references": references,
            "evidence": evidence_list,
            "raw": {"web_search": search_data},
        }

    return {
        **base,
        "success": True,
        "error": None,
        "answer": answer,
        "references": references,
        "evidence": evidence_list,
        "raw": {"web_search": search_data, "chat_completion": chat_data},
    }
