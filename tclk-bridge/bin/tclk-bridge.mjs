#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// Thin JSON CLI over @flop-labs/tclk. Does NOT reimplement the state machine.
// Never custodies keys or funds. PaperRail is demo-only (settles nothing of value).
// Preimages/secrets are returned only in-memory to the caller; never written to disk by this CLI.

import { createInterface } from "node:readline";
import {
  makeOffer,
  makeAccept,
  generateHashLock,
  hashLockFromPreimage,
  openContract,
  applyFrame,
  encodeFrame,
  decodeFrame,
  tryDecodeFrame,
  isTclkLine,
  verifyHashPreimage,
  verifySecret,
  validateFrame,
  validateDeadlines,
  dealRoom,
  capabilityToken,
  parseCapabilityToken,
  OFFER_ROOM,
  TCLK_VERSION,
  TCLK_PREFIX,
  TCLK_TERMINAL_STATUSES,
  lockTerms,
  PaperRail,
  MemoryNoteStore,
  MemoryRail,
  stateNote,
  stateNoteValue,
  parseStateNoteValue,
  tclkStatusToA2A,
} from "@flop-labs/tclk";

/** In-process paper note store for demo paper_* commands only. */
const paperNotes = new MemoryNoteStore();
const paperRail = new PaperRail(paperNotes);
const memoryRail = new MemoryRail("memory-demo");

function ok(result) {
  return { ok: true, result };
}

function fail(error, code = "error") {
  return { ok: false, error: String(error), code };
}

/** Strip secret from contract state before returning durable views. */
function publicState(state) {
  if (!state || typeof state !== "object") return state;
  const { secret: _secret, ...rest } = state;
  return rest;
}

/** Redact secret from reveal frames for transcript persistence. */
function redactFrame(frame) {
  if (!frame || typeof frame !== "object") return frame;
  if (frame.type === "reveal" && "secret" in frame) {
    const { secret: _s, ...rest } = frame;
    return { ...rest, secret: "[REDACTED]" };
  }
  return frame;
}

async function dispatch(cmd) {
  const action = cmd?.action;
  if (!action) throw new Error("missing action");

  switch (action) {
    case "ping":
      return ok({
        version: TCLK_VERSION,
        prefix: TCLK_PREFIX,
        offerRoom: OFFER_ROOM,
        note: "bridge wraps @flop-labs/tclk; PaperRail settles nothing of value",
      });

    case "makeOffer":
      return ok(makeOffer(cmd.fields));

    case "makeAccept":
      return ok(makeAccept(cmd.offer, cmd.accept));

    case "generateHashLock": {
      // Caller must hold preimage; bridge does not persist it.
      const lock = generateHashLock();
      return ok({
        hash: lock.hash,
        preimage: lock.preimage,
        warning: "preimage is ephemeral — never log or persist server-side",
      });
    }

    case "hashLockFromPreimage":
      return ok(hashLockFromPreimage(cmd.preimage));

    case "openContract":
      return ok(publicState(openContract(cmd.offer)));

    case "applyFrame": {
      const nowMs = typeof cmd.nowMs === "number" ? cmd.nowMs : Date.now();
      const step = applyFrame(cmd.state, cmd.frame, nowMs);
      return ok({
        ...step,
        state: publicState(step.state),
        // Do not echo revealed secret back into durable state.
        revealed: cmd.frame?.type === "reveal" ? Boolean(cmd.frame?.secret) : false,
      });
    }

    case "foldTranscript": {
      // Fold offer + frames through the real machine. Secrets in reveal frames
      // are used for verification then dropped from returned state.
      const nowMs = typeof cmd.nowMs === "number" ? cmd.nowMs : Date.now();
      let state = openContract(cmd.offer);
      const steps = [];
      for (const frame of cmd.frames || []) {
        const step = applyFrame(state, frame, nowMs);
        state = step.state;
        steps.push({
          ok: step.ok,
          reason: step.reason,
          status: state.status,
          frameType: frame?.type,
        });
        if (!step.ok && cmd.stopOnReject) break;
      }
      return ok({ state: publicState(state), steps, terminal: TCLK_TERMINAL_STATUSES.has(state.status) });
    }

    case "encodeFrame":
      return ok({ line: encodeFrame(cmd.frame) });

    case "decodeFrame":
      return ok(redactFrame(decodeFrame(cmd.text)));

    case "tryDecodeFrame": {
      const frame = tryDecodeFrame(cmd.text);
      return ok(frame ? redactFrame(frame) : null);
    }

    case "isTclkLine":
      return ok({ isTclk: isTclkLine(cmd.text) });

    case "validateFrame":
      return ok(redactFrame(validateFrame(cmd.value)));

    case "verifyHashPreimage":
      return ok({ valid: verifyHashPreimage(cmd.hash, cmd.preimage) });

    case "verifySecret":
      return ok({
        valid: verifySecret(cmd.lock, cmd.statement, cmd.secret),
      });

    case "validateDeadlines":
      return ok({
        valid: validateDeadlines(
          cmd.offer,
          cmd.nowMs ?? Date.now(),
          cmd.minClaimWindowMs,
          cmd.minRefundGapMs,
        ),
      });

    case "dealRoom":
      return ok({ room: dealRoom(cmd.contract) });

    case "capabilityToken":
      return ok({ token: capabilityToken(cmd.rails || []) });

    case "parseCapabilityToken":
      return ok({ rails: parseCapabilityToken(cmd.note) });

    case "stateNote":
      return ok(stateNote(cmd.contract));

    case "stateNoteValue":
      return ok({ value: stateNoteValue(cmd.status, cmd.railRef) });

    case "parseStateNoteValue":
      return ok(parseStateNoteValue(cmd.value));

    case "lockTerms":
      return ok(lockTerms(cmd.state));

    case "tclkStatusToA2A":
      return ok({ a2a: tclkStatusToA2A(cmd.status) });

    // --- PaperRail demo (settles NOTHING of value) ---
    case "paperLock": {
      const ref = await paperRail.lock(cmd.terms);
      return ok({
        ref,
        rail: "paper",
        settlement: "unverified",
        warning: "PaperRail records lifecycle only — no funds held",
      });
    }

    case "paperVerifyLock":
      return ok({
        verified: await paperRail.verifyLock(cmd.terms, cmd.ref),
        settlement: "paper-demo",
        warning: "Paper verification is not economic settlement",
      });

    case "paperClaim": {
      await paperRail.claim(cmd.ref, cmd.secret);
      return ok({
        claimed: true,
        settlement: "unverified",
        warning: "PaperRail claim is choreography only",
      });
    }

    case "paperRefund": {
      await paperRail.refund(cmd.ref);
      return ok({
        refunded: true,
        settlement: "unverified",
        warning: "PaperRail refund is choreography only",
      });
    }

    case "paperRead": {
      const record = await paperRail.read(cmd.ref);
      // Strip secret from paper record before returning for persistence paths.
      if (record && record.secret) {
        const { secret: _s, ...rest } = record;
        return ok({
          record: { ...rest, secret: "[REDACTED]" },
          settlement: "unverified",
        });
      }
      return ok({ record, settlement: "unverified" });
    }

    case "memoryLock": {
      const ref = await memoryRail.lock(cmd.terms);
      return ok({
        ref,
        rail: "memory-demo",
        settlement: "unverified",
        warning: "MemoryRail is in-process demo only — no funds",
      });
    }

    default:
      throw new Error(`unknown action: ${action}`);
  }
}

async function main() {
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  let buf = "";
  for await (const line of rl) {
    buf += line;
  }
  buf = buf.trim();
  if (!buf) {
    process.stdout.write(JSON.stringify(fail("empty stdin", "bad_request")) + "\n");
    process.exit(2);
  }
  let cmd;
  try {
    cmd = JSON.parse(buf);
  } catch (e) {
    process.stdout.write(JSON.stringify(fail(`invalid JSON: ${e.message}`, "bad_request")) + "\n");
    process.exit(2);
  }
  try {
    const out = await dispatch(cmd);
    process.stdout.write(JSON.stringify(out) + "\n");
    process.exit(out.ok ? 0 : 1);
  } catch (e) {
    process.stdout.write(JSON.stringify(fail(e.message || e)) + "\n");
    process.exit(1);
  }
}

main();
