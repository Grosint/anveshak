"""Optional Drishti integration bridge.

Activated by: ANVESHAK_DRISHTI_BRIDGE=true + DRISHTI_REDPANDA_BOOTSTRAP set.
Disabled by default — Anveshak runs fully standalone without this.

One-directional: Anveshak emits entities TO Drishti via source.envelopes.v1.
Anveshak NEVER reads from Drishti.
"""

from .emitter import BridgeDisabledError, DrishtiBridgeEmitter

__all__ = ["DrishtiBridgeEmitter", "BridgeDisabledError"]
