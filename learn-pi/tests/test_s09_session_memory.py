from __future__ import annotations

import json

from s09_session_memory.code import SessionManager


def test_append_only_jsonl_has_header_and_parent_chain(tmp_path) -> None:
    path = tmp_path / "session.jsonl"
    session = SessionManager.create("project", path)
    first = session.append_message("user", "first")
    second = session.append_message("assistant", "second")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["type"] == "session"
    assert json.loads(lines[0])["version"] == 3
    assert json.loads(lines[1])["parentId"] is None
    assert json.loads(lines[2])["parentId"] == first
    assert session.leaf_id == second


def test_reload_rebuilds_leaf_branch_and_model_context(tmp_path) -> None:
    path = tmp_path / "session.jsonl"
    original = SessionManager.create("project", path)
    original.append_message("user", "question")
    original.append_message("assistant", "answer")
    original.append_custom_entry("ui-state", {"selected": True})

    loaded = SessionManager.open(path)

    assert loaded.leaf_id == original.leaf_id
    assert [message["content"] for message in loaded.build_context().messages] == ["question", "answer"]
    assert len(loaded.get_entries()) == 3


def test_branch_moves_leaf_without_deleting_abandoned_history() -> None:
    session = SessionManager.in_memory()
    first = session.append_message("user", "root")
    branch_point = session.append_message("assistant", "root answer")
    abandoned = session.append_message("user", "old direction")

    session.branch(branch_point)
    sibling = session.append_message("user", "new direction")

    assert session.get_entry(abandoned) is not None
    assert session.leaf_id == sibling
    assert session.get_entry(sibling).parent_id == branch_point
    assert [message["content"] for message in session.build_context().messages] == [
        "root",
        "root answer",
        "new direction",
    ]
    assert first == session.get_branch()[0].entry_id


def test_tree_contains_both_children_in_append_order() -> None:
    session = SessionManager.in_memory()
    root = session.append_message("user", "root")
    first = session.append_message("assistant", "a1")
    session.append_message("user", "branch one")
    session.branch(first)
    session.append_message("user", "branch two")

    tree = session.get_tree()

    assert len(tree) == 1
    assert tree[0].entry.entry_id == root
    assert [child.entry.data["message"]["content"] for child in tree[0].children[0].children] == [
        "branch one",
        "branch two",
    ]


def test_fork_copies_history_with_new_header_and_parent_session(tmp_path) -> None:
    source_path = tmp_path / "source.jsonl"
    target_path = tmp_path / "fork.jsonl"
    source = SessionManager.create("source", source_path)
    source.append_message("user", "keep this")
    source.append_message("assistant", "source answer")

    fork = source.fork_to(target_path, "target")
    fork.append_message("user", "fork-only")
    reloaded_source = SessionManager.open(source_path)
    reloaded_fork = SessionManager.open(target_path)

    assert fork.header.session_id != source.header.session_id
    assert fork.header.parent_session == str(source_path)
    assert [message["content"] for message in reloaded_source.build_context().messages] == [
        "keep this",
        "source answer",
    ]
    assert [message["content"] for message in reloaded_fork.build_context().messages] == [
        "keep this",
        "source answer",
        "fork-only",
    ]


def test_malformed_jsonl_line_does_not_hide_valid_entries(tmp_path) -> None:
    path = tmp_path / "session.jsonl"
    session = SessionManager.create("project", path)
    session.append_message("user", "valid")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{broken line\n")
        handle.write(json.dumps({"type": "message", "id": "tail", "parentId": session.leaf_id, "timestamp": "now", "message": {"role": "user", "content": "tail"}}) + "\n")

    loaded = SessionManager.open(path)

    assert [message["content"] for message in loaded.build_context().messages] == ["valid", "tail"]


def test_branch_summary_is_context_visible_but_custom_entry_is_not() -> None:
    session = SessionManager.in_memory()
    session.append_message("user", "question")
    session.append_custom_entry("state", {"count": 1})
    session.append_branch_summary("facts from abandoned branch")

    contents = [message["content"] for message in session.build_context().messages]

    assert contents == ["question", "[branch summary]\nfacts from abandoned branch"]
