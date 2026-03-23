"""
Token budget and trimming. Budget = CHAT_CONTEXT_WINDOW - output reserve - fixed prompt overhead.
fit_publications degrades in two stages: strips abstracts from least important first, then drops publications from the tail.
"""
from app.config import CHAT_MAX_TOKENS, CHAT_CONTEXT_WINDOW
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.routers.ai import format_entity_context
from app.utils.schemas.ai import EntityRef

INPUT_BUDGET = CHAT_CONTEXT_WINDOW - CHAT_MAX_TOKENS


def tokens(text: str) -> int:
    return len(text) // 4  # ~4 chars per token for English text


def data_budget(entity: EntityRef, prompt: str) -> int:
    fixed = tokens(SYSTEM_PROMPT) + tokens(format_entity_context(entity)) + tokens(prompt)
    return INPUT_BUDGET - fixed


# pubs_data is (core_text, abstract_text), most important first.
# Stage 1: strip abstracts from least important end. Stage 2: drop from least important end.
def fit_publications(pubs_data: list[tuple[str, str]], budget: int) -> list[str]:
    def joined(core: str, abstract: str) -> str:
        return core + ("\n" + abstract if abstract else "")

    def total(data: list[tuple[str, str]]) -> int:
        return sum(tokens(joined(c, a)) for c, a in data)

    if budget <= 0:
        return []
    if total(pubs_data) <= budget:
        return [joined(c, a) for c, a in pubs_data]

    data = list(pubs_data)

    for i in range(len(data) - 1, -1, -1):
        if data[i][1]:
            data[i] = (data[i][0], "")
            if total(data) <= budget:
                return [joined(c, a) for c, a in data]

    while data and total(data) > budget:
        data.pop()

    return [joined(c, a) for c, a in data]


# Ranked lists are already in priority order — trim from the bottom.
def fit_ranked_lines(lines: list[str], budget: int) -> list[str]:
    result, used = [], 0
    for line in lines:
        t = tokens(line)
        if used + t > budget:
            break
        result.append(line)
        used += t
    return result
