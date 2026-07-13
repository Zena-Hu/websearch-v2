# agent.py
# 统一入口：query -> need_search -> 加载 prompt.txt
#        -> search.web_search（检索）-> evidence.build_evidence（结构化证据构建）
#        -> llm.generate_answer（基于证据生成）-> 结构化结果
#
# Evidence-based Answer 流程：
#   query -> search() -> build_evidence() -> llm.generate_answer(query, evidence) -> answer + evidence
# 相比"检索结果直接拼给 LLM"，中间插入 evidence.build_evidence() 把 references 转成带
# evidence_id 的结构化证据，LLM 只接触这份证据（不接触原始检索结果），目的是约束 LLM
# 只能引用已提取的证据作答，而不是绕开检索结果用自身知识补充，从而降低幻觉与无来源事实。

import re
from pathlib import Path

import evidence
import llm
import search

PROMPT_PATH = Path(__file__).parent / "prompt.txt"

SEARCH_KEYWORDS = [
    "汇率", "价格", "最新", "今天", "现在", "当前", "年",
    "是否", "新闻", "规定", "合规", "正确", "verify",
]

# 信息不足降级策略：四档回答等级，必须与 prompt.txt 中「回答等级」表格的档位名称一致
CONFIDENCE_LEVELS = ["检索充分", "部分支持", "没有支持", "来源冲突"]

# 匹配 LLM 回答首行的 [CONFIDENCE: 档位] 标记
_CONFIDENCE_PATTERN = re.compile(r"^\s*\[CONFIDENCE:\s*(.+?)\]\s*\n+")


def need_search(query: str) -> bool:
    return any(k in query for k in SEARCH_KEYWORDS)


def parse_confidence(answer: str) -> tuple[str | None, str]:
    """
    从 LLM 回答首行提取 [CONFIDENCE: 档位] 标记（信息不足降级策略的判定结果），
    返回 (档位, 去掉标记后的正文)。如果模型没有按约定格式输出标记，或档位名称
    不在 CONFIDENCE_LEVELS 中，则档位记为 None，正文原样返回——解析失败不应
    导致回答内容丢失。
    """
    match = _CONFIDENCE_PATTERN.match(answer or "")
    if not match:
        return None, answer

    level = match.group(1).strip()
    if level not in CONFIDENCE_LEVELS:
        return None, answer

    return level, answer[match.end():].lstrip("\n")


def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"未找到系统 Prompt 文件: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def run_agent(query: str) -> dict:
    """
    query -> need_search() -> load prompt.txt
          -> search.web_search()（检索）-> evidence.build_evidence()（结构化证据构建）
          -> llm.generate_answer(query, evidence)（基于证据生成）-> answer + evidence

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

    # 1. search()
    try:
        search_results = search.web_search(query)
    except search.SearchError as exc:
        return {
            **base,
            "success": False,
            "error": f"联网搜索失败：{exc}",
            "answer": None,
            "answer_level": None,
            "references": [],
            "evidence": [],
            "raw": None,
        }

    references = search_results.get("references", [])

    # 2. build_evidence()
    evidence_list = evidence.build_evidence(search_results)

    # 3. llm.generate_answer(query, evidence)
    try:
        chat_data = llm.generate_answer(query, evidence_list, system_prompt)
        answer = llm.extract_answer(chat_data)
    except llm.LLMError as exc:
        return {
            **base,
            "success": False,
            "error": f"LLM 生成失败：{exc}",
            "answer": None,
            "answer_level": None,
            "references": references,
            "evidence": evidence_list,
            "raw": {"web_search": search_results},
        }

    # 信息不足降级策略：从回答首行解析出 LLM 自评的档位（检索充分/部分支持/没有支持/来源冲突）
    answer_level, answer = parse_confidence(answer)

    # 4. return answer + evidence
    return {
        **base,
        "success": True,
        "error": None,
        "answer": answer,
        "answer_level": answer_level,
        "references": references,
        "evidence": evidence_list,
        "raw": {"web_search": search_results, "llm_generate_answer": chat_data},
    }
