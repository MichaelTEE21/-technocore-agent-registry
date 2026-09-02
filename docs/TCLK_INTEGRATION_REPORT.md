# tclk Integration Report

Date: 2026-09-02 (Africa/Johannesburg)
Tree: /workspace/technocore-prod
Scope: Integrate @flop-labs/tclk into Technocore Agent Registry (extend, do not rewrite).
Constraints: Never custody keys/funds. Never fake settlement. PaperRail demo only. Preimage never logged/persisted.

## Summary

- Bridge: tclk-bridge/ TypeScript CLI wrapping real package (JSON stdin/stdout)
- Models: TclkRoom, TclkTranscript, TclkContract
- Python: tar/tclk_bridge.py, tar/tclk.py, tar/tclk_api.py
- API: /tclk/* rooms, transcript, state, discover, build helpers
- UI: /ui/tclk distinguishing protocol state vs unverified settlement
- Discovery: agents listing tclk/1 or flop-htlc in protocols
- Auth: Ed25519 via existing tar.crypto / DID public_key
- Tests: tests/test_tclk.py

## Files

- tclk-bridge/package.json + bin/tclk-bridge.mjs
- src/tar/tclk_bridge.py, tclk.py, tclk_api.py
- src/tar/models.py (extended)
- src/tar/main.py (router + UI)
- src/tar/templates/tclk.html + base.html nav
- tests/test_tclk.py
- docs/TCLK_INTEGRATION_REPORT.md
part two of the report
API endpoints listed in tclk_api.py
protocol vs settlement documented in UI

## API surface

- GET /tclk/info
- GET /tclk/rooms
- GET /tclk/rooms/{id}/transcript
- POST /tclk/rooms/{id}/frames
- POST /tclk/rooms/deal/{contract_id}
- GET /tclk/contracts/{id}
- GET /tclk/state/{id}
- GET /tclk/discover
- POST /tclk/build/offer
- POST /tclk/build/accept
- POST /tclk/build/hash-lock

## Notes

protocol_status from real machine; settlement_status always separate (default unverified).
Preimages never persisted. PaperRail is demo only.
Bridge path: tclk-bridge/bin/tclk-bridge.mjs (optional TCLK_BRIDGE_PATH).
Blocker: pin portable upstream package instead of local file link when shipping.

## Test results

- test_tclk.py: 6 passed
- Full suite: 83 passed
- ruff: clean on tclk modules
- Node: v20.19.2; bridge deps via local tclk-inspect package
