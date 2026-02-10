#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Velero Integrator Charm."""

import logging

import ops
from data_platform_helpers.advanced_statuses.handler import StatusHandler

from core.context import Context
from events.general import GeneralEvents
from events.k8s_backup import K8sBackupTargetEvents
from events.velero_backup import VeleroBackupEvents

logger = logging.getLogger(__name__)


class VeleroIntegratorCharm(ops.CharmBase):
    """Charm for integrating applications with Velero backup schedules."""

    def __init__(self, *args) -> None:
        super().__init__(*args)

        # Context - single source of truth for charm state
        self.context = Context(self)

        # Event handlers (order matters for status priority)
        self.general_events = GeneralEvents(self, self.context)
        self.k8s_backup_events = K8sBackupTargetEvents(self, self.context)
        self.velero_backup_events = VeleroBackupEvents(self, self.context)

        # Status handler from data-platform-helpers
        self.status = StatusHandler(
            self,
            self.general_events,
            self.k8s_backup_events,
            self.velero_backup_events,
        )


if __name__ == "__main__":  # pragma: nocover
    ops.main(VeleroIntegratorCharm)
