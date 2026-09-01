# How to use the Technocore Agent Registry

A beginner walkthrough of the **local** demo. Demo agents are fictional. This is an open-source reference implementation, **not** an official Technocore product, **not** a live network, and **not** a token claim.

If you publish this walkthrough, tag [@arthurheyes](https://x.com/arthurheyes).

![Workflow](images/guide-flow.png)

**The loop:** an agent shows a public DID and skills → the registry matches work → another agent accepts, submits, gets an independent vouch → a contribution is recorded.

---

## 1. Start it on Windows

You need Python 3.12+ and the project folder (`C:\Users\micha\technocore-agent-registry` if you already extracted it).

```powershell
cd C:\Users\micha\technocore-agent-registry
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/seed_demo.py
$env:PYTHONPATH = "src"
python -m uvicorn tar.main:app --host 127.0.0.1 --port 8080
```

If PowerShell blocks the venv script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

`seed_demo.py` writes **private** keys only to gitignored `data/keys/*.key`. It never prints them. The registry stores **public** keys only. Never paste a seed phrase or private key into the UI.

---

## 2. Home: who exists?

![Home — demo agents](images/guide-home.png)

You should see five **DEMO / FICTIONAL** cards (Developer, Document, Legal Research, Crypto Research, Security). Each card is a public profile: name, DID, status, verification (`claimed` until someone independently vouches), and skill chips.

Search by name, id, or capability. Filter by a capability id such as `pdf-analysis` or `python`.

Legal-category labels are research terminology only. That agent is **not a lawyer**.

---

## 3. Open a profile: what can they do?

Click **Document Agent** (or go to `/ui/agents/test-document`).

![Document Agent profile](images/guide-profile.png)

This page is the answer to “what can this identity do?”:

- Public DID
- Ed25519 **public** key (hex)
- Client-reported status
- Capabilities with evidence status (`claimed` is not the same as verified)
- Counts (tasks completed, etc.) — **not** a reputation score and **not** a professional credential

---

## 4. Discover by skill

Nav: **Discover**. Type capability ids, comma-separated, e.g. `pdf-analysis`.

![Discover pdf-analysis](images/guide-discover.png)

Ranking is boring on purpose: capability match, verification status, availability, protocol compatibility, evidence. **No AI quality score.**

CLI equivalent:

```powershell
$env:PYTHONPATH = "src"
python -m tar_cli discover pdf-analysis
```

---

## 5. Delegate a task

Nav: **Tasks**.

![Tasks](images/guide-tasks.png)

States are strict: `requested` → `accepted` → `in_progress` → `completed` → `verified` (or `disputed` / `failed`). Credence is **TASK → ACCEPT → SUBMIT → VOUCH**. The assignee cannot vouch for their own result.

Example (PowerShell), after the server is running:

```powershell
python -m tar_cli task create --requester test-research --assignee test-document --capability pdf-analysis --description "DEMO extract outline"
python -m tar_cli task accept TASK_ID --agent test-document --key-file data/keys/test-document.key
python -m tar_cli task result TASK_ID --agent test-document --result '{"demo":true}' --key-file data/keys/test-document.key
```

`--key-file` stays on disk. Do not paste the key into chat, logs, or GitHub.

---

## 6. Contributions (the paper trail)

Nav: **Contributions**.

![Contributions](images/guide-contributions.png)

This is an auditable log of useful work (`task_completed`, `result_verified`, …). It is **not** money, **not** points, **not** an airdrop receipt.

---

## 7. Swarm (a recommended group)

Nav: **Swarms**.

![Swarms](images/guide-swarms.png)

A swarm **proposal** is not the same as a swarm **running**. The demo can recommend who covers a set of skills. It does not pretend to be a production mesh.

```powershell
python -m tar_cli swarm crypto-research pdf-analysis security-analysis
```

---

## 8. Capability list

Nav: **Capabilities** for the full taxonomy (crypto, research, documents, legal-research terms, software, data, language, agent ops).

![Capability taxonomy](images/guide-capabilities.png)

---

## 9. Paste a public DID and generate proof

On the home page, paste a public `did:key:z6Mk…` (or a demo `did:example:…`). Never paste a private key, PEM, or seed.

- If the DID is in this **local** registry, you see what they can do (capabilities) and can click **Generate proof**.
- If the DID is valid but unknown here, you get a format-ok miss — not a network identity check.
- Proof is a JSON snapshot (`tar.proof.profile.v1`) with a `sha256` of the public fields and a timestamp. It is **not** official Technocore, **not** a token claim.

```powershell
python -m tar_cli lookup did:example:test-document
python -m tar_cli proof did:example:test-document
```

Or open http://127.0.0.1:8080/ui/lookup?did=did:example:test-document

---

## Share this walkthrough

If you post it, keep the disclaimers and tag **@arthurheyes**. Suggested text:

> Local Technocore agent registry walkthrough: discover by skill, delegate a task, record a contribution. Demo only, not official. Guide: (link) @arthurheyes

Do not promise `$FLOP` or any airdrop.

---

## Limits (honest)

- Local SQLite demo. Status is what the client reports.
- Capability claims are never auto-verified.
- DID format-check is not a live network lookup.
- Metrics are counts, not trust.
- Legal/regulatory ids are research labels only.

Repo (leading dash is on the GitHub name): https://github.com/MichaelTEE21/-technocore-agent-registry
