#!/usr/bin/env python3
"""第 11 章：扩展 API、资源发现和失败隔离。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
import inspect
import json
from pathlib import Path
from typing import Any, Literal, TypeAlias

ResourceEventName = Literal["session_start", "resources_discover"]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    execute: Callable[[dict[str, Any]], str | Awaitable[str]]


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ResourceDiagnostic:
    kind: Literal["error", "warning"]
    message: str
    path: str | None = None
    extension: str | None = None


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    path: str
    content: str


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    path: str
    content: str


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    path: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ContextFile:
    path: str
    content: str


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    tools: tuple[ToolDefinition, ...]
    commands: tuple[CommandDefinition, ...]
    skills: tuple[Skill, ...]
    prompts: tuple[PromptTemplate, ...]
    themes: tuple[Theme, ...]
    context_files: tuple[ContextFile, ...]
    diagnostics: tuple[ResourceDiagnostic, ...]
    events: tuple[str, ...]


ExtensionHandler: TypeAlias = Callable[[dict[str, Any]], Any | Awaitable[Any]]
ExtensionFactory: TypeAlias = Callable[["ExtensionAPI"], None | Awaitable[None]]
NamedExtension: TypeAlias = tuple[str, ExtensionFactory]


class ExtensionAPI:
    """扩展拿到的窄 API；核心循环只消费最终注册结果。"""

    def __init__(self) -> None:
        self.tools: list[ToolDefinition] = []
        self.commands: list[CommandDefinition] = []
        self.handlers: dict[ResourceEventName, list[ExtensionHandler]] = {
            "session_start": [],
            "resources_discover": [],
        }

    def register_tool(self, tool: ToolDefinition) -> None:
        self.tools.append(tool)

    def register_command(self, command: CommandDefinition) -> None:
        self.commands.append(command)

    def on(self, event: ResourceEventName, handler: ExtensionHandler) -> None:
        self.handlers[event].append(handler)


class ResourceLoader:
    """离线版 DefaultResourceLoader，负责发现资源而不是执行 Agent。"""

    def __init__(
        self,
        cwd: str | Path,
        agent_dir: str | Path,
        *,
        extensions: Sequence[NamedExtension] = (),
        additional_skill_paths: Sequence[str | Path] = (),
        additional_prompt_paths: Sequence[str | Path] = (),
        additional_theme_paths: Sequence[str | Path] = (),
        no_extensions: bool = False,
        no_skills: bool = False,
        no_prompts: bool = False,
        no_themes: bool = False,
        no_context_files: bool = False,
    ) -> None:
        self.cwd = Path(cwd).resolve()
        self.agent_dir = Path(agent_dir).resolve()
        self.extensions = tuple(extensions)
        self.additional_skill_paths = tuple(self._resolve_path(Path(path)) for path in additional_skill_paths)
        self.additional_prompt_paths = tuple(self._resolve_path(Path(path)) for path in additional_prompt_paths)
        self.additional_theme_paths = tuple(self._resolve_path(Path(path)) for path in additional_theme_paths)
        self.no_extensions = no_extensions
        self.no_skills = no_skills
        self.no_prompts = no_prompts
        self.no_themes = no_themes
        self.no_context_files = no_context_files
        self.snapshot = ResourceSnapshot((), (), (), (), (), (), (), ())

    async def reload(self, reason: Literal["startup", "reload"] = "startup") -> ResourceSnapshot:
        """重新建立本次资源快照；旧快照不会与新快照混合。"""

        api = ExtensionAPI()
        diagnostics: list[ResourceDiagnostic] = []
        events: list[str] = []

        if not self.no_extensions:
            for name, factory in self.extensions:
                try:
                    result = factory(api)
                    if inspect.isawaitable(result):
                        await result
                except Exception as error:
                    diagnostics.append(ResourceDiagnostic("error", str(error), extension=name))
        events.append("extensions_loaded")

        # Session start 允许扩展注册动态工具；随后资源发现返回额外路径。
        await self._emit_handlers(api, "session_start", {"type": "session_start", "reason": reason}, diagnostics)
        events.append("session_start")
        discovered = await self._discover_extension_resources(api, reason, diagnostics)
        events.append("resources_discover")

        skill_paths = [*self._default_paths("skills"), *self.additional_skill_paths, *discovered["skill_paths"]]
        prompt_paths = [*self._default_paths("prompts"), *self.additional_prompt_paths, *discovered["prompt_paths"]]
        theme_paths = [*self._default_paths("themes"), *self.additional_theme_paths, *discovered["theme_paths"]]

        skills = self._load_skills(skill_paths, diagnostics) if not self.no_skills else self._load_skills(
            [*self.additional_skill_paths, *discovered["skill_paths"]], diagnostics
        )
        prompts = self._load_prompts(prompt_paths, diagnostics) if not self.no_prompts else self._load_prompts(
            [*self.additional_prompt_paths, *discovered["prompt_paths"]], diagnostics
        )
        themes = self._load_themes(theme_paths, diagnostics) if not self.no_themes else self._load_themes(
            [*self.additional_theme_paths, *discovered["theme_paths"]], diagnostics
        )
        context_files = self._load_context_files() if not self.no_context_files else []
        for label, paths in (
            ("Skill", [*self.additional_skill_paths, *discovered["skill_paths"]]),
            ("Prompt", [*self.additional_prompt_paths, *discovered["prompt_paths"]]),
            ("Theme", [*self.additional_theme_paths, *discovered["theme_paths"]]),
        ):
            for path in paths:
                if not path.exists():
                    diagnostics.append(ResourceDiagnostic("error", f"{label} 路径不存在", str(path)))

        self._report_tool_collisions(api.tools, diagnostics)
        self._report_command_collisions(api.commands, diagnostics)
        self.snapshot = ResourceSnapshot(
            tools=tuple(api.tools),
            commands=tuple(api.commands),
            skills=tuple(skills),
            prompts=tuple(prompts),
            themes=tuple(themes),
            context_files=tuple(context_files),
            diagnostics=tuple(diagnostics),
            events=tuple(events),
        )
        return self.snapshot

    def _default_paths(self, kind: Literal["skills", "prompts", "themes"]) -> list[Path]:
        return [self.agent_dir / kind, self.cwd / ".pi" / kind]

    def _resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.cwd / path

    async def _emit_handlers(
        self,
        api: ExtensionAPI,
        event_name: ResourceEventName,
        event: dict[str, Any],
        diagnostics: list[ResourceDiagnostic],
    ) -> list[Any]:
        results: list[Any] = []
        for handler in api.handlers[event_name]:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    result = await result
                results.append(result)
            except Exception as error:
                diagnostics.append(ResourceDiagnostic("error", str(error), extension="extension-handler"))
        return results

    async def _discover_extension_resources(
        self,
        api: ExtensionAPI,
        reason: Literal["startup", "reload"],
        diagnostics: list[ResourceDiagnostic],
    ) -> dict[str, list[Path]]:
        discovered: dict[str, list[Path]] = {"skill_paths": [], "prompt_paths": [], "theme_paths": []}
        results = await self._emit_handlers(
            api,
            "resources_discover",
            {"type": "resources_discover", "cwd": str(self.cwd), "reason": reason},
            diagnostics,
        )
        for result in results:
            if not isinstance(result, dict):
                continue
            for key in discovered:
                values = result.get(key, [])
                if isinstance(values, (str, Path)):
                    values = [values]
                if isinstance(values, Iterable):
                    discovered[key].extend(self._resolve_path(Path(value)) for value in values)
        return discovered

    @staticmethod
    def _files(paths: Sequence[Path], suffixes: set[str]) -> list[Path]:
        files: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            if not path.exists():
                continue
            candidates = [path] if path.is_file() else [candidate for candidate in path.rglob("*") if candidate.is_file()]
            for candidate in candidates:
                if candidate.suffix.lower() in suffixes and candidate not in seen:
                    seen.add(candidate)
                    files.append(candidate)
        return files

    @staticmethod
    def _read(path: Path, diagnostics: list[ResourceDiagnostic]) -> str | None:
        try:
            return path.read_text(encoding="utf-8-sig")
        except OSError as error:
            diagnostics.append(ResourceDiagnostic("error", f"无法读取资源: {error}", str(path)))
            return None

    def _load_skills(self, paths: Sequence[Path], diagnostics: list[ResourceDiagnostic]) -> list[Skill]:
        result: list[Skill] = []
        for path in self._files(paths, {".md"}):
            content = self._read(path, diagnostics)
            if content is None:
                continue
            name, description, body = self._parse_frontmatter(content, path.stem)
            result.append(Skill(name, description, str(path), body))
        return result

    def _load_prompts(self, paths: Sequence[Path], diagnostics: list[ResourceDiagnostic]) -> list[PromptTemplate]:
        result: list[PromptTemplate] = []
        for path in self._files(paths, {".md", ".txt"}):
            content = self._read(path, diagnostics)
            if content is not None:
                result.append(PromptTemplate(path.stem, str(path), content))
        return result

    def _load_themes(self, paths: Sequence[Path], diagnostics: list[ResourceDiagnostic]) -> list[Theme]:
        result: list[Theme] = []
        for path in self._files(paths, {".json"}):
            content = self._read(path, diagnostics)
            if content is None:
                continue
            try:
                data = json.loads(content)
                if not isinstance(data, dict):
                    raise ValueError("主题文件必须是 JSON 对象")
                result.append(Theme(path.stem, str(path), data))
            except (json.JSONDecodeError, ValueError) as error:
                diagnostics.append(ResourceDiagnostic("error", f"主题解析失败: {error}", str(path)))
        return result

    @staticmethod
    def _parse_frontmatter(content: str, fallback_name: str) -> tuple[str, str, str]:
        if not content.startswith("---"):
            return fallback_name, "", content
        lines = content.splitlines()
        try:
            end = lines.index("---", 1)
        except ValueError:
            return fallback_name, "", content
        metadata: dict[str, str] = {}
        for line in lines[1:end]:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        body = "\n".join(lines[end + 1 :]).lstrip("\n")
        return metadata.get("name", fallback_name), metadata.get("description", ""), body

    def _load_context_files(self) -> list[ContextFile]:
        # 全局文件先加入，项目祖先从根到 cwd 加入；同一目录只取优先级最高的候选名。
        result: list[ContextFile] = []
        global_file = self._context_file_in(self.agent_dir)
        if global_file is not None:
            result.append(global_file)

        ancestors: list[Path] = []
        current = self.cwd
        while True:
            ancestors.append(current)
            if current.parent == current:
                break
            current = current.parent
        for directory in reversed(ancestors):
            context_file = self._context_file_in(directory)
            if context_file is not None and context_file.path not in {item.path for item in result}:
                result.append(context_file)
        return result

    @staticmethod
    def _context_file_in(directory: Path) -> ContextFile | None:
        for filename in ("AGENTS.override.md", "AGENTS.md", "CLAUDE.md"):
            path = directory / filename
            if path.is_file():
                try:
                    return ContextFile(str(path), path.read_text(encoding="utf-8-sig"))
                except OSError:
                    return None
        return None

    @staticmethod
    def _report_tool_collisions(tools: Sequence[ToolDefinition], diagnostics: list[ResourceDiagnostic]) -> None:
        seen: dict[str, str] = {}
        for tool in tools:
            previous = seen.get(tool.name)
            if previous is not None:
                diagnostics.append(
                    ResourceDiagnostic("warning", f"工具名称冲突，后注册工具按加载顺序生效: {tool.name}", extension=previous)
                )
            seen[tool.name] = tool.name

    @staticmethod
    def _report_command_collisions(commands: Sequence[CommandDefinition], diagnostics: list[ResourceDiagnostic]) -> None:
        seen: set[str] = set()
        for command in commands:
            if command.name in seen:
                diagnostics.append(ResourceDiagnostic("warning", f"命令名称冲突: {command.name}"))
            seen.add(command.name)


async def demo() -> None:
    root = Path(".task-output/s11-demo")
    skills_dir = root / ".pi" / "skills" / "testing"
    prompts_dir = root / ".pi" / "prompts"
    themes_dir = root / ".pi" / "themes"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    themes_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: testing\ndescription: 测试工作流\n---\n先运行离线测试。\n",
        encoding="utf-8",
    )
    (prompts_dir / "review.md").write_text("检查变更并指出风险。", encoding="utf-8")
    (themes_dir / "quiet.json").write_text('{"name":"quiet"}', encoding="utf-8")

    def extension(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("echo", "回显文本", lambda args: str(args.get("text", ""))))
        api.on("session_start", lambda _event: api.register_command(CommandDefinition("inspect", "检查资源")))

    loader = ResourceLoader(root, root / ".agent", extensions=(("demo", extension),))
    snapshot = await loader.reload()
    print("s11: extension and resource boundary\n")
    print(f"tools: {[tool.name for tool in snapshot.tools]}")
    print(f"skills: {[skill.name for skill in snapshot.skills]}")
    print(f"prompts: {[prompt.name for prompt in snapshot.prompts]}")
    print(f"themes: {[theme.name for theme in snapshot.themes]}")
    print(f"events: {list(snapshot.events)}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
