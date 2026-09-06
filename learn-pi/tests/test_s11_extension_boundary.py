from __future__ import annotations

import asyncio
from pathlib import Path

from s11_extension_boundary.code import (
    CommandDefinition,
    ExtensionAPI,
    ResourceLoader,
    ToolDefinition,
)


def run(coro):
    return asyncio.run(coro)


def write_resources(root: Path) -> tuple[Path, Path, Path]:
    skill = root / ".pi" / "skills" / "testing" / "SKILL.md"
    prompt = root / ".pi" / "prompts" / "review.md"
    theme = root / ".pi" / "themes" / "quiet.json"
    skill.parent.mkdir(parents=True)
    prompt.parent.mkdir(parents=True)
    theme.parent.mkdir(parents=True)
    skill.write_text("---\nname: testing\ndescription: 测试流程\n---\n先跑测试。\n", encoding="utf-8")
    prompt.write_text("检查变更。", encoding="utf-8")
    theme.write_text('{"accent":"green"}', encoding="utf-8")
    return skill, prompt, theme


def test_extension_registers_tool_command_and_lifecycle_events(tmp_path) -> None:
    calls: list[str] = []

    def extension(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("echo", "回显", lambda _args: "ok"))
        api.on("session_start", lambda _event: calls.append("session_start"))
        api.on("resources_discover", lambda _event: calls.append("resources_discover"))
        api.register_command(CommandDefinition("inspect", "检查"))

    snapshot = run(ResourceLoader(tmp_path, tmp_path / ".agent", extensions=(("demo", extension),)).reload())

    assert [tool.name for tool in snapshot.tools] == ["echo"]
    assert [command.name for command in snapshot.commands] == ["inspect"]
    assert calls == ["session_start", "resources_discover"]
    assert snapshot.events == ("extensions_loaded", "session_start", "resources_discover")


def test_loader_discovers_skills_prompts_themes_and_context_files(tmp_path) -> None:
    write_resources(tmp_path)
    (tmp_path / "AGENTS.md").write_text("项目约定", encoding="utf-8")

    snapshot = run(ResourceLoader(tmp_path, tmp_path / ".agent").reload())

    assert [skill.name for skill in snapshot.skills] == ["testing"]
    assert snapshot.skills[0].description == "测试流程"
    assert [prompt.name for prompt in snapshot.prompts] == ["review"]
    assert [theme.name for theme in snapshot.themes] == ["quiet"]
    assert snapshot.context_files[0].content == "项目约定"


def test_resources_discovered_by_extension_are_loaded(tmp_path) -> None:
    skill, prompt, theme = write_resources(tmp_path / "extension-assets")

    def extension(api: ExtensionAPI) -> None:
        api.on(
            "resources_discover",
            lambda _event: {
                "skill_paths": [skill.parent],
                "prompt_paths": [prompt],
                "theme_paths": [theme],
            },
        )

    snapshot = run(ResourceLoader(tmp_path, tmp_path / ".agent", extensions=(("assets", extension),)).reload())

    assert [skill.name for skill in snapshot.skills] == ["testing"]
    assert [prompt.name for prompt in snapshot.prompts] == ["review"]
    assert [theme.name for theme in snapshot.themes] == ["quiet"]


def test_no_flags_disable_discovery_but_keep_explicit_paths(tmp_path) -> None:
    skill, prompt, theme = write_resources(tmp_path / "explicit")
    (tmp_path / ".pi" / "skills" / "auto").mkdir(parents=True)
    (tmp_path / ".pi" / "skills" / "auto" / "SKILL.md").write_text("自动技能", encoding="utf-8")

    snapshot = run(
        ResourceLoader(
            tmp_path,
            tmp_path / ".agent",
            additional_skill_paths=[skill],
            additional_prompt_paths=[prompt],
            additional_theme_paths=[theme],
            no_skills=True,
            no_prompts=True,
            no_themes=True,
            no_context_files=True,
        ).reload()
    )

    assert [item.name for item in snapshot.skills] == ["testing"]
    assert [item.name for item in snapshot.prompts] == ["review"]
    assert [item.name for item in snapshot.themes] == ["quiet"]
    assert snapshot.context_files == ()


def test_missing_and_invalid_resources_are_reported_without_aborting_load(tmp_path) -> None:
    invalid_theme = tmp_path / "bad.json"
    invalid_theme.write_text("not json", encoding="utf-8")
    missing = tmp_path / "missing.md"

    snapshot = run(
        ResourceLoader(
            tmp_path,
            tmp_path / ".agent",
            additional_skill_paths=[missing],
            additional_theme_paths=[invalid_theme],
        ).reload()
    )

    assert snapshot.skills == ()
    assert snapshot.themes == ()
    assert any("主题解析失败" in item.message for item in snapshot.diagnostics)


def test_extension_failure_isolated_and_other_extensions_still_load(tmp_path) -> None:
    def broken(_api: ExtensionAPI) -> None:
        raise RuntimeError("extension exploded")

    def healthy(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("healthy", "正常", lambda _args: "ok"))

    snapshot = run(
        ResourceLoader(
            tmp_path,
            tmp_path / ".agent",
            extensions=(("broken", broken), ("healthy", healthy)),
        ).reload()
    )

    assert [tool.name for tool in snapshot.tools] == ["healthy"]
    assert any(item.extension == "broken" and "exploded" in item.message for item in snapshot.diagnostics)


def test_tool_name_collision_is_diagnostic_and_load_order_is_preserved(tmp_path) -> None:
    def first(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("same", "first", lambda _args: "first"))

    def second(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("same", "second", lambda _args: "second"))

    snapshot = run(
        ResourceLoader(
            tmp_path,
            tmp_path / ".agent",
            extensions=(("first", first), ("second", second)),
        ).reload()
    )

    assert [tool.description for tool in snapshot.tools] == ["first", "second"]
    assert any("工具名称冲突" in item.message for item in snapshot.diagnostics)


def test_reload_rebuilds_snapshot_instead_of_accumulating_old_tools(tmp_path) -> None:
    def extension(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("echo", "echo", lambda _args: "ok"))

    loader = ResourceLoader(tmp_path, tmp_path / ".agent", extensions=(("demo", extension),))
    first = run(loader.reload())
    second = run(loader.reload("reload"))

    assert [tool.name for tool in first.tools] == ["echo"]
    assert [tool.name for tool in second.tools] == ["echo"]
    assert second.events[-1] == "resources_discover"
