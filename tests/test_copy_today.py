"""Unit tests for the pure helper logic in copy_today.py.

These cover property extraction, schema lookups and title parsing — the parts
that don't touch the Notion API — so they run offline in CI.
"""

import copy_today as ct


# --- extract_value ---------------------------------------------------------

def test_extract_passthrough_types():
    assert ct.extract_value({"type": "checkbox", "checkbox": True}) is True
    assert ct.extract_value({"type": "number", "number": 42}) == 42
    assert ct.extract_value({"type": "url", "url": "https://x.com"}) == "https://x.com"


def test_extract_select_and_status():
    assert ct.extract_value(
        {"type": "select", "select": {"name": "A", "id": "1"}}) == {"name": "A"}
    assert ct.extract_value(
        {"type": "status", "status": {"name": "Done", "id": "2"}}) == {"name": "Done"}


def test_extract_multi_select():
    prop = {"type": "multi_select",
            "multi_select": [{"name": "x", "id": "1"}, {"name": "y", "id": "2"}]}
    assert ct.extract_value(prop) == [{"name": "x"}, {"name": "y"}]


def test_extract_people_and_relation():
    assert ct.extract_value(
        {"type": "people", "people": [{"id": "u1", "name": "Jo"}]}) == [{"id": "u1"}]
    assert ct.extract_value(
        {"type": "relation", "relation": [{"id": "r1"}]}) == [{"id": "r1"}]


def test_extract_files_keeps_only_external():
    prop = {"type": "files", "files": [
        {"type": "external", "name": "a", "external": {"url": "u"}},
        {"type": "file", "name": "b", "file": {"url": "signed"}},
    ]}
    assert ct.extract_value(prop) == [
        {"type": "external", "name": "a", "external": {"url": "u"}}]


def test_extract_files_all_uploaded_returns_none():
    prop = {"type": "files", "files": [
        {"type": "file", "name": "b", "file": {"url": "signed"}}]}
    assert ct.extract_value(prop) is None


def test_extract_readonly_type_returns_none():
    assert ct.extract_value(
        {"type": "formula", "formula": {"type": "number", "number": 5}}) is None


def test_extract_empty_values_return_none():
    assert ct.extract_value({"type": "rich_text", "rich_text": []}) is None
    assert ct.extract_value({"type": "multi_select", "multi_select": []}) is None
    assert ct.extract_value({"type": "url", "url": ""}) is None
    assert ct.extract_value({"type": "select", "select": None}) is None


# --- find_prop_by_type -----------------------------------------------------

def test_find_prop_by_type():
    schema = {"Name": {"type": "title"}, "When": {"type": "date"},
              "Tags": {"type": "multi_select"}}
    assert ct.find_prop_by_type(schema, "date") == "When"
    assert ct.find_prop_by_type(schema, "checkbox") is None


# --- _title_of -------------------------------------------------------------

def test_title_of_reads_title_property():
    page = {"properties": {
        "Name": {"type": "title", "title": [
            {"plain_text": "Crab "}, {"plain_text": "Walks"}]}}}
    assert ct._title_of(page) == "Crab Walks"


def test_title_of_empty_title():
    page = {"properties": {"Name": {"type": "title", "title": []}}}
    assert ct._title_of(page) == "(untitled)"


def test_title_of_no_title_prop():
    page = {"properties": {"X": {"type": "number", "number": 1}}}
    assert ct._title_of(page) == "(no title prop)"
