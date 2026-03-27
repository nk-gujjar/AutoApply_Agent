from __future__ import annotations

import importlib
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List

import yaml


@dataclass(frozen=True)
class AgentCatalogEntry:
    agent_id: str
    class_path: str
    display_name: str
    description: str
    skill_name: str
    skill_description: str
    tags: List[str]
    examples: List[str]
    routing_hints: List[str]
    a2a_intent: str
    allowed_payload_keys: List[str]
    default_payload: Dict[str, Any]


CATALOG_FILE_PATH = Path(__file__).resolve().parent / "config" / "agent_catalog.yaml"


def _read_catalog_file() -> Dict[str, Any]:
    if not CATALOG_FILE_PATH.exists():
        raise FileNotFoundError(f"Agent catalog file not found: {CATALOG_FILE_PATH}")

    with CATALOG_FILE_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError("Agent catalog must be a mapping at top level")
    if "agents" not in data or not isinstance(data["agents"], dict):
        raise ValueError("Agent catalog must include an 'agents' mapping")
    return data


def _validate_agent_entry(agent_id: str, raw: Dict[str, Any]) -> AgentCatalogEntry:
    required_fields = [
        "class_path",
        "display_name",
        "description",
        "skill_name",
        "skill_description",
        "tags",
        "examples",
        "routing_hints",
        "a2a_intent",
        "allowed_payload_keys",
    ]
    missing = [field for field in required_fields if field not in raw]
    if missing:
        raise ValueError(f"Agent '{agent_id}' is missing required fields: {', '.join(missing)}")

    for list_field in ["tags", "examples", "routing_hints", "allowed_payload_keys"]:
        if not isinstance(raw[list_field], list):
            raise ValueError(f"Agent '{agent_id}' field '{list_field}' must be a list")

    default_payload = raw.get("default_payload", {})
    if not isinstance(default_payload, dict):
        raise ValueError(f"Agent '{agent_id}' field 'default_payload' must be a mapping if provided")

    return AgentCatalogEntry(
        agent_id=agent_id,
        class_path=str(raw["class_path"]),
        display_name=str(raw["display_name"]),
        description=str(raw["description"]),
        skill_name=str(raw["skill_name"]),
        skill_description=str(raw["skill_description"]),
        tags=[str(item) for item in raw["tags"]],
        examples=[str(item) for item in raw["examples"]],
        routing_hints=[str(item) for item in raw["routing_hints"]],
        a2a_intent=str(raw["a2a_intent"]),
        allowed_payload_keys=[str(item) for item in raw["allowed_payload_keys"]],
        default_payload={str(k): v for k, v in default_payload.items()},
    )


def _load_catalog_entries() -> Dict[str, AgentCatalogEntry]:
    parsed = _read_catalog_file()
    raw_agents = parsed.get("agents", {})
    catalog: Dict[str, AgentCatalogEntry] = {}
    for agent_id, raw in raw_agents.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Agent '{agent_id}' must be a mapping")
        catalog[agent_id] = _validate_agent_entry(agent_id, raw)
    return catalog


AGENT_CATALOG: Dict[str, AgentCatalogEntry] = _load_catalog_entries()


def load_agent_instances() -> Dict[str, Any]:
    """Instantiate all registered agents using their class paths."""
    instances: Dict[str, Any] = {}
    for agent_id, entry in AGENT_CATALOG.items():
        module_name, class_name = entry.class_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        instances[agent_id] = cls()
    return instances


def get_agent_card_profiles() -> Dict[str, Dict[str, Any]]:
    return {
        agent_id: {
            "display_name": entry.display_name,
            "description": entry.description,
            "skill_name": entry.skill_name,
            "skill_description": entry.skill_description,
            "tags": entry.tags,
            "examples": entry.examples,
        }
        for agent_id, entry in AGENT_CATALOG.items()
    }


def get_routing_manifest() -> Dict[str, Dict[str, Any]]:
    return {
        agent_id: {
            "description": entry.description,
            "hints": entry.routing_hints,
            "examples": entry.examples,
            "a2a_intent": entry.a2a_intent,
            "allowed_payload_keys": entry.allowed_payload_keys,
            "default_payload": entry.default_payload,
        }
        for agent_id, entry in AGENT_CATALOG.items()
    }
