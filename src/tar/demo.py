"""Fictional demo agent profiles. Not real operators. DIDs are did:example:test-* only."""

from __future__ import annotations

DEMO_NOTE = (
    "FICTIONAL demo agent for the Technocore Agent Registry. "
    "Not a real service, not a live network identity, not a professional credential."
)

LEGAL_NOTE = (
    " Legal/regulatory research terminology only — not a substitute for a qualified "
    "legal professional. This agent is not a lawyer."
)

AGENTS = [
    {
        "id": "test-research",
        "name": "Crypto Research Agent",
        "did": "did:example:test-research",
        "version": "1.0.0",
        "description": f"{DEMO_NOTE} Advertises crypto-research, blockchain-research, source-verification.",
        "status": "online",
        "endpoint": "https://example.invalid/agents/research",
        "protocols": ["http"],
        "capabilities": [
            {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"},
            {"id": "blockchain-research", "category": "crypto-web3", "level": "advanced"},
            {"id": "source-verification", "category": "research", "level": "intermediate"},
        ],
    },
    {
        "id": "test-legal",
        "name": "Legal Research Agent",
        "did": "did:example:test-legal",
        "version": "1.0.0",
        "description": f"{DEMO_NOTE} Advertises legal-research, regulatory-research, legal-document-analysis.{LEGAL_NOTE}",
        "status": "online",
        "endpoint": "https://example.invalid/agents/legal",
        "protocols": ["http"],
        "capabilities": [
            {"id": "legal-research", "category": "legal", "level": "advanced"},
            {"id": "regulatory-research", "category": "legal", "level": "intermediate"},
            {"id": "legal-document-analysis", "category": "legal", "level": "intermediate"},
        ],
    },
    {
        "id": "test-document",
        "name": "Document Agent",
        "did": "did:example:test-document",
        "version": "1.0.0",
        "description": f"{DEMO_NOTE} Advertises pdf-analysis, document-extraction, summarization.",
        "status": "online",
        "endpoint": "https://example.invalid/agents/document",
        "protocols": ["http"],
        "capabilities": [
            {"id": "pdf-analysis", "category": "documents", "level": "advanced"},
            {"id": "document-extraction", "category": "documents", "level": "advanced"},
            {"id": "summarization", "category": "documents", "level": "intermediate"},
        ],
    },
    {
        "id": "test-developer",
        "name": "Developer Agent",
        "did": "did:example:test-developer",
        "version": "1.0.0",
        "description": f"{DEMO_NOTE} Advertises python, api-development, testing.",
        "status": "unknown",
        "endpoint": "https://example.invalid/agents/developer",
        "protocols": ["http"],
        "capabilities": [
            {"id": "python", "category": "software", "level": "advanced"},
            {"id": "api-development", "category": "software", "level": "advanced"},
            {"id": "testing", "category": "software", "level": "intermediate"},
        ],
    },
    {
        "id": "test-security",
        "name": "Security Agent",
        "did": "did:example:test-security",
        "version": "1.0.0",
        "description": f"{DEMO_NOTE} Advertises security-analysis, smart-contract-analysis. Not an audit certificate.",
        "status": "online",
        "endpoint": "https://example.invalid/agents/security",
        "protocols": ["http"],
        "capabilities": [
            {"id": "security-analysis", "category": "software", "level": "advanced"},
            {"id": "smart-contract-analysis", "category": "crypto-web3", "level": "advanced"},
        ],
    },
]
