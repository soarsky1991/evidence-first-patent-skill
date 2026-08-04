#!/usr/bin/env python3
"""Vendored copy of the Skill Creator quick validator for offline CI.

Keep its validation behavior aligned with the local official validator used by the
development runtime. The small offline copy avoids a CI dependency on a user-local path.
"""
import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # Keep the install-layout check usable with stdlib Python.
    yaml = None

MAX_SKILL_NAME_LENGTH = 64


def load_frontmatter(value: str):
    """Load the small Skill frontmatter subset without requiring PyYAML.

    The archive check only needs the flat public contract fields.  Use PyYAML
    when it is available; otherwise support quoted or unquoted scalar values
    and empty mapping-valued optional keys.  Nested metadata is accepted as an
    opaque mapping because this validator checks only the permitted top-level
    names plus the required string fields.
    """
    if yaml is not None:
        return yaml.safe_load(value)

    result = {}
    active_mapping = None
    for raw_line in value.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[0].isspace():
            if active_mapping is None:
                raise ValueError("nested content without a mapping key")
            continue
        if ":" not in raw_line:
            raise ValueError("invalid frontmatter line")
        key, raw_value = raw_line.split(":", 1)
        key, raw_value = key.strip(), raw_value.strip()
        if not key:
            raise ValueError("empty frontmatter key")
        if raw_value:
            if (raw_value.startswith('"') and raw_value.endswith('"')) or (
                raw_value.startswith("'") and raw_value.endswith("'")
            ):
                raw_value = raw_value[1:-1]
            result[key] = raw_value
            active_mapping = None
        else:
            result[key] = {}
            active_mapping = key
    return result


def validate_skill(skill_path):
    skill_path = Path(skill_path)
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"
    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"
    try:
        frontmatter = load_frontmatter(match.group(1))
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except Exception as exc:
        return False, f"Invalid YAML in frontmatter: {exc}"
    allowed = {"name", "description", "license", "allowed-tools", "metadata"}
    unexpected = set(frontmatter) - allowed
    if unexpected:
        return False, "Unexpected key(s) in SKILL.md frontmatter: " + ", ".join(sorted(unexpected))
    if "name" not in frontmatter or "description" not in frontmatter:
        return False, "Missing name or description in frontmatter"
    name = frontmatter["name"]
    description = frontmatter["description"]
    if not isinstance(name, str) or not isinstance(description, str):
        return False, "Name and description must be strings"
    name = name.strip(); description = description.strip()
    if name and (not re.match(r"^[a-z0-9-]+$", name) or name.startswith("-") or name.endswith("-") or "--" in name or len(name) > MAX_SKILL_NAME_LENGTH):
        return False, "Invalid skill name"
    if description and ("<" in description or ">" in description or len(description) > 1024):
        return False, "Invalid description"
    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        raise SystemExit(1)
    ok, message = validate_skill(sys.argv[1])
    print(message)
    raise SystemExit(0 if ok else 1)
