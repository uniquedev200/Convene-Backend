"""Generic MCP/tool implementation for DebateStack.

Person C owns this module. The tools are generic unless the contract says
otherwise, and preset-specific access is enforced from DOMAIN_REGISTRY.
"""

from __future__ import annotations

import datetime as dt
import html as html_lib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .contracts import (
    DOMAIN_REGISTRY,
    MCP_TOOL_DEFINITIONS,
    PresetId,
    ToolResult,
)


class ToolAccessError(ValueError):
    """Raised when a preset tries to use a tool it has not enabled."""


class ToolExecutionError(RuntimeError):
    """Raised when an enabled tool cannot complete its lookup."""


ToolRunner = Callable[..., ToolResult]

DEFAULT_TIMEOUT_SECONDS = float(os.getenv("TOOL_HTTP_TIMEOUT_SECONDS", "12"))
SUMMARY_LIMIT = int(os.getenv("TOOL_SUMMARY_LIMIT", "900"))
SEARCH_MAX_RESULTS = int(os.getenv("DUCKDUCKGO_MAX_RESULTS", "20"))
SEARCH_TOP_RESULTS = int(os.getenv("DUCKDUCKGO_TOP_RESULTS", "6"))

BLOCKED_SEARCH_DOMAINS = {
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "quora.com",
    "reddit.com",
    "youtube.com",
}

TRUSTED_SEARCH_DOMAIN_BONUS = {
    "docs.python.org": 4,
    "developer.mozilla.org": 4,
    "github.com": 3,
    "docs.github.com": 4,
    "cloud.google.com": 3,
    "docs.aws.amazon.com": 3,
    "learn.microsoft.com": 3,
    "postgresql.org": 3,
    "mongodb.com": 3,
    "sqlite.org": 3,
    "wikipedia.org": 1,
}


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, bytes, dict[str, str]]:
    body = None
    request_headers = {"User-Agent": "DebateStack/2.0"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ToolExecutionError(f"{url} returned HTTP {exc.code}: {detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise ToolExecutionError(f"{url} request failed: {exc.reason}") from exc


def _compact_text(text: str, limit: int = SUMMARY_LIMIT) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return urllib.parse.unquote(_compact_text(html))


def _clean_duckduckgo_href(href: str) -> str:
    href = html_lib.unescape(href)
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query:
        return query["uddg"][0]
    if parsed.scheme in {"http", "https"}:
        return href
    return ""


def _domain_for(url: str) -> str:
    hostname = urllib.parse.urlparse(url).hostname or ""
    return hostname.removeprefix("www.").lower()


def _query_terms(query: str) -> set[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "for",
        "in",
        "is",
        "of",
        "or",
        "the",
        "to",
        "vs",
        "what",
        "which",
        "with",
    }
    return {
        term
        for term in re.findall(r"[a-z0-9][a-z0-9.+#-]*", query.lower())
        if len(term) > 1 and term not in stop_words and not re.fullmatch(r"20\d{2}", term)
    }


def _search_score(result: dict[str, str], terms: set[str]) -> float:
    title = result.get("title", "")
    body = result.get("body", "")
    href = result.get("href", "")
    domain = _domain_for(href)
    searchable = f"{title} {body} {domain}".lower()
    score = sum(2 for term in terms if term in title.lower())
    score += sum(1 for term in terms if term in searchable)
    score += min(len(body), 260) / 260
    for trusted_domain, bonus in TRUSTED_SEARCH_DOMAIN_BONUS.items():
        if domain.endswith(trusted_domain):
            score += bonus
            break
    if any(domain.endswith(blocked) for blocked in BLOCKED_SEARCH_DOMAINS):
        score -= 10
    if len(body.strip()) < 45:
        score -= 2
    return score


def _filter_search_results(query: str, raw_results: list[dict[str, str]]) -> list[dict[str, str]]:
    terms = _query_terms(query)
    seen: set[tuple[str, str]] = set()
    filtered: list[dict[str, str]] = []

    for result in raw_results:
        title = _compact_text(str(result.get("title") or ""), 160)
        body = _compact_text(str(result.get("body") or ""), 320)
        href = str(result.get("href") or result.get("url") or "")
        domain = _domain_for(href)
        if not title or not body or not href or not domain:
            continue
        if any(domain.endswith(blocked) for blocked in BLOCKED_SEARCH_DOMAINS):
            continue
        dedupe_key = (domain, re.sub(r"\W+", "", title.lower())[:80])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(
            {
                "title": title,
                "body": body,
                "href": href,
                "domain": domain,
                "score": _search_score({"title": title, "body": body, "href": href}, terms),
            }
        )

    filtered.sort(key=lambda item: item["score"], reverse=True)
    return filtered[:SEARCH_TOP_RESULTS]


def _format_search_summary(query: str, results: list[dict[str, str]]) -> str:
    if not results:
        return f"No high-quality DuckDuckGo results survived filtering for: {query}"

    lines = [f"DuckDuckGo filtered web evidence for '{query}':"]
    for index, result in enumerate(results, start=1):
        lines.append(
            f"{index}. {result['title']} ({result['domain']}) - "
            f"{result['body']} Source: {result['href']}"
        )
    return _compact_text(" ".join(lines), max(SUMMARY_LIMIT, 1400))


def _search_query_attempts(query: str) -> list[str]:
    attempts = [query]
    low_signal_terms = {
        "best",
        "better",
        "choose",
        "comparison",
        "current",
        "decision",
        "production",
        "should",
        "versus",
        "vs",
    }
    terms = [
        term
        for term in re.findall(r"[a-zA-Z0-9.+#-]+", query)
        if not re.fullmatch(r"20\d{2}", term) and term.lower() not in {"vs", "versus"}
    ]
    simplified = " ".join(terms[:10]).strip()
    if simplified and simplified.lower() != query.lower():
        attempts.append(simplified)
    core_terms = " ".join(
        term
        for term in terms[:10]
        if term.lower() not in low_signal_terms
    ).strip()
    if core_terms and core_terms.lower() not in {attempt.lower() for attempt in attempts}:
        attempts.append(core_terms)
    return attempts


def _parse_duckduckgo_html_results(html: str) -> list[dict[str, str]]:
    try:
        from lxml import html as lxml_html
    except ImportError as exc:
        raise ToolExecutionError("DuckDuckGo HTML fallback requires lxml") from exc

    doc = lxml_html.fromstring(html)
    results: list[dict[str, str]] = []
    nodes = doc.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' result ')]")
    for node in nodes:
        title_nodes = node.xpath(".//a[contains(@class, 'result__a')]")
        if not title_nodes:
            continue
        title = _compact_text(" ".join(title_nodes[0].xpath(".//text()")), 160)
        href = _clean_duckduckgo_href(title_nodes[0].get("href", ""))
        body = _compact_text(
            " ".join(node.xpath(".//*[contains(@class, 'result__snippet')]//text()")),
            320,
        )
        if title and href and body:
            results.append({"title": title, "body": body, "href": href})
    return results


def _duckduckgo_html_search(query: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query})
    _, body, _ = _request(
        f"https://html.duckduckgo.com/html/?{params}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            )
        },
    )
    return _parse_duckduckgo_html_results(body.decode("utf-8", errors="replace"))


def run_tool_search(query: str) -> ToolResult:
    """Search current web information using DuckDuckGo with LLM-ready filtering."""
    t0 = time.monotonic()
    query = query.strip()
    if not query:
        raise ToolExecutionError("web_search requires a non-empty query")

    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise ToolExecutionError("Install ddgs to use web_search") from exc

    errors: list[str] = []
    raw_results: list[dict[str, str]] = []
    successful_query = query
    provider = "ddgs"
    attempted_queries = _search_query_attempts(query)
    for attempted_query in attempted_queries:
        try:
            raw_results = list(
                DDGS(timeout=int(DEFAULT_TIMEOUT_SECONDS)).text(
                    attempted_query,
                    region=os.getenv("DUCKDUCKGO_REGION", "wt-wt"),
                    safesearch=os.getenv("DUCKDUCKGO_SAFESEARCH", "moderate"),
                    timelimit=os.getenv("DUCKDUCKGO_TIMELIMIT") or None,
                    max_results=SEARCH_MAX_RESULTS,
                    backend=os.getenv("DUCKDUCKGO_BACKEND", "duckduckgo"),
                )
            )
            successful_query = attempted_query
            if raw_results:
                break
        except Exception as exc:
            errors.append(f"{attempted_query}: {exc}")
        try:
            raw_results = _duckduckgo_html_search(attempted_query)
            successful_query = attempted_query
            provider = "duckduckgo_html"
            if raw_results:
                break
        except Exception as exc:
            errors.append(f"{attempted_query} html: {exc}")
    if not raw_results:
        raise ToolExecutionError(f"DuckDuckGo search failed for '{query}': {'; '.join(errors)}")

    filtered = _filter_search_results(query, raw_results)
    elapsed_ms = (time.monotonic() - t0) * 1000
    return ToolResult(
        tool_name="web_search",
        query=query,
        result_summary=_format_search_summary(query, filtered),
        raw_data={
            "provider": "duckduckgo_search",
            "backend": provider,
            "searched_query": successful_query,
            "attempted_queries": attempted_queries,
            "raw_count": len(raw_results),
            "filtered_count": len(filtered),
            "results": filtered,
        },
        duration_ms=round(elapsed_ms, 1),
    )


def run_url_fetch(url: str) -> ToolResult:
    """Fetch and summarize a specific URL."""
    t0 = time.monotonic()
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ToolExecutionError("url_fetch requires an http(s) URL")

    status, body, headers = _request(url)
    content_type = headers.get("Content-Type", "")
    text = body.decode("utf-8", errors="replace")
    summary = _strip_html(text) if "html" in content_type.lower() else _compact_text(text)
    elapsed_ms = (time.monotonic() - t0) * 1000
    return ToolResult(
        tool_name="url_fetch",
        query=url,
        result_summary=summary or f"Fetched {url} but found no readable text",
        raw_data={"status": status, "content_type": content_type, "bytes": len(body)},
        duration_ms=round(elapsed_ms, 1),
    )


def _read_pdf_bytes(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ToolExecutionError("document_reader needs pypdf installed to read PDFs") from exc

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def run_document_reader(document_url: str) -> ToolResult:
    """Read a linked or local document and return a concise summary."""
    t0 = time.monotonic()
    target = document_url.strip()
    if not target:
        raise ToolExecutionError("document_reader requires a URL or file path")

    raw_data: dict[str, Any] = {}
    parsed = urllib.parse.urlparse(target)
    suffix = Path(parsed.path or target).suffix.lower()
    if parsed.scheme in {"http", "https"}:
        status, body, headers = _request(target)
        raw_data.update({"source": "url", "status": status, "content_type": headers.get("Content-Type", "")})
    else:
        path = Path(target).expanduser()
        if not path.exists() or not path.is_file():
            raise ToolExecutionError(f"document not found: {target}")
        body = path.read_bytes()
        suffix = path.suffix.lower()
        raw_data.update({"source": "file", "path": str(path), "bytes": len(body)})

    if suffix == ".pdf":
        text = _read_pdf_bytes(body)
    else:
        text = body.decode("utf-8", errors="replace")

    elapsed_ms = (time.monotonic() - t0) * 1000
    return ToolResult(
        tool_name="document_reader",
        query=document_url,
        result_summary=_compact_text(text or f"No readable text found in: {document_url}"),
        raw_data=raw_data,
        duration_ms=round(elapsed_ms, 1),
    )


def run_github_repo_stats(repo: str) -> ToolResult:
    """Fetch GitHub repository health signals."""
    t0 = time.monotonic()
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ToolExecutionError("github_repo_stats requires owner/repo format")

    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    status, body, _ = _request(f"https://api.github.com/repos/{repo}", headers=headers)
    repo_data = json.loads(body.decode("utf-8"))
    commit_status, commit_body, _ = _request(
        f"https://api.github.com/repos/{repo}/commits?per_page=1",
        headers=headers,
    )
    commits = json.loads(commit_body.decode("utf-8"))
    last_commit_at = None
    last_commit_days_ago = None
    if commits:
        last_commit_at = commits[0].get("commit", {}).get("committer", {}).get("date")
        if last_commit_at:
            committed = dt.datetime.fromisoformat(last_commit_at.replace("Z", "+00:00"))
            last_commit_days_ago = (dt.datetime.now(dt.UTC) - committed).days

    stars = repo_data.get("stargazers_count", 0)
    open_issues = repo_data.get("open_issues_count", 0)
    pushed_at = repo_data.get("pushed_at")
    elapsed_ms = (time.monotonic() - t0) * 1000
    return ToolResult(
        tool_name="github_repo_stats",
        query=repo,
        result_summary=(
            f"{repo}: {stars:,} stars, {open_issues:,} open issues/PRs, "
            f"last commit {last_commit_days_ago if last_commit_days_ago is not None else 'unknown'} days ago"
        ),
        raw_data={
            "status": status,
            "commit_status": commit_status,
            "stars": stars,
            "open_issues_count": open_issues,
            "last_commit_at": last_commit_at,
            "last_commit_days_ago": last_commit_days_ago,
            "pushed_at": pushed_at,
        },
        duration_ms=round(elapsed_ms, 1),
    )


TOOL_RUNNERS: dict[str, ToolRunner] = {
    "web_search": run_tool_search,
    "url_fetch": run_url_fetch,
    "document_reader": run_document_reader,
    "github_repo_stats": run_github_repo_stats,
}


def get_enabled_tool_names(preset_id: PresetId) -> list[str]:
    return list(DOMAIN_REGISTRY[preset_id].enabled_tools)


def get_enabled_tool_definitions(preset_id: PresetId) -> list[dict[str, Any]]:
    enabled = set(get_enabled_tool_names(preset_id))
    return [definition for definition in MCP_TOOL_DEFINITIONS if definition["name"] in enabled]


def get_enabled_tool_runners(preset_id: PresetId) -> dict[str, ToolRunner]:
    enabled = set(get_enabled_tool_names(preset_id))
    return {name: runner for name, runner in TOOL_RUNNERS.items() if name in enabled}


def call_enabled_tool(preset_id: PresetId, tool_name: str, **kwargs: Any) -> ToolResult:
    runners = get_enabled_tool_runners(preset_id)
    if tool_name not in runners:
        raise ToolAccessError(f"{tool_name} is not enabled for preset {preset_id}")
    return runners[tool_name](**kwargs)


def create_mcp_server() -> Any:
    """Create an optional FastMCP server exposing the frozen tool schemas.

    The dependency is optional so the API/test layer can run before MCP is
    installed. Agent binding should still use get_enabled_tool_definitions()
    so presets only receive tools they are allowed to call.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the 'mcp' package to run the MCP server") from exc

    server = FastMCP("debatestack-tools")

    @server.tool(name="web_search", description=MCP_TOOL_DEFINITIONS[0]["description"])
    def mcp_web_search(query: str) -> dict[str, Any]:
        return run_tool_search(query).model_dump()

    @server.tool(name="url_fetch", description=MCP_TOOL_DEFINITIONS[1]["description"])
    def mcp_url_fetch(url: str) -> dict[str, Any]:
        return run_url_fetch(url).model_dump()

    @server.tool(name="document_reader", description=MCP_TOOL_DEFINITIONS[2]["description"])
    def mcp_document_reader(document_url: str) -> dict[str, Any]:
        return run_document_reader(document_url).model_dump()

    @server.tool(name="github_repo_stats", description=MCP_TOOL_DEFINITIONS[3]["description"])
    def mcp_github_repo_stats(repo: str) -> dict[str, Any]:
        return run_github_repo_stats(repo).model_dump()

    return server


if __name__ == "__main__":
    create_mcp_server().run()
