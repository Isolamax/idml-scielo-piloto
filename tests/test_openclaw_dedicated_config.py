import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "openclaw-idml-dedicated.json"
COMPOSE_PATH = ROOT / "deploy" / "docker-compose.dev.yml"


def test_dedicated_openclaw_config_has_a_single_inert_agent() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["meta"]["lastTouchedVersion"] == "2026.6.11"
    assert config["env"]["shellEnv"]["enabled"] is False
    assert config["plugins"]["enabled"] is False
    assert config["skills"]["allowBundled"] == []

    agents = config["agents"]["list"]
    assert [agent["id"] for agent in agents] == ["idml-evaluator"]
    assert agents[0]["model"] == {
        "primary": "openai/gpt-5.4-mini",
        "fallbacks": [],
    }
    assert agents[0]["tools"]["allow"] == []
    assert agents[0]["tools"]["deny"] == ["*"]
    assert agents[0]["skills"] == []
    assert config["agents"]["defaults"]["heartbeat"]["every"] == "0m"
    assert agents[0]["heartbeat"]["every"] == "0m"
    heartbeat = (ROOT / "openclaw" / "idml-evaluator-workspace" / "HEARTBEAT.md").read_text(
        encoding="utf-8"
    )
    assert heartbeat.strip() == "# Heartbeat disabled"


def test_dedicated_openclaw_exposes_only_the_required_http_endpoint() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    gateway = config["gateway"]
    endpoints = gateway["http"]["endpoints"]

    assert gateway["mode"] == "local"
    assert gateway["bind"] == "lan"
    assert gateway["controlUi"]["enabled"] is False
    assert endpoints["responses"]["enabled"] is True
    assert endpoints["responses"]["maxUrlParts"] == 0
    assert endpoints["responses"]["files"]["allowUrl"] is False
    assert endpoints["responses"]["images"]["allowUrl"] is False
    assert endpoints["chatCompletions"]["enabled"] is False
    assert gateway["auth"]["mode"] == "token"
    assert "token" not in gateway["auth"]
    assert "secrets" not in config


def test_dedicated_openclaw_compose_is_private_and_has_no_provider_key() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    service = compose.split("  openclaw-idml:\n", maxsplit=1)[1].split(
        "\n  api:\n", maxsplit=1
    )[0]

    assert "ghcr.io/openclaw/openclaw@sha256:" in service
    assert "OPENCLAW_GATEWAY_TOKEN:" in service
    assert "OPENAI_API_KEY" not in service
    assert "ports:" not in service
    assert "read_only: true" in service
    assert "cap_drop:" in service
    assert "- idml_openclaw" in service
    assert "internal: true" in compose.split("  idml_openclaw:\n", maxsplit=1)[1]
