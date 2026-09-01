"""Capability taxonomy stored in-process so new caps can be added without a protocol change."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Categories follow the v0.1 proposal. Capability ids are stable strings;
# adding a new id does not change the wire protocol.
#
# agent-orchestration and task-delegation are capability *ids* only.
# This registry does not implement an orchestration or messaging protocol.

TAXONOMY: dict[str, dict[str, Any]] = {
    "crypto-web3": {
        "id": "crypto-web3",
        "name": "Crypto / Web3",
        "description": "Public-chain research, taxonomy, and read-only on-chain inspection. Never holds private keys or seeds.",
        "capabilities": [
            {
                "id": "crypto-research",
                "name": "Crypto research",
                "description": "Market, protocol, and ecosystem research from public sources.",
            },
            {
                "id": "onchain-read",
                "name": "On-chain read",
                "description": "Read public chain state. No signing, no key custody.",
            },
            {
                "id": "token-taxonomy",
                "name": "Token taxonomy",
                "description": "Classify tokens and protocols from public metadata.",
            },
            {
                "id": "defi-research",
                "name": "DeFi research",
                "description": "Describe DeFi mechanisms from public documentation.",
            },
            {
                "id": "wallet-analysis",
                "name": "Wallet analysis",
                "description": "Analyze public addresses only. Never request or store keys.",
            },
        ],
    },
    "research": {
        "id": "research",
        "name": "Research",
        "description": "Open-web and literature research with source attribution.",
        "capabilities": [
            {
                "id": "web-research",
                "name": "Web research",
                "description": "Gather and summarize publicly available information.",
            },
            {
                "id": "source-verification",
                "name": "Source verification",
                "description": "Check claims against cited public sources.",
            },
            {
                "id": "literature-review",
                "name": "Literature review",
                "description": "Survey papers and long-form public documents.",
            },
            {
                "id": "fact-checking",
                "name": "Fact checking",
                "description": "Compare statements to cited evidence.",
            },
        ],
    },
    "documents": {
        "id": "documents",
        "name": "Documents",
        "description": "Parse, extract, and summarize documents supplied by the caller.",
        "capabilities": [
            {
                "id": "pdf-analysis",
                "name": "PDF analysis",
                "description": "Structure and inspect PDF content.",
            },
            {
                "id": "document-extraction",
                "name": "Document extraction",
                "description": "Pull fields, tables, and entities from documents.",
            },
            {
                "id": "summarization",
                "name": "Summarization",
                "description": "Produce shorter restatements of provided text.",
            },
            {
                "id": "ocr",
                "name": "OCR",
                "description": "Optical character recognition on supplied images or scans.",
            },
        ],
    },
    "legal": {
        "id": "legal",
        "name": "Legal",
        "description": "Legal *research assistance* only. Not legal advice. See the disclaimer in docs/capabilities.md.",
        "disclaimer": (
            "Capabilities in the legal category are research and drafting aids. "
            "They are not a lawyer, they do not form an attorney-client relationship, "
            "and their output is not legal advice. A qualified professional in the "
            "relevant jurisdiction must review any matter that has legal consequences."
        ),
        "capabilities": [
            {
                "id": "legal-research",
                "name": "Legal research",
                "description": "Find publicly available statutes, cases, and commentary. Not legal advice.",
            },
            {
                "id": "contract-review",
                "name": "Contract review",
                "description": "Highlight clauses in a supplied draft. Not a legal opinion.",
            },
            {
                "id": "compliance-check",
                "name": "Compliance check",
                "description": "Map a description to publicly documented policy checklists. Not a determination.",
            },
        ],
    },
    "software": {
        "id": "software",
        "name": "Software",
        "description": "Code, APIs, tests, and developer tooling.",
        "capabilities": [
            {
                "id": "python",
                "name": "Python",
                "description": "Write, review, and explain Python.",
            },
            {
                "id": "api-development",
                "name": "API development",
                "description": "Design and implement HTTP APIs.",
            },
            {
                "id": "testing",
                "name": "Testing",
                "description": "Unit, integration, and regression tests.",
            },
            {
                "id": "code-review",
                "name": "Code review",
                "description": "Review diffs for defects and style.",
            },
            {
                "id": "debugging",
                "name": "Debugging",
                "description": "Isolate failures from logs and reproductions.",
            },
        ],
    },
    "data": {
        "id": "data",
        "name": "Data",
        "description": "Analyze, clean, and present structured data.",
        "capabilities": [
            {
                "id": "data-analysis",
                "name": "Data analysis",
                "description": "Describe patterns in supplied datasets.",
            },
            {
                "id": "etl",
                "name": "ETL",
                "description": "Extract, transform, and load pipelines.",
            },
            {
                "id": "visualization",
                "name": "Visualization",
                "description": "Charts and summaries of supplied data.",
            },
            {
                "id": "data-cleaning",
                "name": "Data cleaning",
                "description": "Normalize and repair messy tables.",
            },
        ],
    },
    "language": {
        "id": "language",
        "name": "Language",
        "description": "Translation, writing, and localization.",
        "capabilities": [
            {
                "id": "translation",
                "name": "Translation",
                "description": "Translate text between languages.",
            },
            {
                "id": "writing",
                "name": "Writing",
                "description": "Draft prose to a brief.",
            },
            {
                "id": "copy-editing",
                "name": "Copy editing",
                "description": "Edit for clarity, grammar, and consistency.",
            },
            {
                "id": "localization",
                "name": "Localization",
                "description": "Adapt copy for a locale.",
            },
        ],
    },
    "agent-ops": {
        "id": "agent-ops",
        "name": "Agent operations",
        "description": (
            "How agents describe operational roles in a swarm. "
            "agent-orchestration and task-delegation are capability identifiers only; "
            "this registry does not run a messaging or delegation protocol (FUTURE)."
        ),
        "capabilities": [
            {
                "id": "agent-orchestration",
                "name": "Agent orchestration",
                "description": "Claimed ability to coordinate other agents. Protocol is FUTURE — not implemented here.",
            },
            {
                "id": "task-delegation",
                "name": "Task delegation",
                "description": "Claimed ability to split and assign work. Protocol is FUTURE — not implemented here.",
            },
            {
                "id": "swarm-coordination",
                "name": "Swarm coordination",
                "description": "Claimed ability to keep a named swarm coherent. Not a runtime.",
            },
            {
                "id": "capability-discovery",
                "name": "Capability discovery",
                "description": "Find agents by advertised capability — this registry's own job.",
            },
            {
                "id": "heartbeat",
                "name": "Heartbeat",
                "description": "Client-reported liveness signals. This registry does not probe hosts.",
            },
        ],
    },
}

LEVELS = ("beginner", "intermediate", "advanced", "expert")


def all_categories() -> list[dict[str, Any]]:
    return [deepcopy(c) for c in TAXONOMY.values()]


def get_category(category_id: str) -> dict[str, Any] | None:
    cat = TAXONOMY.get(category_id)
    return deepcopy(cat) if cat else None


def _index() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cat in TAXONOMY.values():
        for cap in cat["capabilities"]:
            item = dict(cap)
            item["category"] = cat["id"]
            item["category_name"] = cat["name"]
            if "disclaimer" in cat:
                item["disclaimer"] = cat["disclaimer"]
            out[cap["id"]] = item
    return out


CAPABILITY_INDEX = _index()


def get_capability(capability_id: str) -> dict[str, Any] | None:
    item = CAPABILITY_INDEX.get(capability_id)
    return deepcopy(item) if item else None


def list_capabilities(category: str | None = None) -> list[dict[str, Any]]:
    if category:
        cat = TAXONOMY.get(category)
        if not cat:
            return []
        return [get_capability(c["id"]) for c in cat["capabilities"]]  # type: ignore[misc]
    return [deepcopy(v) for v in CAPABILITY_INDEX.values()]


def known_capability_ids() -> set[str]:
    return set(CAPABILITY_INDEX)


def known_category_ids() -> set[str]:
    return set(TAXONOMY)
