from pathlib import Path
from typing import Any, Dict

from config import BASE_DIR


def load_yaml_config(relative_path: str) -> Dict[str, Any]:
    path = BASE_DIR / relative_path
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    config: Dict[str, Any] = {}
    current_section = None
    current_field = None
    buffer = []

    def flush_field():
        nonlocal buffer, current_field, current_section
        if current_section and current_field:
            config[current_section][current_field] = "\n".join(buffer).strip()
        buffer = []

    for raw_line in lines:
        if not raw_line.strip():
            if current_field:
                buffer.append("")
            continue

        if not raw_line.startswith(" ") and raw_line.endswith(":"):
            flush_field()
            current_section = raw_line[:-1].strip()
            config[current_section] = {}
            current_field = None
            continue

        if raw_line.startswith("  ") and not raw_line.startswith("    "):
            flush_field()
            field_line = raw_line.strip()
            if field_line.endswith(": >"):
                current_field = field_line[:-3].strip()
            elif field_line.endswith(":"):
                current_field = field_line[:-1].strip()
            else:
                key, _, value = field_line.partition(":")
                current_field = key.strip()
                buffer = [value.strip()]
                flush_field()
                current_field = None
            continue

        if current_field:
            buffer.append(raw_line.strip())

    flush_field()
    return config
