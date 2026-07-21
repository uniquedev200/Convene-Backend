import pytest

from app.tools_mcp import (
    ToolAccessError,
    call_enabled_tool,
    create_mcp_server,
    run_tool_search,
    get_enabled_tool_definitions,
    get_enabled_tool_names,
    _parse_duckduckgo_html_results,
)


def test_github_repo_stats_only_enabled_for_developer():
    assert "github_repo_stats" in get_enabled_tool_names("developer")
    assert "github_repo_stats" not in get_enabled_tool_names("education")
    assert "github_repo_stats" not in get_enabled_tool_names("startup")


def test_tool_definitions_are_filtered_by_preset():
    startup_tools = {tool["name"] for tool in get_enabled_tool_definitions("startup")}

    assert startup_tools == {"web_search"}


def test_call_enabled_tool_rejects_disabled_tool_before_network_call():
    with pytest.raises(ToolAccessError):
        call_enabled_tool("startup", "github_repo_stats", repo="facebook/react")


def test_duckduckgo_search_filters_and_formats_llm_ready_results(monkeypatch):
    class FakeDDGS:
        def __init__(self, timeout):
            self.timeout = timeout

        def text(self, query, region, safesearch, timelimit, max_results, backend):
            assert backend == "duckduckgo"
            return [
                {
                    "title": "PostgreSQL Documentation: Reliability",
                    "body": "PostgreSQL documents ACID transactions, indexing, replication, and reliability guarantees for production systems.",
                    "href": "https://www.postgresql.org/docs/current/",
                },
                {
                    "title": "Random short result",
                    "body": "tiny",
                    "href": "https://example.com/postgres",
                },
                {
                    "title": "Noisy discussion",
                    "body": "A long but low-signal discussion that should be blocked.",
                    "href": "https://reddit.com/r/database/comments/1",
                },
            ]

    class FakeModule:
        DDGS = FakeDDGS

    monkeypatch.setitem(__import__("sys").modules, "ddgs", FakeModule)

    result = run_tool_search("Postgres reliability production")

    assert result.raw_data["provider"] == "duckduckgo_search"
    assert result.raw_data["filtered_count"] == 2
    assert "PostgreSQL Documentation" in result.result_summary
    assert "Source: https://www.postgresql.org/docs/current/" in result.result_summary
    assert "reddit.com" not in result.result_summary


def test_duckduckgo_html_parser_extracts_result_cards():
    html = """
    <div class="result">
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Fwww.postgresql.org%2Fdocs%2Fcurrent%2F">
        PostgreSQL Documentation
      </a>
      <a class="result__snippet">ACID transactions, indexing, and replication docs.</a>
    </div>
    """

    results = _parse_duckduckgo_html_results(html)

    assert results == [
        {
            "title": "PostgreSQL Documentation",
            "body": "ACID transactions, indexing, and replication docs.",
            "href": "https://www.postgresql.org/docs/current/",
        }
    ]


def test_create_mcp_server_uses_real_fastmcp():
    server = create_mcp_server()

    assert server.name == "debatestack-tools"
