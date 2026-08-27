from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path


FORBIDDEN_NAMES = (
    "LLM API KEY.txt",
    "settings.local.toml",
    ".git/",
    ".venv/",
    "node_modules/",
    "playwright-report/",
    "test-results/",
    "game.db",
)
FORBIDDEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def version_label(version: str) -> str:
    parts = version.split(".")
    if len(parts) >= 3 and parts[2] != "0":
        return ".".join(parts[:3])
    return ".".join(parts[:2])


def read_project_version(project_root: Path) -> str:
    for line in (project_root / "pyproject.toml").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.startswith("version = "):
            return line.split('"', 2)[1]
    raise RuntimeError("pyproject.toml 中未找到项目版本")


def audit(zip_path: Path, project_root: Path) -> tuple[int, str]:
    expected_version = version_label(read_project_version(project_root))
    expected_exe = "霍格沃兹人生模拟器.exe"
    errors: list[str] = []

    with zipfile.ZipFile(zip_path) as archive:
        bad_crc = archive.testzip()
        if bad_crc:
            errors.append(f"CRC 校验失败：{bad_crc}")
        names = [name.replace("\\", "/") for name in archive.namelist()]
        top_levels = {name.split("/", 1)[0] for name in names if name}
        if len(top_levels) != 1:
            errors.append(f"ZIP 必须只有一个顶层目录，当前为：{sorted(top_levels)}")
        if not any(name.endswith(f"/{expected_exe}") for name in names):
            errors.append(f"缺少 {expected_exe}")
        if not any("/_internal/" in name for name in names):
            errors.append("缺少 _internal 运行资源目录")
        if not any(
            name.endswith("/_internal/frontend/dist/index.html")
            for name in names
        ):
            errors.append("缺少 _internal/frontend/dist/index.html")
        if not any(
            name.endswith("/_internal/config/settings.example.toml")
            for name in names
        ):
            errors.append("缺少 _internal/config/settings.example.toml")
        if not any(name.endswith("/玩家指南.txt") for name in names):
            errors.append("缺少 玩家指南.txt")
        for name in names:
            lowered = name.casefold()
            if any(forbidden.casefold() in lowered for forbidden in FORBIDDEN_NAMES):
                errors.append(f"包含禁止文件：{name}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            content = archive.read(info)
            text = content.decode("utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in FORBIDDEN_PATTERNS):
                errors.append(f"疑似包含敏感令牌：{info.filename}")
            if expected_version not in text and info.filename.endswith(
                ("玩家指南.txt", "version_info.txt")
            ):
                errors.append(f"版本信息不匹配：{info.filename}")

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    size = zip_path.stat().st_size
    if errors:
        return 1, "\n".join(f"- {error}" for error in errors)
    return 0, f"审计通过：{zip_path}\n大小：{size:,} bytes\nSHA-256：{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description="审计便携 ZIP 结构和敏感信息")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    code, message = audit(args.zip_path.resolve(), args.project_root.resolve())
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
