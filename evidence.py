# evidence.py
# Evidence Extraction / Evidence Builder：介于 search 和 llm 之间的中间层。
#
# 目的：LLM 在拿到"检索结果"和"自身知识"两种信息来源时，容易绕开检索结果、
# 用自身知识补充答案，产生幻觉与无来源事实。做法是把百度搜索的原始返回，
# 转成结构化、带编号的 Evidence 列表，每条证据都可以被追溯到具体的
# source/title/url/content，配合 prompt.txt 中"仅依据 Evidence 回答，且需
# 标注 evidence_id"的规则，约束 LLM 只能引用已提取的证据，不得用自身知识补充。

from dataclasses import asdict, dataclass


@dataclass
class Evidence:
    evidence_id: str
    source: str
    title: str
    url: str
    content: str


def build_evidence(search_results: dict) -> list[dict]:
    """
    接收 search.web_search() 返回的原始搜索结果，提取并整理为结构化 Evidence 列表。
    跳过没有正文内容的检索结果（标题/摘要类噪声，无法作为事实依据）。
    """
    references = (
        search_results.get("references", []) if isinstance(search_results, dict) else (search_results or [])
    )

    evidence_list = []
    for i, ref in enumerate(references, start=1):
        content = (ref.get("content") or ref.get("snippet") or "").strip()
        if not content:
            continue
        evidence_list.append(
            Evidence(
                evidence_id=f"E{i}",
                source=ref.get("website") or ref.get("web_anchor") or "未知来源",
                title=ref.get("title", ""),
                url=ref.get("url", ""),
                content=content,
            )
        )
    return [asdict(e) for e in evidence_list]


def format_evidence_for_prompt(evidence_list: list[dict]) -> str:
    """把结构化 Evidence 拼接为 LLM 可读的文本块，每条附带 evidence_id 便于引用溯源。"""
    if not evidence_list:
        return ""

    blocks = []
    for ev in evidence_list:
        blocks.append(
            f"[{ev['evidence_id']}] 来源：{ev['source']}\n"
            f"标题：{ev['title']}\n"
            f"链接：{ev['url']}\n"
            f"内容：{ev['content']}"
        )
    return "\n\n".join(blocks)
