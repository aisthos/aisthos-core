"""Web Search skill — tool definitions and handlers.

Uses duckduckgo-search for full web search (text + news).
No API key required. Gated by internet_enabled parental control flag.

Strategy: news search first (best for Russian queries and current data),
then text search as supplement. This gives the best results for questions
about prices, weather, events, people, etc.
"""

import logging

logger = logging.getLogger(__name__)

# ── Tool Definition (sent to Claude API) ─────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "web_search",
        "description": (
            "Поиск актуальной информации в интернете. Используй когда нужны "
            "свежие данные: новости, погода, цены, курсы, факты. "
            "Параметр search_type: 'news' для новостей и актуальных данных (рекомендуется), "
            "'text' для общих вопросов (кто такой, что такое)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Короткий поисковый запрос (3-5 слов)",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["text", "news"],
                    "description": "Тип поиска: news (новости, цены, погода — по умолчанию) или text (общие факты)",
                    "default": "news",
                },
            },
            "required": ["query"],
        },
    },
]


def _search_news(ddgs, query: str, max_results: int = 5) -> list[dict]:
    """Run news search, return formatted results."""
    raw = list(ddgs.news(query, region="ru-ru", max_results=max_results))
    results = []
    for r in raw:
        results.append({
            "title": r.get("title", ""),
            "body": r.get("body", "")[:400],
            "source": r.get("source", ""),
            "date": r.get("date", ""),
            "url": r.get("url", ""),
        })
    return results


def _search_text(ddgs, query: str, max_results: int = 5) -> list[dict]:
    """Run text search, return formatted results."""
    raw = list(ddgs.text(query, region="ru-ru", max_results=max_results))
    results = []
    for r in raw:
        results.append({
            "title": r.get("title", ""),
            "body": r.get("body", "")[:400],
            "url": r.get("href", ""),
        })
    return results


def handle_web_search(inp: dict, internet_enabled: bool = False) -> dict:
    """Search the web using duckduckgo-search.

    Strategy:
      - news (default): news search first, text search as fallback
      - text: text search first, news as fallback

    Args:
        inp: Tool input with 'query' and optional 'search_type'.
        internet_enabled: Whether internet access is allowed.

    Returns:
        Dict with search results or error/disabled status.
    """
    if not internet_enabled:
        return {
            "status": "disabled",
            "message": "Интернет-поиск отключён. Попроси хозяина включить опцию.",
        }

    query = inp["query"]
    search_type = inp.get("search_type", "news")

    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            if search_type == "news":
                # News first (best for Russian), text as fallback
                results = _search_news(ddgs, query)
                used_type = "news"
                if not results:
                    results = _search_text(ddgs, query)
                    used_type = "text (fallback)"
            else:
                # Text first, news as fallback
                results = _search_text(ddgs, query)
                used_type = "text"
                if not results:
                    results = _search_news(ddgs, query)
                    used_type = "news (fallback)"

        if not results:
            return {
                "status": "ok",
                "query": query,
                "search_type": used_type,
                "results": [],
                "message": f"Ничего не найдено по запросу '{query}'. Попробуй переформулировать.",
            }

        return {
            "status": "ok",
            "query": query,
            "search_type": used_type,
            "results": results,
        }

    except Exception as e:
        logger.error("Web search failed for '%s': %s", query, e)
        return {
            "status": "error",
            "message": f"Ошибка поиска: {str(e)}",
        }
