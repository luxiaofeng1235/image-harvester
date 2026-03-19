from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def _as_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    return float(value)


@dataclass(slots=True)
class Settings:
    project_dir: Path
    package_dir: Path
    logs_dir: Path
    exports_dir: Path
    runtime_dir: Path
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_charset: str
    db_table: str
    qwen_open_url: str
    qwen_key: str
    qwen_model_default: str
    qwen_model_deep: str
    qwen_temperature: float
    qwen_max_tokens: int
    qwen_system_prompt: str
    qwen_batch_size: int
    image_api_url: str
    image_timeout: int
    image_retry: int
    image_min_bytes: int
    image_allow_gif_as_main: bool
    title_similarity_threshold: float
    task_max_attempts_multiplier: int
    ai_tech_preset_image_file: Path
    oss_access_key_id: str
    oss_access_key_secret: str
    oss_rolearn: str
    oss_bucket: str
    oss_endpoint: str
    oss_view_domain: str
    oss_tokenexpiretime: int
    oss_policyfile: str
    oss_prefix: str

    @property
    def db_config(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
            "charset": self.db_charset,
            "cursorclass": None,
        }

    def ensure_runtime_dirs(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        missing = []
        if not self.db_host:
            missing.append("DB_HOST")
        if not self.db_user:
            missing.append("DB_USER")
        if not self.db_name:
            missing.append("DB_NAME")
        if not self.db_table:
            missing.append("DB_TABLE or TARGET_TABLE")
        if not self.qwen_open_url:
            missing.append("QW_OPEN_URL")
        if not self.qwen_key:
            missing.append("QW_KEY or QWEN_KEY")
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")


def load_settings(env_file: Path | None = None) -> Settings:
    env_path = env_file or (PROJECT_DIR / ".env")
    if env_path.exists():
        load_dotenv(env_path)

    settings = Settings(
        project_dir=PROJECT_DIR,
        package_dir=PACKAGE_DIR,
        logs_dir=PACKAGE_DIR / "logs",
        exports_dir=PACKAGE_DIR / "exports",
        runtime_dir=PACKAGE_DIR / "runtime",
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=_as_int(os.getenv("DB_PORT"), 3306),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_name=os.getenv("DB_NAME", ""),
        db_charset=os.getenv("DB_CHARSET", "utf8mb4"),
        db_table=os.getenv("DB_TABLE") or os.getenv("TARGET_TABLE", ""),
        qwen_open_url=os.getenv(
            "QW_OPEN_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        ),
        qwen_key=os.getenv("QW_KEY") or os.getenv("QWEN_KEY", ""),
        qwen_model_default=os.getenv("QW_MODEL_DEFAULT", "qwen-plus"),
        qwen_model_deep=os.getenv("QW_MODEL_DEEP", "qwen-max"),
        qwen_temperature=_as_float(os.getenv("QW_TEMPERATURE"), 0.7),
        qwen_max_tokens=_as_int(os.getenv("QW_MAX_TOKENS"), 4096),
        qwen_system_prompt=os.getenv(
            "QW_SYSTEM_PROMPT",
            "你是资深电商商品策划与文案助手，仅返回 JSON 数组。",
        ),
        qwen_batch_size=_as_int(os.getenv("QW_BATCH_SIZE"), 15),
        image_api_url=os.getenv(
            "IMAGE_API_URL",
            os.getenv("IMG_API_URL", "https://ptapi.jsss999.com/api/fetch/getImages"),
        ),
        image_timeout=_as_int(os.getenv("IMG_TIMEOUT"), 20),
        image_retry=_as_int(os.getenv("IMG_RETRY"), 3),
        image_min_bytes=_as_int(os.getenv("IMG_MIN_BYTES"), 1024),
        image_allow_gif_as_main=_as_bool(os.getenv("IMG_ALLOW_GIF_AS_MAIN"), False),
        title_similarity_threshold=_as_float(
            os.getenv("TITLE_SIMILARITY_THRESHOLD"), 0.88
        ),
        task_max_attempts_multiplier=_as_int(
            os.getenv("TASK_MAX_ATTEMPTS_MULTIPLIER"), 3
        ),
        ai_tech_preset_image_file=PROJECT_DIR
        / os.getenv("AI_TECH_PRESET_IMAGE_FILE", "AI科技商品整理.txt"),
        oss_access_key_id=os.getenv("OSS_ACCESS_KEY_ID", ""),
        oss_access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", ""),
        oss_rolearn=os.getenv("OSS_ROLEARN", ""),
        oss_bucket=os.getenv("OSS_BUCKET", ""),
        oss_endpoint=os.getenv("OSS_ENDPOINT", ""),
        oss_view_domain=os.getenv("OSS_VIEW_DOMAIN", ""),
        oss_tokenexpiretime=_as_int(os.getenv("OSS_TOKENEXPIRETIME"), 900),
        oss_policyfile=os.getenv("OSS_POLICYFILE", ""),
        oss_prefix=os.getenv("OSS_PREFIX", "goods/images/"),
    )
    settings.ensure_runtime_dirs()
    settings.validate()
    return settings
