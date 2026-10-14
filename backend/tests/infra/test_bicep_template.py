"""Compiled-template assertions for `infra/main.bicep` (plan.md "Compiled-template tests")."""

import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.infra

REPO = Path(__file__).parents[3]
MAIN = REPO / "infra" / "main.bicep"

ACR_PULL = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
EH_SENDER = "2b629674-e913-4c01-ae53-ef4638d8f975"
EH_RECEIVER = "a638d3c7-ab3a-418d-83e6-5f17a39d4fde"
BLOB_CONTRIBUTOR = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
AZURE_AI_USER = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
FR_007_ROLES = {ACR_PULL, EH_SENDER, EH_RECEIVER, BLOB_CONTRIBUTOR, AZURE_AI_USER}

GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LAST_LITERAL = re.compile(r"'([^']+)'\)\]$")
REFERENCE = re.compile(r"(parameters|variables)\('([^']+)'\)")


def bicep_command() -> list[str] | None:
    if shutil.which("az"):
        return ["az", "bicep", "build", "--file", str(MAIN), "--stdout"]
    if shutil.which("bicep"):
        return ["bicep", "build", str(MAIN), "--stdout"]
    return None


@dataclass(frozen=True)
class Compiled:
    template: dict[str, Any]
    diagnostics: str


@cache
def compile_main() -> Compiled:
    command = bicep_command()
    if command is None:
        pytest.skip("neither the az CLI nor the bicep CLI is installed")
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
    assert result.returncode == 0, result.stderr
    return Compiled(json.loads(result.stdout), result.stderr)


@dataclass(frozen=True)
class Resource:
    body: dict[str, Any]
    scope: dict[str, Any]

    @property
    def type(self) -> str:
        return str(self.body["type"])

    @property
    def props(self) -> dict[str, Any]:
        props: dict[str, Any] = self.body.get("properties", {})
        return props

    def resolve(self, value: str) -> str:
        """Inline `parameters('x')` / `variables('x')` references whose resolved value is a string."""

        def substitute(match: re.Match[str]) -> str:
            resolved = self.scope.get(match.group(2))
            return f"'{resolved}'" if isinstance(resolved, str) else match.group(0)

        return REFERENCE.sub(substitute, value)


def _resources(template: dict[str, Any]) -> list[dict[str, Any]]:
    resources = template.get("resources", [])
    return list(resources.values()) if isinstance(resources, dict) else list(resources)


def _scope(template: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    scope = {name: p.get("defaultValue") for name, p in template.get("parameters", {}).items()}
    scope.update(values)
    scope.update({k: v for k, v in template.get("variables", {}).items() if isinstance(v, str)})
    return scope


def _module_values(deployment: dict[str, Any], parent: Resource) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, entry in deployment["properties"].get("parameters", {}).items():
        value = entry.get("value")
        if isinstance(value, str) and value.startswith("["):
            match = REFERENCE.fullmatch(value[1:-1])
            value = parent.scope.get(match.group(2)) if match else value
        values[name] = value
    return values


def flatten(template: dict[str, Any], values: dict[str, Any] | None = None) -> Iterator[Resource]:
    scope = _scope(template, values or {})
    for body in _resources(template):
        resource = Resource(body, scope)
        if resource.type == "Microsoft.Resources/deployments":
            yield from flatten(body["properties"]["template"], _module_values(body, resource))
        else:
            yield resource


@cache
def resources() -> tuple[Resource, ...]:
    return tuple(flatten(compile_main().template))


def of_type(resource_type: str) -> list[Resource]:
    return [r for r in resources() if r.type.lower() == resource_type.lower()]


def one(resource_type: str) -> Resource:
    found = of_type(resource_type)
    assert len(found) == 1, f"{resource_type}: {len(found)} resources"
    return found[0]


def last_segment(name: str) -> str:
    if not name.startswith("["):
        return name.rsplit("/", 1)[-1]
    match = LAST_LITERAL.search(name)
    assert match, name
    return match.group(1)


def container_app() -> dict[str, Any]:
    return one("Microsoft.App/containerApps").body


def test_build_has_no_diagnostics() -> None:
    diagnostics = compile_main().diagnostics
    assert "Warning" not in diagnostics
    assert "Error" not in diagnostics


def test_single_replica() -> None:
    scale = container_app()["properties"]["template"]["scale"]
    assert scale["minReplicas"] == 1
    assert scale["maxReplicas"] == 1


def test_ingress_is_external_websocket_capable_on_8000() -> None:
    config = container_app()["properties"]["configuration"]
    ingress = config["ingress"]
    assert ingress["targetPort"] == 8000
    assert ingress["external"] is True
    assert ingress["transport"] == "auto"
    assert ingress["allowInsecure"] is False
    assert config["activeRevisionsMode"] == "Single"


def test_three_healthz_probes() -> None:
    (container,) = container_app()["properties"]["template"]["containers"]
    probes = {p["type"]: p for p in container["probes"]}
    assert set(probes) == {"Startup", "Liveness", "Readiness"}
    for probe in probes.values():
        assert probe["httpGet"]["path"] == "/healthz"
        assert probe["httpGet"]["port"] == 8000
    assert probes["Startup"]["periodSeconds"] == 3
    assert probes["Startup"]["failureThreshold"] == 20
    assert probes["Liveness"]["periodSeconds"] == 10
    assert probes["Readiness"]["periodSeconds"] == 5


def test_container_resources_and_secret_ref() -> None:
    app = container_app()
    (container,) = app["properties"]["template"]["containers"]
    assert "1.0" in str(container["resources"]["cpu"])
    assert container["resources"]["memory"] == "2Gi"
    env = {e["name"]: e for e in container["env"]}
    assert env["APPLICATIONINSIGHTS_CONNECTION_STRING"] == {
        "name": "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "secretRef": "appinsights-connection-string",
    }
    assert {s["name"] for s in app["properties"]["configuration"]["secrets"]} == {
        "appinsights-connection-string"
    }
    for name in [
        "TACTISTREAM_BUS",
        "TACTISTREAM_AGENTS",
        "EVENTHUBS_FULLY_QUALIFIED_NAMESPACE",
        "EVENTHUBS_NAME",
        "EVENTHUBS_CONSUMER_GROUP",
        "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT",
        "AZURE_CLIENT_ID",
        "AZURE_STORAGE_ACCOUNT_URL",
        "TACTISTREAM_ARTIFACT_STORE",
        "TACTISTREAM_ANALYTICS_PUBLISH",
        "TACTISTREAM_HISTORY",
        "TACTISTREAM_HISTORY_TIMEOUT_MS",
        "TACTISTREAM_STATIC_DIR",
        "TACTISTREAM_CONTRACTS_DIR",
        "TACTISTREAM_ENVIRONMENT",
    ]:
        assert name in env, name
    assert env["EVENTHUBS_CONSUMER_GROUP"]["value"] == "live-state"
    assert env["TACTISTREAM_ARTIFACT_STORE"]["value"] == "blob"


def test_container_app_uses_managed_identity_for_registry() -> None:
    app = container_app()
    assert app["identity"]["type"] == "UserAssigned"
    (registry,) = app["properties"]["configuration"]["registries"]
    assert "identity" in registry
    assert "passwordSecretRef" not in registry


def test_container_app_has_azd_service_tag() -> None:
    assert container_app()["tags"]["azd-service-name"] == "web"


def test_event_hub_partitions_and_retention() -> None:
    hub = one("Microsoft.EventHub/namespaces/eventhubs")
    assert last_segment(hub.body["name"]) == "tactistream-feed"
    assert hub.props["partitionCount"] == 2
    assert hub.props["messageRetentionInDays"] == 7


def test_event_hubs_namespace_standard_tls12() -> None:
    namespace = one("Microsoft.EventHub/namespaces")
    assert namespace.body["sku"] == {"name": "Standard", "tier": "Standard", "capacity": 1}
    assert namespace.props["minimumTlsVersion"] == "1.2"


def test_consumer_groups_exactly_live_state_and_fabric() -> None:
    groups = of_type("Microsoft.EventHub/namespaces/eventhubs/consumergroups")
    assert {last_segment(g.body["name"]) for g in groups} == {"live-state", "fabric"}
    assert len(groups) == 2


def test_fabric_listen_rule_is_listen_only() -> None:
    (rule,) = of_type("Microsoft.EventHub/namespaces/eventhubs/authorizationRules")
    assert last_segment(rule.body["name"]) == "fabric-listen"
    assert rule.props["rights"] == ["Listen"]
    assert of_type("Microsoft.EventHub/namespaces/authorizationRules") == []


def test_storage_containers_exactly_three_private() -> None:
    containers = of_type("Microsoft.Storage/storageAccounts/blobServices/containers")
    assert {last_segment(c.body["name"]) for c in containers} == {"datasets", "artifacts", "checkpoints"}
    assert len(containers) == 3
    assert all(c.props["publicAccess"] == "None" for c in containers)


def test_storage_disables_shared_key_and_public_access() -> None:
    account = one("Microsoft.Storage/storageAccounts")
    assert account.body["kind"] == "StorageV2"
    assert account.body["sku"]["name"] == "Standard_LRS"
    assert account.props["allowSharedKeyAccess"] is False
    assert account.props["allowBlobPublicAccess"] is False
    assert account.props["minimumTlsVersion"] == "TLS1_2"


def test_registry_basic_without_admin_user() -> None:
    registry = one("Microsoft.ContainerRegistry/registries")
    assert registry.body["sku"]["name"] == "Basic"
    assert registry.props["adminUserEnabled"] is False


def test_monitoring_workspace_and_app_insights() -> None:
    workspace = one("Microsoft.OperationalInsights/workspaces")
    assert workspace.props["sku"]["name"] == "PerGB2018"
    assert workspace.props["retentionInDays"] == 30
    component = one("Microsoft.Insights/components")
    assert "WorkspaceResourceId" in component.props


def test_role_definitions_equal_fr_007() -> None:
    assignments = of_type("Microsoft.Authorization/roleAssignments")
    found = [set(GUID.findall(a.resolve(a.props["roleDefinitionId"]))) for a in assignments]
    assert all(len(ids) == 1 for ids in found), found
    assert {next(iter(ids)) for ids in found} == FR_007_ROLES
    assert len(assignments) == len(FR_007_ROLES)
    assert all(a.props["principalType"] == "ServicePrincipal" for a in assignments)


def test_budget_notifications() -> None:
    budget = one("Microsoft.Consumption/budgets")
    assert budget.props["timeGrain"] == "Monthly"
    thresholds = {(n["threshold"], n["thresholdType"]) for n in budget.props["notifications"].values()}
    assert thresholds == {(50, "Actual"), (80, "Actual"), (100, "Actual"), (100, "Forecasted")}


def test_outputs_for_azd_and_runtime() -> None:
    outputs = compile_main().template["outputs"]
    assert set(outputs) >= {
        "AZURE_CONTAINER_REGISTRY_ENDPOINT",
        "SERVICE_WEB_NAME",
        "SERVICE_WEB_URI",
        "EVENTHUBS_FULLY_QUALIFIED_NAMESPACE",
        "AZURE_STORAGE_ACCOUNT_URL",
        "APPINSIGHTS_NAME",
        "MANAGED_IDENTITY_CLIENT_ID",
    }
    assert not any("connection" in name.lower() for name in outputs)


def test_no_module_outputs_a_connection_string() -> None:
    def walk(template: dict[str, Any]) -> Iterator[str]:
        yield from template.get("outputs", {})
        for body in _resources(template):
            if body["type"] == "Microsoft.Resources/deployments":
                yield from walk(body["properties"]["template"])

    assert not [name for name in walk(compile_main().template) if "connection" in name.lower()]
