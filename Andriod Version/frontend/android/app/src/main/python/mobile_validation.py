from pathlib import Path


def probe(files_dir: str) -> str:
    """Return a deterministic message proving Python can use Android app storage."""
    app_data_dir = Path(files_dir)
    return f"Python bridge ready: {app_data_dir.name}"
