import json
from pathlib import Path

from pydantic import Field

from idml_foundation.domain.common import StrictModel


class JournalProfile(StrictModel):
    profile_id: str
    profile_version: str
    journal_title: str
    journal_abbreviated_title: str
    journal_issn: str
    primary_language: str = Field(pattern=r"^[a-z]{2,3}$")
    secondary_language: str = Field(pattern=r"^[a-z]{2,3}$")
    article_category: str
    style_roles: dict[str, str]

    def role_for_prefix(self, prefix: str | None) -> str | None:
        if prefix is None:
            return None
        return self.style_roles.get(prefix) or self.style_roles.get(prefix.split(".", 1)[0])


def default_profile_path() -> Path:
    return Path(__file__).resolve().parents[3] / "profiles" / "esa-aop-1.0.json"


def load_profile(path: Path | None = None) -> JournalProfile:
    profile_path = path or default_profile_path()
    return JournalProfile.model_validate(json.loads(profile_path.read_text(encoding="utf-8")))
