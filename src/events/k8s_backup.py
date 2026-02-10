#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""K8s backup target relation event handlers."""

from typing import TYPE_CHECKING

from data_platform_helpers.advanced_statuses.models import StatusObject
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope
from ops.charm import (
    RelationBrokenEvent,
    RelationChangedEvent,
    RelationCreatedEvent,
    RelationJoinedEvent,
)

from constants import K8S_BACKUP_TARGET_RELATION
from core.context import Context
from core.statuses import CharmStatuses, RelationStatuses
from events.base import BaseEventHandler, defer_on_premature_data_access_error

if TYPE_CHECKING:
    from charm import VeleroIntegratorCharm


class K8sBackupTargetEvents(BaseEventHandler, ManagerStatusProtocol):
    """Class implementing k8s-backup-target relation event hooks."""

    def __init__(self, charm: "VeleroIntegratorCharm", context: Context):
        self.name = "k8s-backup-target"
        super().__init__(charm, self.name)
        self.charm = charm
        self.state: Context = context  # type: ignore[reportIncompatibleVariableOverride]

        self.framework.observe(
            self.charm.on[K8S_BACKUP_TARGET_RELATION].relation_created,
            self._on_relation_created,
        )
        self.framework.observe(
            self.charm.on[K8S_BACKUP_TARGET_RELATION].relation_joined,
            self._on_relation_joined,
        )
        self.framework.observe(
            self.charm.on[K8S_BACKUP_TARGET_RELATION].relation_changed,
            self._on_relation_changed,
        )
        self.framework.observe(
            self.charm.on[K8S_BACKUP_TARGET_RELATION].relation_broken,
            self._on_relation_broken,
        )

    @defer_on_premature_data_access_error
    def _on_relation_created(self, _: RelationCreatedEvent) -> None:
        """Handle k8s-backup-target relation created."""
        self.logger.info("k8s-backup-target relation created")
        self._trigger_publish()

    @defer_on_premature_data_access_error
    def _on_relation_joined(self, _: RelationJoinedEvent) -> None:
        """Handle k8s-backup-target relation joined."""
        self.logger.info("k8s-backup-target relation joined")
        self._trigger_publish()

    @defer_on_premature_data_access_error
    def _on_relation_changed(self, _: RelationChangedEvent) -> None:
        """Handle k8s-backup-target relation changed."""
        self.logger.info("k8s-backup-target relation changed")
        self._trigger_publish()

    def _on_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Handle k8s-backup-target relation broken."""
        self.logger.info("k8s-backup-target relation broken")
        self._clear_status()
        self._trigger_publish()

    def _trigger_publish(self) -> None:
        """Trigger publishing to velero-backup relations."""
        if not self.charm.unit.is_leader():
            return
        self.charm.velero_backup_events.publish_to_all_relations()

    def _clear_status(self) -> None:
        """Clear status for this component."""
        for scope in ("app", "unit"):
            self.state.statuses.clear(scope=scope, component=self.name)

    def get_statuses(self, scope: Scope, recompute: bool = False) -> list[StatusObject]:
        """Return the list of statuses for this component."""
        if not self.charm.unit.is_leader():
            return []

        if not self.state.has_k8s_backup_relation:
            return [RelationStatuses.WAITING_K8S_BACKUP_RELATION.value]

        return [CharmStatuses.ACTIVE_IDLE.value]
