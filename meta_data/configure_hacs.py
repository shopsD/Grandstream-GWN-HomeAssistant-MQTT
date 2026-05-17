from pathlib import Path
import re

archive_root: Path = Path("dist/hacs")
vendored_root: Path = archive_root / "gwn"

from_pattern: re.Pattern[str] = re.compile(
    r"^(?P<indent>\s*)from\s+gwn(?P<module>(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s+import\s+(?P<names>.+)$",
    re.MULTILINE
)
import_pattern: re.Pattern[str] = re.compile(
    r"^(?P<indent>\s*)import\s+(?P<modules>gwn(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?(?:\s*,\s*gwn(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?)*)$",
    re.MULTILINE
)

def _relative_module(current_parent_parts: list[str], target_parts: list[str]) -> str:
    common_length: int = 0
    while (
        common_length < len(current_parent_parts)
        and common_length < len(target_parts)
        and current_parent_parts[common_length] == target_parts[common_length]
    ):
        common_length += 1
    level: int = len(current_parent_parts) - common_length + 1
    remainder: list[str] = target_parts[common_length:]
    prefix: str = "." * level
    if len(remainder) == 0:
        return prefix
    return f"{prefix}{'.'.join(remainder)}"

def _rewrite_from_line(target_file: Path, match: re.Match[str]) -> str:
    indent: str = match.group("indent")
    module_suffix: str = match.group("module")
    imported_names: str = match.group("names")
    module_parts: list[str] = module_suffix.removeprefix(".").split(".") if len(module_suffix) > 0 else []

    if vendored_root in target_file.parents:
        current_parent_parts: list[str] = list(target_file.relative_to(vendored_root).parent.parts)
        relative_module: str = _relative_module(current_parent_parts, module_parts)
        return f"{indent}from {relative_module} import {imported_names}"

    relative_module = f".gwn{module_suffix}"
    return f"{indent}from {relative_module} import {imported_names}"

def _rewrite_import_line(target_file: Path, match: re.Match[str]) -> str:
    indent: str = match.group("indent")
    raw_modules: str = match.group("modules")
    rewritten_lines: list[str] = []

    for raw_module in raw_modules.split(","):
        module_entry: str = raw_module.strip()
        module_name: str
        alias_name: str | None = None
        if " as " in module_entry:
            module_name, alias_name = module_entry.split(" as ", 1)
        else:
            module_name = module_entry

        module_parts: list[str] = module_name.split(".")
        if module_parts[0] != "gwn":
            rewritten_lines.append(f"{indent}import {module_entry}")
            continue

        target_parts: list[str] = module_parts[1:]
        if len(target_parts) == 0:
            raise RuntimeError(f"Unsupported import rewrite in {target_file}: {module_entry}")

        imported_name: str = target_parts[-1]
        import_suffix: str = f" as {alias_name}" if alias_name is not None else ""

        if vendored_root in target_file.parents:
            current_parent_parts: list[str] = list(target_file.relative_to(vendored_root).parent.parts)
            relative_module: str = _relative_module(current_parent_parts, target_parts[:-1])
            rewritten_lines.append(f"{indent}from {relative_module} import {imported_name}{import_suffix}")
        else:
            if len(target_parts) == 1:
                rewritten_lines.append(f"{indent}from .gwn import {imported_name}{import_suffix}")
            else:
                rewritten_lines.append(
                    f"{indent}from .gwn.{'.'.join(target_parts[:-1])} import {imported_name}{import_suffix}"
                )

    return "\n".join(rewritten_lines)

def main() -> None:
    staged_files: list[Path] = sorted(archive_root.rglob("*.py"))
    for target_file in staged_files:
        content: str = target_file.read_text(encoding="utf-8")
        updated_content: str = from_pattern.sub(lambda match: _rewrite_from_line(target_file, match), content)
        updated_content = import_pattern.sub(lambda match: _rewrite_import_line(target_file, match), updated_content)
        target_file.write_text(updated_content, encoding="utf-8")

if __name__ == "__main__":
    main()
