"""The k3s egress policy is the control the in-process guard cannot be (#55).

A browser resolves and navigates inside its own process, and a name can answer
differently between the check and the connection. Neither matters if the packet
to an internal address is dropped. That only holds if the policy selects the
pods it names, so these tests read the policy against the deployments.

A NetworkPolicy whose selector matches no pod is not an error in Kubernetes: it
applies to nothing, quietly, which is the failure mode this file exists to catch.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_K3S = Path(__file__).resolve().parents[2] / "infra" / "k3s"

_PRIVATE_RANGES = {"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16"}

# Named by a rule, deployed by no manifest in infra/k3s. Recorded rather than
# tolerated: the gap is the missing Deployment, and this set is what keeps it
# from quietly becoming a rule that permits traffic to nothing.
_NOT_DEPLOYED_ON_K3S = {"tor-proxy"}


def _documents(path: Path) -> list[dict]:
    return [doc for doc in yaml.safe_load_all(path.read_text()) if doc]


def _policies() -> dict[str, dict]:
    return {
        doc["metadata"]["name"]: doc
        for doc in _documents(_K3S / "networkpolicy.yml")
        if doc.get("kind") == "NetworkPolicy"
    }


def _deployed_app_labels() -> set[str]:
    labels: set[str] = set()
    for path in sorted(_K3S.glob("*.yml")):
        if path.name == "networkpolicy.yml":
            continue
        for doc in _documents(path):
            if doc.get("kind") != "Deployment":
                continue
            app = doc["spec"]["template"]["metadata"]["labels"].get("app")
            if app:
                labels.add(app)
    return labels


def _selected_apps(policy: dict) -> set[str]:
    selector = policy["spec"]["podSelector"]
    if not selector:
        return set()  # {} selects every pod in the namespace
    apps: set[str] = set()
    match_labels = selector.get("matchLabels", {})
    if "app" in match_labels:
        apps.add(match_labels["app"])
    for expression in selector.get("matchExpressions", []):
        if expression["key"] == "app" and expression["operator"] == "In":
            apps.update(expression["values"])
    return apps


@pytest.mark.parametrize(
    "policy_name",
    [
        "allow-external-https-egress",
        "allow-scraper-tor-egress",
        "allow-services-to-datastores-egress",
        "allow-services-to-ollama-egress",
    ],
)
def test_every_egress_policy_selects_pods_that_exist(policy_name: str):
    deployed = _deployed_app_labels()
    selected = _selected_apps(_policies()[policy_name])

    assert selected, f"{policy_name} selects nothing by app label"
    assert selected <= deployed, (
        f"{policy_name} names apps that no deployment carries: {sorted(selected - deployed)}"
    )


def test_the_collectors_may_not_reach_the_internal_network():
    """Outbound scraping is allowed to the internet, and not into the deployment."""
    egress = _policies()["allow-external-https-egress"]["spec"]["egress"]
    blocks = [
        peer["ipBlock"] for rule in egress for peer in rule.get("to", []) if "ipBlock" in peer
    ]

    assert blocks, "the rule allows every destination, internal addresses included"
    for block in blocks:
        assert _PRIVATE_RANGES <= set(block.get("except", [])), (
            f"{block['cidr']} does not exclude the private ranges: {block.get('except')}"
        )


def test_the_scraper_can_still_reach_the_services_it_needs():
    """Excluding the private ranges must not cut the collectors off from postgres."""
    selected = _selected_apps(_policies()["allow-services-to-datastores-egress"])

    assert {"scrape-web-worker", "scrape-web-scheduler"} <= selected


def test_egress_is_denied_by_default():
    default = _policies()["default-deny-egress"]

    assert default["spec"]["podSelector"] == {}
    assert default["spec"]["policyTypes"] == ["Egress"]


def _peer_apps(policy: dict) -> set[str]:
    """Every app label a policy names as a destination or a source peer."""
    apps: set[str] = set()
    spec = policy["spec"]
    for rule in spec.get("egress", []) + spec.get("ingress", []):
        for peer in rule.get("to", []) + rule.get("from", []):
            selector = peer.get("podSelector") or {}
            app = selector.get("matchLabels", {}).get("app")
            if app:
                apps.add(app)
    return apps


def test_every_peer_a_rule_names_is_deployed():
    """A rule pointing at a pod that does not exist permits traffic to nothing.

    The selector test above reads only the pods a policy applies TO. This reads
    the peers it lets them talk to, which is where the tor-proxy gap hid.
    """
    deployed = _deployed_app_labels() | _NOT_DEPLOYED_ON_K3S
    unknown = {
        f"{name}:{app}"
        for name, policy in _policies().items()
        for app in _peer_apps(policy)
        if app not in deployed
    }

    assert unknown == set(), f"rules naming peers no manifest deploys: {sorted(unknown)}"


def test_the_services_that_call_the_embedding_endpoint_may_reach_it():
    """RAG chunks must not fail open, so a denied hop here is a broken report."""
    egress = _selected_apps(_policies()["allow-services-to-analyse-scheduler-egress"])
    ingress_sources = _peer_apps(_policies()["allow-services-to-analyse-scheduler"])

    assert {"api", "report-worker"} <= egress
    assert {"api", "report-worker"} <= ingress_sources


def test_every_service_that_calls_ollama_may_reach_it():
    """The api warms the model at startup and probes it in /health/ready."""
    assert {"api", "analyse-worker", "report-worker"} <= _selected_apps(
        _policies()["allow-services-to-ollama-egress"]
    )
    assert {"api", "analyse-worker", "report-worker"} <= _peer_apps(
        _policies()["allow-services-to-ollama"]
    )


def test_dns_egress_does_not_reach_the_internet():
    """Port 53 to anywhere is an exfiltration path out of a collector."""
    for rule in _policies()["allow-dns-egress"]["spec"]["egress"]:
        peers = rule.get("to", [])
        assert peers, "DNS egress names no destination, so it allows every destination"
        for peer in peers:
            assert "namespaceSelector" in peer or "podSelector" in peer
