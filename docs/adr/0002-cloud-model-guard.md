# ADR 0002: Cloud model access is guarded, not merely discouraged

- Status: Accepted
- Date: 2026-09-08
- Epic: #21, #22

## Context

Architectural rule 10 states that no cloud LLM is ever called with real data.
Ollama is reachable on localhost or the internal Docker network only, and intel data never leaves the deployment boundary.

Development pulls the other way.
Iterating on a prompt against a local 7B model on CPU is slow, and comparing a local model against a stronger cloud model is the only way to know whether the local model is good enough to ship.
Issue #34 requires exactly that comparison: the local mobilization confirmation model is measured against a cloud model on the same labelled test set.

A rule enforced by discipline alone fails silently.
A developer sets an environment variable, forgets it, and a deployment inherits it.

## Decision

Cloud provider access is a settings value, off by default, and refused outright in a production environment.

1. Provider selection routes through the existing model abstraction.
   No provider name appears in service code.
   Swapping local for cloud is configuration, never a code change.
2. `LLM_CLOUD_ENABLED` defaults to `false`.
   Nothing reaches a cloud provider unless it is explicitly set.
3. `ENVIRONMENT=production` combined with `LLM_CLOUD_ENABLED=true` is a hard refusal at startup.
   The process raises rather than warns.
   A misconfiguration stops a deployment; it never degrades into a silent data leak.
4. Every cloud call emits a structured log line carrying a SHA-256 hash of its payload.
   The hash proves what was sent without recording the content.
5. When the flag is off, that fact is logged at INFO at startup with the reason.
   Per the silent failure prevention rules, a disabled feature explains itself.

## Consequences

Cloud inference is available on a developer machine and impossible in production.
The refusal is structural rather than procedural, so it survives a forgotten environment variable.

Benchmark runs that compare local against cloud are development-environment work by construction.
The labelled test set for #34 is drawn from public reporting of past events, so no real collected intel is sent to a cloud provider even during that comparison.

The payload hash log gives an auditor a complete record of every cloud call made during development, without the audit log itself becoming a copy of the data.
