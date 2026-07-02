# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Shared JSONL audit-log contract for the BAF services (mcp-baf, baf-write-mcp, hermes, baf-ops-dashboard). **Stdlib-only, zero runtime dependencies (Python ≥3.11)** — consumers depend on this package, never the reverse.

## Scope is deliberately frozen

The library stays tiny: **write, format, trace, redaction, read**. Do NOT add databases, dashboards, FastAPI, OpenTelemetry, or queues here — those are separate consumers/services. This rule came from the owner explicitly and has been enforced before.

## Contract rules (don't break)

- **Schema v2** with backward compatibility: the reader must understand both v1 and v2 records; old flat event names stay valid through the alias map in `events.py` (`canonical()` maps them). Mixed v1/v2 files must not crash reading.
- `trace_id` is never null in new records; nested events inherit it.
- Secrets never reach the log; HTTP bodies are never logged in full (the `one_c.http` event carries method/endpoint/status/duration/bytes only).
- `iter_events()` in `reader.py` is the single read API — it follows rotated archives in order and silently counts (not raises on) broken lines. External projections/dashboards build on it.
- Every behavioral change gets a test; consumer test suites (baf-write-mcp) must stay green.

## Releasing

Published on PyPI as `mcp-baf-audit` via GitHub Actions **Trusted Publishing (OIDC)** — no manual token uploads. Consumers pin `mcp-baf-audit>=X.Y`; a record-format change (like schema v2) is a **minor** bump with a git tag. In local monorepo-style development consumers install it with `pip install -e ../mcp-baf-audit`.

## Owner's workflow

Branch per task, commits in logical blocks with English messages, PR title in English. README is in Ukrainian — keep it that way.
