from tar.taxonomy import add_capability, known_capability_ids, known_category_ids, list_capabilities

REQUIRED = {
    "crypto-research", "blockchain-research", "defi-analysis", "dex-analysis",
    "tokenomics-analysis", "governance-analysis", "onchain-analysis", "wallet-analysis",
    "protocol-analysis", "smart-contract-analysis",
    "web-research", "technical-research", "academic-research", "competitive-analysis",
    "fact-checking", "source-verification",
    "pdf-analysis", "document-analysis", "document-extraction", "ocr", "summarization",
    "document-comparison", "data-extraction", "report-generation",
    "legal-research", "legal-document-analysis", "contract-analysis", "regulatory-research",
    "compliance-research", "privacy-research", "intellectual-property-research",
    "python", "javascript", "typescript", "api-development", "database-development",
    "testing", "devops", "github", "smart-contract-development", "security-analysis",
    "data-analysis", "statistics", "visualization", "data-cleaning", "etl",
    "market-data-analysis", "blockchain-data-analysis",
    "translation", "transcription", "localization", "multilingual-communication",
    "agent-discovery", "agent-orchestration", "task-delegation", "agent-verification",
    "monitoring", "automation",
}


def test_required_capability_ids_present():
    ids = known_capability_ids()
    missing = REQUIRED - ids
    assert not missing
    assert "crypto-web3" in known_category_ids()
    assert "legal" in known_category_ids()
    legal = [c for c in list_capabilities("legal") if c]
    assert all(c.get("disclaimer") for c in legal)


def test_safe_add_capability():
    added = add_capability(
        "research",
        {"id": "safe-add-demo", "name": "Safe add demo", "description": "Test-only id"},
        persist=False,
    )
    assert added["id"] == "safe-add-demo"
    assert "safe-add-demo" in known_capability_ids()
