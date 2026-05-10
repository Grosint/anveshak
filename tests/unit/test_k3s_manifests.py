"""RED phase — K3s manifest validation tests.

Tests for:
  - All required service manifests exist
  - Env var ordering: POSTGRES_PASSWORD before POSTGRES_URL
  - Security hardening: securityContext on all pods
  - Liveness probes on all pods
  - NetworkPolicy exists
  - PodDisruptionBudget for API
  - Kustomization includes all resources

pytest.mark.unit — file-based checks only, no cluster required.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

K3S_DIR = Path("infra/k3s")


def _load_yaml_docs(path: Path) -> list[dict]:
    """Load all YAML documents from a file."""
    with open(path) as f:
        return list(yaml.safe_load_all(f))


def _find_deployments(docs: list[dict]) -> list[dict]:
    """Filter to Deployment resources."""
    return [d for d in docs if d and d.get("kind") == "Deployment"]


def _get_container(deployment: dict, idx: int = 0) -> dict:
    """Get the first container spec from a Deployment."""
    return deployment["spec"]["template"]["spec"]["containers"][idx]


def _get_env_names(container: dict) -> list[str]:
    """Get ordered list of env var names from a container."""
    return [e["name"] for e in container.get("env", [])]


# ===================================================================
# 1. Required manifests exist
# ===================================================================

class TestManifestExistence:
    """All required K3s service manifests must exist."""

    REQUIRED = [
        "ollama.yml",
        "scraper.yml",
        "reporter.yml",
        "vision.yml",
        "frontend.yml",
        "ingress.yml",
        "networkpolicy.yml",
    ]

    @pytest.mark.parametrize("filename", REQUIRED)
    def test_manifest_exists(self, filename):
        path = K3S_DIR / filename
        assert path.exists(), f"Missing K3s manifest: {filename}"


# ===================================================================
# 2. Env var ordering: POSTGRES_PASSWORD before POSTGRES_URL
# ===================================================================

class TestEnvVarOrdering:
    """POSTGRES_PASSWORD must be defined before POSTGRES_URL."""

    @pytest.mark.parametrize("filename", ["api.yml", "analyst.yml"])
    def test_password_before_url(self, filename):
        docs = _load_yaml_docs(K3S_DIR / filename)
        for dep in _find_deployments(docs):
            container = _get_container(dep)
            names = _get_env_names(container)
            if "POSTGRES_PASSWORD" in names and "POSTGRES_URL" in names:
                pw_idx = names.index("POSTGRES_PASSWORD")
                url_idx = names.index("POSTGRES_URL")
                assert pw_idx < url_idx, (
                    f"{filename}: POSTGRES_PASSWORD (idx={pw_idx}) must come "
                    f"before POSTGRES_URL (idx={url_idx}) for $(POSTGRES_PASSWORD) "
                    f"substitution to work"
                )


# ===================================================================
# 3. securityContext on all Deployments
# ===================================================================

class TestSecurityContext:
    """All Deployments must have pod-level securityContext."""

    MANIFESTS_WITH_DEPLOYMENTS = [
        "api.yml", "analyst.yml", "postgres.yml", "redis.yml",
        "ollama.yml", "scraper.yml", "reporter.yml", "vision.yml",
        "frontend.yml",
    ]

    @pytest.mark.parametrize("filename", MANIFESTS_WITH_DEPLOYMENTS)
    def test_has_security_context(self, filename):
        path = K3S_DIR / filename
        if not path.exists():
            pytest.skip(f"{filename} not yet created")
        docs = _load_yaml_docs(path)
        for dep in _find_deployments(docs):
            pod_spec = dep["spec"]["template"]["spec"]
            sc = pod_spec.get("securityContext", {})
            container = _get_container(dep)
            csc = container.get("securityContext", {})
            # At least one of pod-level or container-level must set runAsNonRoot
            has_non_root = (
                sc.get("runAsNonRoot") is True
                or csc.get("runAsNonRoot") is True
            )
            # postgres and redis run as their own user — skip runAsNonRoot check
            name = dep["metadata"]["name"]
            if name in ("postgres", "redis"):
                continue
            assert has_non_root, (
                f"{filename}/{name}: must set runAsNonRoot: true "
                f"in securityContext"
            )


# ===================================================================
# 4. Liveness probes on all Deployments
# ===================================================================

class TestLivenessProbes:
    """All Deployments must have livenessProbe (not just readinessProbe)."""

    MANIFESTS = [
        "api.yml", "analyst.yml", "ollama.yml", "scraper.yml",
        "reporter.yml", "vision.yml", "frontend.yml",
    ]

    @pytest.mark.parametrize("filename", MANIFESTS)
    def test_has_liveness_probe(self, filename):
        path = K3S_DIR / filename
        if not path.exists():
            pytest.skip(f"{filename} not yet created")
        docs = _load_yaml_docs(path)
        for dep in _find_deployments(docs):
            container = _get_container(dep)
            name = dep["metadata"]["name"]
            assert "livenessProbe" in container, (
                f"{filename}/{name}: must have livenessProbe"
            )


# ===================================================================
# 5. NetworkPolicy
# ===================================================================

class TestNetworkPolicy:
    """NetworkPolicy must define default-deny + allow rules."""

    def test_networkpolicy_file_exists(self):
        assert (K3S_DIR / "networkpolicy.yml").exists()

    def test_has_default_deny(self):
        docs = _load_yaml_docs(K3S_DIR / "networkpolicy.yml")
        policies = [d for d in docs if d and d.get("kind") == "NetworkPolicy"]
        assert len(policies) >= 1, "Must have at least one NetworkPolicy"

        # At least one policy should be a default-deny (empty podSelector)
        deny_policies = [
            p for p in policies
            if p["spec"].get("podSelector", {}).get("matchLabels") is None
            or p["spec"].get("podSelector", {}).get("matchLabels") == {}
        ]
        assert len(deny_policies) >= 1, (
            "Must have a default-deny NetworkPolicy (empty podSelector)"
        )


# ===================================================================
# 6. PodDisruptionBudget for API
# ===================================================================

class TestPodDisruptionBudget:
    """API must have a PodDisruptionBudget."""

    def test_api_has_pdb(self):
        docs = _load_yaml_docs(K3S_DIR / "api.yml")
        pdbs = [d for d in docs if d and d.get("kind") == "PodDisruptionBudget"]
        assert len(pdbs) >= 1, "api.yml must include a PodDisruptionBudget"

    def test_pdb_min_available(self):
        docs = _load_yaml_docs(K3S_DIR / "api.yml")
        pdbs = [d for d in docs if d and d.get("kind") == "PodDisruptionBudget"]
        assert pdbs, "No PDB found"
        pdb = pdbs[0]
        assert pdb["spec"].get("minAvailable") == 1, (
            "API PDB must set minAvailable: 1"
        )


# ===================================================================
# 7. Kustomization includes all resources
# ===================================================================

class TestKustomization:
    """kustomization.yml must reference all manifest files."""

    REQUIRED_RESOURCES = [
        "namespace.yml",
        "secrets-template.yml",
        "postgres.yml",
        "redis.yml",
        "api.yml",
        "analyst.yml",
        "ollama.yml",
        "scraper.yml",
        "reporter.yml",
        "vision.yml",
        "frontend.yml",
        "ingress.yml",
        "networkpolicy.yml",
    ]

    def test_all_resources_listed(self):
        docs = _load_yaml_docs(K3S_DIR / "kustomization.yml")
        kustomization = docs[0]
        resources = kustomization.get("resources", [])
        for r in self.REQUIRED_RESOURCES:
            assert r in resources, (
                f"kustomization.yml missing resource: {r}"
            )


# ===================================================================
# 8. Ollama manifest specifics
# ===================================================================

class TestOllamaManifest:
    """Ollama manifest must have correct memory limits and health probe."""

    def test_memory_limit_at_least_8gi(self):
        path = K3S_DIR / "ollama.yml"
        if not path.exists():
            pytest.skip("ollama.yml not yet created")
        docs = _load_yaml_docs(path)
        for dep in _find_deployments(docs):
            container = _get_container(dep)
            mem_limit = container["resources"]["limits"]["memory"]
            # Parse Gi value
            assert "Gi" in mem_limit, "Ollama memory limit must be in Gi"
            val = int(mem_limit.replace("Gi", ""))
            assert val >= 8, f"Ollama needs >= 8Gi memory, got {val}Gi"

    def test_has_model_volume(self):
        path = K3S_DIR / "ollama.yml"
        if not path.exists():
            pytest.skip("ollama.yml not yet created")
        docs = _load_yaml_docs(path)
        for dep in _find_deployments(docs):
            volumes = dep["spec"]["template"]["spec"].get("volumes", [])
            volume_names = [v.get("name", "") for v in volumes]
            # Must have a volume for model storage
            assert any("model" in n.lower() or "ollama" in n.lower() for n in volume_names), (
                "Ollama must have a volume for model storage"
            )
