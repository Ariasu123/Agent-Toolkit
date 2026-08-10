"""MCP 提供的 bash/read/write/edit 工具。"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from .runtime import SandboxCommandResult, SandboxError
from .workspace import WorkspaceAccessError, WorkspaceGuard

MAX_OUTPUT_BYTES = 100 * 1024
MAX_LINES = 1000
MAX_LINE_CHARS = 2000


class Runtime(Protocol):
    guard: WorkspaceGuard | None

    async def execute(
        self,
        command: str,
        *,
        timeout_s: int,
        abort: asyncio.Event | None,
        on_update,
        max_output_bytes: int,
    ) -> SandboxCommandResult: ...

    async def close(self) -> None: ...

    def describe(self) -> dict[str, object]: ...


@dataclass
class ToolResult:
    text: str
    is_error: bool = False
    details: dict[str, object] | None = None


class BashArgs(BaseModel):
    command: str = Field(description="Bash command to execute")
    timeout_s: int = Field(
        default=120,
        ge=1,
        description="Timeout in seconds; the execution environment is restarted when exceeded",
    )


class ReadArgs(BaseModel):
    path: str = Field(description="Path to the file to read (relative or absolute)")
    offset: int = Field(
        default=1,
        description="Line number to start reading from (1-indexed). Negative values read from the end of the file.",
    )
    limit: int | None = Field(default=None, description="Maximum number of lines to read")


class WriteArgs(BaseModel):
    path: str = Field(description="Path to the file to write (relative or absolute)")
    content: str = Field(description="Content to write to the file")


class EditArgs(BaseModel):
    path: str = Field(description="Path to the file to edit (relative or absolute)")
    old_string: str = Field(
        description="Exact text to replace. Must be unique in the file unless replace_all is set."
    )
    new_string: str = Field(description="Replacement text")
    replace_all: bool = Field(
        default=False, description="Replace every occurrence of old_string"
    )


class Tool:
    name: str
    description: str
    Args: type[BaseModel]

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.guard = runtime.guard

    @property
    def parameters(self) -> dict[str, Any]:
        return self.Args.model_json_schema()

    def validate(self, raw: dict[str, Any]) -> BaseModel:
        try:
            return self.Args.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"Invalid arguments for tool {self.name}: {exc}") from exc

    def details(self, values: dict[str, object]) -> dict[str, object]:
        return {**self.runtime.describe(), **values}


class BashTool(Tool):
    name = "bash"
    description = (
        "Execute a bash command. Returns combined stdout and stderr, truncated to the last "
        f"{MAX_OUTPUT_BYTES // 1024}KB. Non-zero exit codes are reported in the output, not raised."
    )
    Args = BashArgs

    async def execute(self, args: BashArgs) -> ToolResult:
        try:
            result = await self.runtime.execute(
                args.command,
                timeout_s=args.timeout_s,
                abort=None,
                on_update=None,
                max_output_bytes=MAX_OUTPUT_BYTES,
            )
        except SandboxError as exc:
            return ToolResult(
                f"Error: sandbox command failed: {exc}",
                details=self.details({"exitCode": None, "truncated": False}),
            )
        output = result.output
        if result.truncated:
            output = (
                f"[output truncated: showing last ~{MAX_OUTPUT_BYTES // 1024}KB]\n\n{output}"
            )
        details = self.details(
            {
                "exitCode": result.exit_code,
                "truncated": result.truncated,
                "timedOut": result.timed_out,
                "aborted": result.aborted,
            }
        )
        if result.aborted:
            return ToolResult(
                f"Command aborted.\n\n{output}" if output else "Command aborted.",
                details=details,
            )
        if result.timed_out:
            note = f"Error: command timed out after {args.timeout_s}s and was killed."
            return ToolResult(f"{note}\n\n{output}" if output else note, details=details)
        text = output
        if result.exit_code != 0:
            note = f"[exit code {result.exit_code}]"
            text = f"{text}\n\n{note}" if text else note
        return ToolResult(text or "(no output)", details=details)


class ReadTool(Tool):
    name = "read"
    description = (
        f"Read the contents of a file as UTF-8 text with line numbers. Output is truncated to "
        f"{MAX_LINES} lines or {MAX_OUTPUT_BYTES // 1024}KB; lines longer than "
        f"{MAX_LINE_CHARS} characters are truncated. Use offset/limit for large files."
    )
    Args = ReadArgs

    async def execute(self, args: ReadArgs) -> ToolResult:
        try:
            path = self.guard.resolve(args.path, "read") if self.guard else Path(args.path).expanduser()
        except WorkspaceAccessError as exc:
            return ToolResult(f"Error: {exc}", details=self.details({"denied": True}))
        try:
            if self.guard:
                fd = self.guard.open_file(args.path, "read", os.O_RDONLY)
                with os.fdopen(fd, "rb") as handle:
                    raw = handle.read()
            else:
                raw = path.read_bytes()
        except FileNotFoundError:
            return ToolResult(f"Error: file not found: {args.path}", details=self.details({}))
        except IsADirectoryError:
            return ToolResult(
                f"Error: path is a directory, not a file: {args.path}",
                details=self.details({}),
            )
        except OSError as exc:
            return ToolResult(f"Error: could not read {args.path}: {exc}", details=self.details({}))
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                f"Error: {args.path} is not valid UTF-8 text", details=self.details({})
            )
        lines = text.split("\n")
        total_lines = len(lines)
        start = max(0, total_lines + args.offset) if args.offset < 0 else args.offset - 1
        if start >= total_lines:
            return ToolResult(
                f"Error: offset {args.offset} is beyond end of file ({total_lines} lines total)",
                details=self.details(
                    {"truncated": False, "linesReturned": 0, "totalLines": total_lines}
                ),
            )
        selected = lines[start:]
        if args.limit is not None:
            selected = selected[: max(0, args.limit)]
        truncated = len(selected) > MAX_LINES
        selected = selected[:MAX_LINES]
        out_lines: list[str] = []
        out_bytes = 0
        for index, line in enumerate(selected):
            if len(line) > MAX_LINE_CHARS:
                line = line[:MAX_LINE_CHARS] + " [... line truncated]"
                truncated = True
            numbered = f"{start + index + 1}\t{line}"
            size = len(numbered.encode("utf-8")) + (1 if out_lines else 0)
            if out_bytes + size > MAX_OUTPUT_BYTES:
                truncated = True
                break
            out_lines.append(numbered)
            out_bytes += size
        output = "\n".join(out_lines)
        last_display = start + len(out_lines)
        if last_display < total_lines:
            note = (
                f"[Showing lines {start + 1}-{last_display} of {total_lines}. "
                f"Use offset={last_display + 1} to continue.]"
            )
            output = f"{output}\n\n{note}" if output else note
        return ToolResult(
            output,
            details=self.details(
                {
                    "truncated": truncated,
                    "linesReturned": len(out_lines),
                    "totalLines": total_lines,
                }
            ),
        )


class WriteTool(Tool):
    name = "write"
    description = (
        "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
        "Automatically creates parent directories."
    )
    Args = WriteArgs

    async def execute(self, args: WriteArgs) -> ToolResult:
        try:
            path = self.guard.resolve(args.path, "write") if self.guard else Path(args.path).expanduser()
        except WorkspaceAccessError as exc:
            return ToolResult(f"Error: {exc}", details=self.details({"denied": True}))
        try:
            if self.guard:
                fd = self.guard.open_file(
                    args.path,
                    "write",
                    os.O_WRONLY | os.O_CREAT,
                    create_parents=True,
                )
                with os.fdopen(fd, "wb") as handle:
                    os.ftruncate(handle.fileno(), 0)
                    handle.write(args.content.encode("utf-8"))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(args.content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(f"Error: could not write {args.path}: {exc}", details=self.details({}))
        num_bytes = len(args.content.encode("utf-8"))
        return ToolResult(
            f"Successfully wrote {num_bytes} bytes to {args.path}",
            details=self.details({"bytes": num_bytes}),
        )


class EditTool(Tool):
    name = "edit"
    description = (
        "Edit a file using exact text replacement. old_string must match the file content "
        "exactly and must be unique unless replace_all is set."
    )
    Args = EditArgs

    async def execute(self, args: EditArgs) -> ToolResult:
        if not args.old_string:
            return ToolResult(
                "Error: old_string must not be empty",
                details=self.details({"replacements": 0}),
            )
        try:
            path = self.guard.resolve(args.path, "edit") if self.guard else Path(args.path).expanduser()
        except WorkspaceAccessError as exc:
            return ToolResult(
                f"Error: {exc}",
                details=self.details({"denied": True, "replacements": 0}),
            )
        secure_handle = None
        try:
            try:
                if self.guard:
                    fd = self.guard.open_file(args.path, "edit", os.O_RDWR)
                    secure_handle = os.fdopen(fd, "r+b")
                    content = secure_handle.read().decode("utf-8")
                else:
                    content = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                return ToolResult(
                    f"Error: file not found: {args.path}",
                    details=self.details({"replacements": 0}),
                )
            except IsADirectoryError:
                return ToolResult(
                    f"Error: path is a directory, not a file: {args.path}",
                    details=self.details({"replacements": 0}),
                )
            except (OSError, UnicodeDecodeError) as exc:
                return ToolResult(
                    f"Error: could not read {args.path}: {exc}",
                    details=self.details({"replacements": 0}),
                )
            occurrences = content.count(args.old_string)
            if occurrences == 0:
                return ToolResult(
                    f"Error: old_string not found in {args.path}. It must match the file content exactly.",
                    details=self.details({"replacements": 0}),
                )
            if occurrences > 1 and not args.replace_all:
                return ToolResult(
                    f"Error: old_string occurs {occurrences} times in {args.path}. "
                    "Provide more context to make it unique, or set replace_all to true.",
                    details=self.details({"replacements": 0}),
                )
            replacements = occurrences if args.replace_all else 1
            updated = content.replace(
                args.old_string, args.new_string, -1 if args.replace_all else 1
            )
            try:
                if secure_handle:
                    secure_handle.seek(0)
                    secure_handle.write(updated.encode("utf-8"))
                    secure_handle.truncate()
                else:
                    path.write_text(updated, encoding="utf-8")
            except OSError as exc:
                return ToolResult(
                    f"Error: could not write {args.path}: {exc}",
                    details=self.details({"replacements": 0}),
                )
            return ToolResult(
                f"Successfully replaced {replacements} occurrence(s) in {args.path}.",
                details=self.details({"replacements": replacements}),
            )
        finally:
            if secure_handle:
                secure_handle.close()


def build_tools(runtime: Runtime) -> dict[str, Tool]:
    tools: list[Tool] = [ReadTool(runtime), WriteTool(runtime), EditTool(runtime), BashTool(runtime)]
    return {tool.name: tool for tool in tools}


__all__ = [
    "BashArgs",
    "BashTool",
    "EditArgs",
    "EditTool",
    "ReadArgs",
    "ReadTool",
    "Runtime",
    "ToolResult",
    "WriteArgs",
    "WriteTool",
    "build_tools",
]
