"""Tests of the Tropical Forages selection tools (offline, the MCP call is faked)."""

from domain.services import forage_selection
from domain.tools import forage_tools


def _func(tool):
    return getattr(tool, "func", tool)


def test_tools_are_offered_only_when_the_service_is_configured(monkeypatch):
    monkeypatch.delenv(forage_selection.URL_ENV, raising=False)
    assert forage_tools.forage_tools() == []

    monkeypatch.setenv(forage_selection.URL_ENV, "https://tf-selection.example/")
    assert [t.name for t in forage_tools.forage_tools()] == [
        "find_forage", "list_forage_features", "search_tropical_forages", "read_forage_factsheet",
    ]
    assert forage_selection.base_url() == "https://tf-selection.example"


def test_search_passes_filters_and_drops_empty_ones(monkeypatch):
    calls = []
    monkeypatch.setattr(forage_selection, "call_tool", lambda name, args: calls.append((name, args)) or '{"remaining": 3}')

    result = _func(forage_tools.search_tropical_forages)(numeric_filters={"Rainfall": "1200-1800"})

    assert result.content == '{"remaining": 3}'
    assert calls == [("search_tropical_forages", {"categorical_filters": None, "numeric_filters": {"Rainfall": "1200-1800"}, "limit": 15})]


def test_unavailable_service_gives_the_fixed_text(monkeypatch):
    def fail(name, args):
        raise forage_selection.ForageServiceUnavailable("down")

    monkeypatch.setattr(forage_selection, "call_tool", fail)

    assert "not available" in _func(forage_tools.find_forage)("Toledo").content


def test_call_tool_needs_a_url(monkeypatch):
    monkeypatch.delenv(forage_selection.URL_ENV, raising=False)
    try:
        forage_selection.call_tool("find_forage", {"name": "x"})
    except forage_selection.ForageServiceUnavailable:
        return
    raise AssertionError("expected ForageServiceUnavailable")
