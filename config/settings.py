import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# tomllib is stdlib in Python 3.11+
if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = None


@dataclass
class ModelConfig:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.3
    max_tokens: int = 65536
    context_limit: int = 0  # 0 = auto-detect from overflow.py MODEL_CONTEXT_LIMITS


@dataclass
class PatchConfig:
    similarity_threshold: float = 0.85
    max_search_files: int = 5
    max_context_lines: int = 100
    enable_fuzzy: bool = True
    enable_ast: bool = False


@dataclass
class SecurityConfig:
    require_approval: bool = True
    auto_approve_read: bool = True
    auto_approve_build_once: bool = True
    max_auto_approve: int = 3
    blocked_commands: list[str] = field(default_factory=lambda: [
        "rm -rf", "del /f", "format",
        "> /dev/sda", "dd if=",
        "shutdown", "reboot",
    ])


@dataclass
class CodeGraphConfig:
    enabled: bool = True
    auto_init: bool = True
    auto_index: bool = True
    fallback_to_builtin: bool = True
    timeout_seconds: int = 60
    index_timeout_seconds: int = 300
    max_symbols_context: int = 15
    codegraph_path: str = ""


@dataclass
class AppConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    patch: PatchConfig = field(default_factory=PatchConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    codegraph: CodeGraphConfig = field(default_factory=CodeGraphConfig)
    project_root: str = "."


def get_api_base_url(provider: str) -> str:
    urls = {
        "deepseek": "https://api.deepseek.com",
        "openai": "https://api.openai.com/v1",
        "claude": "https://api.anthropic.com",
        "anthropic": "https://api.anthropic.com",
        "gemini": "https://generativelanguage.googleapis.com",
        "openrouter": "https://openrouter.ai/api/v1",
        "9router": "http://localhost:20128/v1",
    }
    return urls.get(provider, urls["deepseek"])


_PROVIDER_PACKAGE_MAP = {
    "deepseek": "openai",
    "openai": "openai",
    "openrouter": "openai",
    "9router": "openai",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "gemini": "google.generativeai",
}

_PROVIDER_PIP_MAP = {
    "deepseek": "openai",
    "openai": "openai",
    "openrouter": "openai",
    "9router": "openai",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "gemini": "google-generativeai",
}


def get_provider_package(provider: str) -> str | None:
    return _PROVIDER_PACKAGE_MAP.get(provider)


def get_provider_pip_package(provider: str) -> str | None:
    return _PROVIDER_PIP_MAP.get(provider)


def _check_package_available(pkg_name: str) -> bool:
    try:
        __import__(pkg_name)
        return True
    except ImportError:
        return False


def get_available_providers() -> list[str]:
    available = []
    seen = set()
    for provider, pkg in _PROVIDER_PACKAGE_MAP.items():
        if _check_package_available(pkg):
            canonical = "anthropic" if provider == "claude" else provider
            if canonical not in seen:
                seen.add(canonical)
                available.append(canonical)
    return available


def get_default_provider() -> str:
    available = get_available_providers()
    if "deepseek" in available:
        return "deepseek"
    if "openai" in available:
        return "openai"
    return available[0] if available else "deepseek"


def ensure_viable_provider(provider: str) -> str:
    available = get_available_providers()
    if provider in available:
        return provider
    return get_default_provider()


def _parse_kv_file(path: Path, key_map: dict[str, str], override: bool = False) -> bool:
    """Parse a key=value config file and set env vars. Returns True if any value was loaded."""
    loaded = False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("["):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    env_key = key_map.get(k)
                    if env_key and v:
                        if override:
                            os.environ[env_key] = v
                        else:
                            os.environ.setdefault(env_key, v)
                        loaded = True
    except OSError:
        pass
    return loaded


def _load_toml(path: Path) -> dict | None:
    """Parse a TOML file with tomllib (Python 3.11+). Returns None if unavailable or invalid."""
    if tomllib is None:
        return None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def _apply_toml_to_config(config: AppConfig, data: dict) -> None:
    """Populate AppConfig fields from a parsed TOML dict."""
    # Support both [model] section and flat key=value format (backward compat)
    m = data["model"] if "model" in data else data
    config.model.provider = str(m.get("provider", config.model.provider))
    config.model.model = str(m.get("model") or m.get("default_text_model") or config.model.model)
    config.model.api_key = str(m.get("api_key", config.model.api_key))
    config.model.base_url = str(m.get("base_url", config.model.base_url))
    config.model.temperature = float(m.get("temperature", config.model.temperature))
    config.model.max_tokens = int(m.get("max_tokens", config.model.max_tokens))
    config.model.context_limit = int(m.get("context_limit", config.model.context_limit))
    if "patch" in data:
        p = data["patch"]
        config.patch.similarity_threshold = float(p.get("similarity_threshold", config.patch.similarity_threshold))
        config.patch.max_search_files = int(p.get("max_search_files", config.patch.max_search_files))
        config.patch.max_context_lines = int(p.get("max_context_lines", config.patch.max_context_lines))
        config.patch.enable_fuzzy = bool(p.get("enable_fuzzy", config.patch.enable_fuzzy))
        config.patch.enable_ast = bool(p.get("enable_ast", config.patch.enable_ast))
    if "security" in data:
        s = data["security"]
        config.security.require_approval = bool(s.get("require_approval", config.security.require_approval))
        config.security.auto_approve_read = bool(s.get("auto_approve_read", config.security.auto_approve_read))
        config.security.auto_approve_build_once = bool(s.get("auto_approve_build_once", config.security.auto_approve_build_once))
        config.security.max_auto_approve = int(s.get("max_auto_approve", config.security.max_auto_approve))
        if "blocked_commands" in s:
            config.security.blocked_commands = list(s["blocked_commands"])
    if "codegraph" in data:
        cg = data["codegraph"]
        config.codegraph.enabled = bool(cg.get("enabled", config.codegraph.enabled))
        config.codegraph.auto_init = bool(cg.get("auto_init", config.codegraph.auto_init))
        config.codegraph.auto_index = bool(cg.get("auto_index", config.codegraph.auto_index))
        config.codegraph.fallback_to_builtin = bool(cg.get("fallback_to_builtin", config.codegraph.fallback_to_builtin))
        config.codegraph.timeout_seconds = int(cg.get("timeout_seconds", config.codegraph.timeout_seconds))
        config.codegraph.index_timeout_seconds = int(cg.get("index_timeout_seconds", config.codegraph.index_timeout_seconds))
        config.codegraph.max_symbols_context = int(cg.get("max_symbols_context", config.codegraph.max_symbols_context))
        config.codegraph.codegraph_path = str(cg.get("codegraph_path", config.codegraph.codegraph_path))


_ORCA_KEY_MAP = {
    "api_key": "ORCA_API_KEY",
    "provider": "ORCA_PROVIDER",
    "default_text_model": "ORCA_MODEL",
    "base_url": "ORCA_BASE_URL",
}


def load_config(config_path: str | None = ".env") -> AppConfig:
    # 1. Load project-level .env if it exists (without override — let config.toml win)
    if config_path:
        try:
            from dotenv import load_dotenv
            p = Path(config_path)
            if p.exists():
                load_dotenv(dotenv_path=p, override=False)
        except ImportError:
            pass

    config = AppConfig()
    _app_root = Path(__file__).resolve().parent.parent

    # 2. Try proper TOML parsing (Python 3.11+ with tomllib)
    # priority: home-level (canonical storage) > install-level (legacy)
    toml_data = None
    home_toml = Path.home() / ".orcacode" / "config.toml"
    if home_toml.exists():
        toml_data = _load_toml(home_toml)

    if toml_data is None:
        app_toml = _app_root / ".orcacode" / "config.toml"
        if app_toml.exists():
            toml_data = _load_toml(app_toml)

    if toml_data is not None:
        _apply_toml_to_config(config, toml_data)
    else:
        # 3. Legacy: parse config.toml (or flat files) as key=value
        _loaded = False
        home_toml = Path.home() / ".orcacode" / "config.toml"
        if home_toml.exists():
            _loaded = _parse_kv_file(home_toml, _ORCA_KEY_MAP, override=True)

        if not _loaded:
            if app_toml.exists():
                _loaded = _parse_kv_file(app_toml, _ORCA_KEY_MAP)

        # Legacy: ~/.orcacode as a flat dotenv file
        if not _loaded:
            legacy_file = Path.home() / ".orcacode"
            if legacy_file.is_file():
                _loaded = _parse_kv_file(legacy_file, _ORCA_KEY_MAP)

        # Legacy: ~/.orca/api_key + ~/.orca/provider
        if not _loaded or not os.getenv("ORCA_API_KEY"):
            orca_dir = Path.home() / ".orca"
            if orca_dir.is_dir():
                legacy_map = {"api_key": "ORCA_API_KEY", "model": "ORCA_MODEL"}
                api_file = orca_dir / "api_key"
                if api_file.exists():
                    _parse_kv_file(api_file, legacy_map)
                provider_file = orca_dir / "provider"
                if provider_file.exists():
                    _parse_kv_file(provider_file, {"provider": "ORCA_PROVIDER"})

        config.model.provider = os.getenv("ORCA_PROVIDER", "deepseek")
        config.model.model = os.getenv("ORCA_MODEL", "deepseek-chat")
    config.model.max_tokens = int(os.getenv("ORCA_MAX_TOKENS", "8192"))
    config.model.temperature = float(os.getenv("ORCA_TEMPERATURE", "0.3"))
    config.model.base_url = os.getenv("ORCA_BASE_URL", "")
    config.model.context_limit = int(os.getenv("ORCA_CONTEXT_LIMIT", "0"))

    # 4. Env vars always override (highest priority)
    config.model.provider = os.getenv("ORCA_PROVIDER", config.model.provider)
    config.model.model = os.getenv("ORCA_MODEL", config.model.model)
    config.model.max_tokens = int(os.getenv("ORCA_MAX_TOKENS", str(config.model.max_tokens)))
    config.model.temperature = float(os.getenv("ORCA_TEMPERATURE", str(config.model.temperature)))
    config.model.base_url = os.getenv("ORCA_BASE_URL", config.model.base_url)
    config.model.context_limit = int(os.getenv("ORCA_CONTEXT_LIMIT", str(config.model.context_limit)))

    # 5. API key fallback chain
    api_key = os.getenv("ORCA_API_KEY", config.model.api_key)
    if not api_key:
        provider_env_vars = {
            "deepseek": "DEEPSEEK_API_KEY",
            "openai": "OPENAI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "9router": "9ROUTER_API_KEY",
        }
        fallback_var = provider_env_vars.get(config.model.provider.lower().strip())
        if fallback_var:
            api_key = os.getenv(fallback_var, "")
    config.model.api_key = api_key

    # 6. Normalize "claude" → "anthropic" everywhere internally
    if config.model.provider.lower().strip() in ("claude", "anthropic"):
        config.model.provider = "anthropic"
    config.project_root = os.path.abspath(os.getenv("ORCA_PROJECT_ROOT", config.project_root))
    return config
