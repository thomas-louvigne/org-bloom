import tomllib
from pathlib import Path

from .edn_config_loader import load_edn_config

CONFIG_FILENAME = "org-bloom.toml"
# Name used before the project was renamed org-bloom; still read when present.
LEGACY_CONFIG_FILENAME = "logseq-site-builder.toml"


def config_path(source_dir: Path) -> Path:
    """Return the config file to use: org-bloom.toml, else the legacy name if it exists."""
    legacy = source_dir / LEGACY_CONFIG_FILENAME
    if not (source_dir / CONFIG_FILENAME).exists() and legacy.exists():
        return legacy
    return source_dir / CONFIG_FILENAME


def read_toml_file(source_dir: Path) -> dict:
    """The config file alone, without the config.edn values."""
    toml_path = config_path(source_dir)
    if not toml_path.exists():
        return {}
    with toml_path.open("rb") as f:
        return tomllib.load(f)


def load_toml_config(source_dir: Path, *, logseq: bool = True) -> dict:
    """Load config from config.edn (base) then org-bloom.toml (overrides).

    TOML values always win over EDN-derived values. `logseq=False` leaves
    config.edn out: the project is read as plain org-mode.
    """
    merged = load_edn_config(source_dir) if logseq else {}
    toml = read_toml_file(source_dir)

    for key, value in toml.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return merged
