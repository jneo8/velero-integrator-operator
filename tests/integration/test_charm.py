# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for velero-integrator charm."""

import json
import logging
from pathlib import Path

import jubilant
from helpers import (
    APP_NAME,
    INTEGRATOR_K8S_BACKUP_RELATION,
    INTEGRATOR_VELERO_BACKUP_RELATION,
    TEST_APP_NAME,
    TEST_APP_RELATION_NAME,
    VELERO_OPERATOR_APP_NAME,
    VELERO_OPERATOR_BACKUP_RELATION,
    get_application_data_from_relation,
    get_unit_status,
    is_relation_joined,
)

logger = logging.getLogger(__name__)


def test_build_and_deploy(
    juju: jubilant.Juju,
    velero_integrator_charm: Path,
    test_app_charm: Path,
):
    """Deploy the velero-integrator and test-app charms."""
    logger.info("Deploying velero-integrator and test-app charms")

    # Deploy velero-integrator
    juju.deploy(velero_integrator_charm.resolve(), app=APP_NAME)

    # Deploy test-app
    juju.deploy(test_app_charm.resolve(), app=TEST_APP_NAME)

    # Wait for charms to be idle first
    juju.wait(jubilant.all_agents_idle, timeout=300)

    # Wait for both to settle (velero-integrator should be blocked)
    juju.wait(
        lambda status: status.apps[APP_NAME].units[f"{APP_NAME}/0"].workload_status.current
        == "blocked",
        timeout=300,
    )
    juju.wait(
        lambda status: status.apps[TEST_APP_NAME]
        .units[f"{TEST_APP_NAME}/0"]
        .workload_status.current
        == "waiting",
        timeout=300,
    )


def test_integrate_test_app(juju: jubilant.Juju):
    """Integrate test-app with velero-integrator via k8s-backup-target."""
    logger.info("Integrating test-app with velero-integrator")

    juju.integrate(
        f"{APP_NAME}:{INTEGRATOR_K8S_BACKUP_RELATION}",
        f"{TEST_APP_NAME}:{TEST_APP_RELATION_NAME}",
    )

    # Wait for relation to be established
    juju.wait(
        lambda status: is_relation_joined(juju, APP_NAME, INTEGRATOR_K8S_BACKUP_RELATION),
        timeout=120,
    )

    # test-app should become active
    juju.wait(
        lambda status: status.apps[TEST_APP_NAME]
        .units[f"{TEST_APP_NAME}/0"]
        .workload_status.current
        == "active",
        timeout=120,
    )

    # velero-integrator should still be blocked (no velero-backup relation)
    status, message = get_unit_status(juju, APP_NAME)
    assert status == "blocked", f"Expected blocked status, got {status}"


def test_integrate_velero_operator(juju: jubilant.Juju):
    """Deploy and integrate with Velero Operator to verify active status."""
    logger.info("Deploying Velero Operator")
    juju.deploy(
        "velero-operator",
        app=VELERO_OPERATOR_APP_NAME,
        channel="edge",
        revision=442,
        trust=True,
    )

    logger.info("Integrating with Velero Operator")
    juju.integrate(
        f"{VELERO_OPERATOR_APP_NAME}:{VELERO_OPERATOR_BACKUP_RELATION}",
        f"{APP_NAME}:{INTEGRATOR_VELERO_BACKUP_RELATION}",
    )

    # Wait for everything to settle
    # Velero Operator might block waiting for S3, but Velero Integrator should become active
    # once related to Velero Operator.

    # Wait for velero-integrator to become active
    juju.wait(
        lambda status: status.apps[APP_NAME].units[f"{APP_NAME}/0"].workload_status.current
        == "active",
        timeout=600,
    )

    status, _ = get_unit_status(juju, APP_NAME)
    assert status == "active", f"Expected active status for {APP_NAME}, got {status}"


def test_verify_initial_propagation(juju: jubilant.Juju):
    """Verify initial data propagation to Velero Operator."""
    logger.info("Verifying initial data propagation")

    # We check the data received by the velero-operator
    app_data = get_application_data_from_relation(
        juju, VELERO_OPERATOR_APP_NAME, VELERO_OPERATOR_BACKUP_RELATION
    )

    assert "spec" in app_data, "Expected 'spec' in velero-backup relation data"

    spec = json.loads(app_data["spec"])
    # Defaults from test-app
    assert spec.get("include_namespaces") == ["test-namespace"]
    # No schedule set yet
    assert "schedule" not in spec or spec.get("schedule") is None

    logger.info("Initial propagation verified: %s", spec)


def test_config_schedule_propagation(juju: jubilant.Juju):
    """Test setting schedule configuration and verification via databag."""
    logger.info("Setting schedule configuration")

    juju.config(APP_NAME, {"schedule": "0 2 * * *"})

    # Wait for config to be applied
    juju.wait(jubilant.all_agents_idle, timeout=120)

    # Verify via relation data on operator side
    app_data = get_application_data_from_relation(
        juju, VELERO_OPERATOR_APP_NAME, VELERO_OPERATOR_BACKUP_RELATION
    )
    spec = json.loads(app_data["spec"])

    assert spec.get("schedule") == "0 2 * * *"
    logger.info("Schedule propagation verified")


def test_update_test_app_propagation(juju: jubilant.Juju):
    """Test that updating test-app config propagates to Velero Operator."""
    logger.info("Updating test-app configuration")

    # Change the namespace in test-app
    juju.config(TEST_APP_NAME, {"namespace": "updated-namespace", "ttl": "48h"})
    juju.wait(jubilant.all_agents_idle, timeout=120)

    # Verify via relation data on operator side
    app_data = get_application_data_from_relation(
        juju, VELERO_OPERATOR_APP_NAME, VELERO_OPERATOR_BACKUP_RELATION
    )
    spec = json.loads(app_data["spec"])

    assert spec.get("include_namespaces") == ["updated-namespace"]
    assert spec.get("ttl") == "48h"
    # Schedule should persist
    assert spec.get("schedule") == "0 2 * * *"

    logger.info("Test app update propagation verified")


def test_config_paused_propagation(juju: jubilant.Juju):
    """Test setting paused configuration and verification via databag."""
    logger.info("Setting paused configuration")

    juju.config(APP_NAME, {"paused": "true"})
    juju.wait(jubilant.all_agents_idle, timeout=120)

    # Verify paused=true in databag
    app_data = get_application_data_from_relation(
        juju, VELERO_OPERATOR_APP_NAME, VELERO_OPERATOR_BACKUP_RELATION
    )
    spec = json.loads(app_data["spec"])
    assert spec.get("paused") is True

    # Resume
    juju.config(APP_NAME, {"paused": "false"})
    juju.wait(jubilant.all_agents_idle, timeout=120)

    # Verify paused=false in databag
    app_data = get_application_data_from_relation(
        juju, VELERO_OPERATOR_APP_NAME, VELERO_OPERATOR_BACKUP_RELATION
    )
    spec = json.loads(app_data["spec"])
    assert spec.get("paused") is False

    logger.info("Pause/Resume propagation verified")


def test_config_invalid_schedule(juju: jubilant.Juju):
    """Test invalid schedule configuration."""
    logger.info("Testing invalid schedule configuration")

    # Set invalid schedule
    juju.config(APP_NAME, {"schedule": "invalid-cron"})
    juju.wait(jubilant.all_agents_idle, timeout=120)

    # Should be blocked with config error
    status, message = get_unit_status(juju, APP_NAME)
    assert status == "blocked", f"Expected blocked, got {status}"

    # Reset to valid schedule
    juju.config(APP_NAME, {"schedule": "0 2 * * *"})
    juju.wait(jubilant.all_agents_idle, timeout=120)

    # Should return to active
    status, message = get_unit_status(juju, APP_NAME)
    assert status == "active", f"Expected active, got {status}"


def test_action_status_detail(juju: jubilant.Juju):
    """Test the status-detail action."""
    logger.info("Testing status-detail action")

    # Run the action and expect success
    cmd_output = juju.cli("run", f"{APP_NAME}/0", "status-detail", "--format=json")

    # Simple check for success indication
    assert "completed" in cmd_output or "success" in cmd_output
