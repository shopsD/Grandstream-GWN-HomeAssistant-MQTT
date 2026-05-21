import json
import re
import shutil
from pathlib import Path

ROOT_NAME="gwn"

integration_root: Path = Path("custom_components/grandstream_gwn")
archive_root: Path = Path("dist/hacs")
library_root: Path = Path(ROOT_NAME)
hacs_archive_root: Path = archive_root / library_root
translations_root: Path = archive_root / "translations"

ignore_patterns: set[str] = set(["__pycache__*", "*.pyc", "*.pyo"])

from_pattern: re.Pattern[str] = re.compile(
    r"^(?P<indent>\s*)from\s+gwn(?P<module>(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s+import\s+(?P<names>.+)$",
    re.MULTILINE
)
import_pattern: re.Pattern[str] = re.compile(
    r"^(?P<indent>\s*)import\s+(?P<modules>gwn(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?(?:\s*,\s*gwn(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?)*)$",
    re.MULTILINE
)
translation_key_pattern: re.Pattern[str] = re.compile(r"^\[%key:(?P<key>.+)%\]$")

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

    if hacs_archive_root in target_file.parents:
        current_parent_parts: list[str] = list(target_file.relative_to(hacs_archive_root).parent.parts)
        relative_module: str = _relative_module(current_parent_parts, module_parts)
        return f"{indent}from {relative_module} import {imported_names}"

    relative_module = f".{ROOT_NAME}{module_suffix}"
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
        if module_parts[0] != ROOT_NAME:
            rewritten_lines.append(f"{indent}import {module_entry}")
            continue

        target_parts: list[str] = module_parts[1:]
        if len(target_parts) == 0:
            raise RuntimeError(f"Unsupported import rewrite in {target_file}: {module_entry}")

        imported_name: str = target_parts[-1]
        import_suffix: str = f" as {alias_name}" if alias_name is not None else ""

        if hacs_archive_root in target_file.parents:
            current_parent_parts: list[str] = list(target_file.relative_to(hacs_archive_root).parent.parts)
            relative_module: str = _relative_module(current_parent_parts, target_parts[:-1])
            rewritten_lines.append(f"{indent}from {relative_module} import {imported_name}{import_suffix}")
        elif len(target_parts) == 1:
            rewritten_lines.append(f"{indent}from .{ROOT_NAME} import {imported_name}{import_suffix}")
        else:
            rewritten_lines.append(f"{indent}from .{ROOT_NAME}.{'.'.join(target_parts[:-1])} import {imported_name}{import_suffix}")

    return "\n".join(rewritten_lines)

def _setup_directory_structure() -> None:
    if archive_root.exists() and archive_root.is_dir():
        shutil.rmtree(archive_root)
    shutil.copytree(integration_root.resolve(), archive_root.resolve(), dirs_exist_ok=True, ignore=shutil.ignore_patterns(*ignore_patterns))
    shutil.copytree(library_root.resolve(), hacs_archive_root.resolve(), dirs_exist_ok=True, ignore=shutil.ignore_patterns(*ignore_patterns))

def _lookup_translation_key(document: dict[str, object], key_path: str) -> object:
    value: object = document
    for key in key_path.split("::"):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(f"Unable to resolve translation key path: {key_path}")
        value = value[key]
    return value

def _expand_translation_value(document: dict[str, object], value: object, used_key_paths: set[str]) -> object:
    if isinstance(value, dict):
        return {
            key: _expand_translation_value(document, nested_value, used_key_paths)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_expand_translation_value(document, nested_value, used_key_paths) for nested_value in value]
    if isinstance(value, str):
        match: re.Match[str] | None = translation_key_pattern.fullmatch(value)
        if match is None:
            return value
        key_path: str = match.group("key")
        used_key_paths.add(key_path)
        return _expand_translation_value(document, _lookup_translation_key(document, key_path), used_key_paths)
    return value

def _remove_key_path(document: dict[str, object], key_path: str) -> None:
    parts: list[str] = key_path.split("::")
    current: dict[str, object] | None = document
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        nested: object | None = current.get(part)
        if not isinstance(nested, dict):
            return
        current = nested
    if isinstance(current, dict):
        current.pop(parts[-1], None)

def _prune_empty_containers(value: object) -> object | None:
    if isinstance(value, dict):
        pruned_dict: dict[str, object] = {}
        for key, nested_value in value.items():
            pruned_value: object | None = _prune_empty_containers(nested_value)
            if pruned_value is not None:
                pruned_dict[key] = pruned_value
        return None if len(pruned_dict) == 0 else pruned_dict
    if isinstance(value, list):
        pruned_list: list[object] = []
        for nested_value in value:
            pruned_value: object | None = _prune_empty_containers(nested_value)
            if pruned_value is not None:
                pruned_list.append(pruned_value)
        return None if len(pruned_list) == 0 else pruned_list
    return value

def _expand_translation_file(path: Path) -> None:
    document: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    used_key_paths: set[str] = set()
    expanded_document: dict[str, object] = _expand_translation_value(document, document, used_key_paths)
    for key_path in sorted(used_key_paths, key=lambda value: value.count("::"), reverse=True):
        _remove_key_path(expanded_document, key_path)
    pruned_document: object | None = _prune_empty_containers(expanded_document)
    if not isinstance(pruned_document, dict):
        raise RuntimeError(f"Expanded translation file is not a dictionary: {path}")
    path.write_text(json.dumps(pruned_document, indent=4, ensure_ascii=True) + "\n", encoding="utf-8")

def _expand_translation_files() -> None:
    if not translations_root.exists():
        return
    for translation_file in sorted(translations_root.glob("*.json")):
        _expand_translation_file(translation_file)

def main() -> None:
    _setup_directory_structure()
    staged_files: list[Path] = sorted(archive_root.rglob("*.py"))
    for target_file in staged_files:
        content: str = target_file.read_text(encoding="utf-8")
        updated_content: str = from_pattern.sub(lambda match: _rewrite_from_line(target_file, match), content)
        updated_content = import_pattern.sub(lambda match: _rewrite_import_line(target_file, match), updated_content)
        target_file.write_text(updated_content, encoding="utf-8")
    _expand_translation_files()

if __name__ == "__main__":
    main()
