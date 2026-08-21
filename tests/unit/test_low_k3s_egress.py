"""Unit tests for k3s egress network policy — LOW-21.

Must have at least one egress rule to restrict outbound traffic.
Default k8s behavior is allow-all egress — need explicit deny + allows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

NETPOL_PATH = Path("infra/k3s/networkpolicy.yml")


class TestK3sEgressPolicy:
    def test_networkpolicy_file_exists(self):
        assert NETPOL_PATH.exists(), "k3s networkpolicy.yml not found"

    def test_has_egress_rules(self):
        """At least one NetworkPolicy must define egress rules."""
        content = NETPOL_PATH.read_text()
        docs = list(yaml.safe_load_all(content))
        policies = [d for d in docs if d and d.get("kind") == "NetworkPolicy"]

        has_egress = any(
            "egress" in (p.get("spec", {}).get("policyTypes", []))
            or "Egress" in (p.get("spec", {}).get("policyTypes", []))
            for p in policies
        )
        assert has_egress, (
            "No NetworkPolicy with Egress policyType found — outbound traffic is unrestricted"
        )
