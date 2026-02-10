#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Status definitions for Velero Integrator charm."""

from enum import Enum

from data_platform_helpers.advanced_statuses.models import StatusObject


class CharmStatuses(Enum):
    """Generic status objects related to the charm."""

    ACTIVE_IDLE = StatusObject(status="active", message="")
    ACTIVE_MANUAL = StatusObject(status="active", message="Manual backup mode")
    ACTIVE_STANDBY = StatusObject(status="active", message="Unit is ready (standby)")

    @staticmethod
    def schedule_active(schedule: str) -> StatusObject:
        """Active with schedule."""
        return StatusObject(status="active", message=f"Schedule: {schedule}")

    @staticmethod
    def schedule_paused() -> StatusObject:
        """Schedule is paused."""
        return StatusObject(status="active", message="Schedule paused")


class ConfigStatuses(Enum):
    """Status objects related to config options."""

    @staticmethod
    def invalid_config_parameters(fields: list[str]) -> StatusObject:
        """Return status for invalid config parameters."""
        fields_str = ", ".join(f"'{field}'" for field in fields)
        return StatusObject(
            status="blocked",
            message=f"Invalid configuration: {fields_str}",
            action=f"Fix invalid config(s): {fields_str}",
        )


class RelationStatuses(Enum):
    """Status objects related to relations."""

    MISSING_VELERO_RELATION = StatusObject(
        status="blocked",
        message="Missing relation: velero-backup",
        action="Relate this charm to velero-operator",
    )

    WAITING_K8S_BACKUP_RELATION = StatusObject(
        status="waiting",
        message="Waiting for k8s-backup-target relation",
        action="Relate applications that need backup to this charm",
    )
