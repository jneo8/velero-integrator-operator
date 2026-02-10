#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Velero backup relation event handlers."""

from typing import TYPE_CHECKING

from data_platform_helpers.advanced_statuses.models import StatusObject
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope
from ops import Relation
from ops.charm import (
    RelationBrokenEvent,
    RelationChangedEvent,
    RelationCreatedEvent,
    RelationJoinedEvent,
)

from constants import VELERO_BACKUP_RELATION
from core.context import Context
from core.statuses import CharmStatuses, RelationStatuses
from events.base import BaseEventHandler, defer_on_premature_data_access_error

if TYPE_CHECKING:
    from charm import VeleroIntegratorCharm


class VeleroBackupEvents(BaseEventHandler, ManagerStatusProtocol):
    """Class implementing velero-backup relation event hooks."""

    def __init__(self, charm: "VeleroIntegratorCharm", context: Context):
        self.name = "velero-backup"
        super().__init__(charm, self.name)
        self.charm = charm
        self.state: Context = context  # type: ignore[reportIncompatibleVariableOverride]

        self.framework.observe(
            self.charm.on[VELERO_BACKUP_RELATION].relation_created,
            self._on_relation_created,
        )
        self.framework.observe(
            self.charm.on[VELERO_BACKUP_RELATION].relation_joined,
            self._on_relation_joined,
        )
        self.framework.observe(
            self.charm.on[VELERO_BACKUP_RELATION].relation_changed,
            self._on_relation_changed,
        )
        self.framework.observe(
            self.charm.on[VELERO_BACKUP_RELATION].relation_broken,
            self._on_relation_broken,
        )

    @defer_on_premature_data_access_error
    def _on_relation_created(self, _: RelationCreatedEvent) -> None:
        """Handle velero-backup relation created."""
        self.logger.info("velero-backup relation created")
        self.publish_to_all_relations()

    @defer_on_premature_data_access_error
    def _on_relation_joined(self, _: RelationJoinedEvent) -> None:
        """Handle velero-backup relation joined."""
        self.logger.info("velero-backup relation joined")
        self.publish_to_all_relations()

    @defer_on_premature_data_access_error
    def _on_relation_changed(self, _: RelationChangedEvent) -> None:
        """Handle velero-backup relation changed."""
        self.logger.info("velero-backup relation changed")
        self.publish_to_all_relations()

    def _on_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Handle velero-backup relation broken."""
        self.logger.info("velero-backup relation broken")
        self._clear_status()

    def _add_status(self, status: StatusObject) -> None:
        """Add status for this component."""
        for scope in ("app", "unit"):
            self.state.statuses.add(status=status, scope=scope, component=self.name)

    def _clear_status(self) -> None:
        """Clear status for this component."""
        for scope in ("app", "unit"):
            self.state.statuses.clear(scope=scope, component=self.name)

    def publish_to_relation(self, relation: Relation) -> None:
        """Publish backup specs to a specific velero-backup relation."""
        if not self.charm.unit.is_leader() or relation is None:
            return

        config = self.state.config
        if not config:
            self.logger.warning("Invalid config, skipping publish")
            return

        # Get all backup targets and publish merged specs
        targets = self.state.get_backup_targets()
        for target in targets:
            velero_spec = target.to_velero_spec(config)
            databag = target.to_databag_dict(velero_spec)
            relation.data[self.charm.app].update(databag)
            self.logger.info(
                "Published backup spec from %s to velero-backup relation %s",
                target.app_name,
                relation.id,
            )

    def publish_to_all_relations(self) -> None:
        """Publish backup specs to all velero-backup relations."""
        if not self.charm.unit.is_leader():
            return

        self._clear_status()

        for relation in self.state.velero_relations:
            self.publish_to_relation(relation)

        # Store the detailed status based on config
        config = self.state.config
        if config and config.is_scheduled:
            if config.is_paused:
                self._add_status(CharmStatuses.schedule_paused())
            else:
                self._add_status(CharmStatuses.schedule_active(config.schedule or ""))
        else:
            self._add_status(CharmStatuses.ACTIVE_MANUAL.value)

    def get_statuses(self, scope: Scope, recompute: bool = False) -> list[StatusObject]:
        """Return the list of statuses for this component."""
        if not self.charm.unit.is_leader():
            return []

        if not self.state.has_velero_relation:
            return [RelationStatuses.MISSING_VELERO_RELATION.value]

        if not recompute:
            return list(self.state.statuses.get(scope=scope, component=self.name))

        # Determine appropriate status based on config
        config = self.state.config
        if config and config.is_scheduled:
            if config.is_paused:
                return [CharmStatuses.schedule_paused()]
            return [CharmStatuses.schedule_active(config.schedule or "")]

        return [CharmStatuses.ACTIVE_MANUAL.value]
