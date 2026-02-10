#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""General event handlers (config, upgrade, update-status)."""

from typing import TYPE_CHECKING

from data_platform_helpers.advanced_statuses.models import StatusObject
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope
from ops.charm import ConfigChangedEvent, UpdateStatusEvent, UpgradeCharmEvent
from pydantic import ValidationError

from core.charm_config import CharmConfig
from core.context import Context
from core.statuses import CharmStatuses, ConfigStatuses
from events.base import BaseEventHandler, defer_on_premature_data_access_error

if TYPE_CHECKING:
    from charm import VeleroIntegratorCharm


class GeneralEvents(BaseEventHandler, ManagerStatusProtocol):
    """Class implementing general event hooks."""

    def __init__(self, charm: "VeleroIntegratorCharm", context: Context):
        self.name = "general"
        super().__init__(charm, self.name)
        self.charm = charm
        self.state: Context = context  # type: ignore[reportIncompatibleVariableOverride]

        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)

    @defer_on_premature_data_access_error
    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Handle config changed event."""
        if not self.charm.unit.is_leader():
            return

        self.logger.debug(f"Config changed. Current configuration: {self.charm.config}")
        self._trigger_publish()

    @defer_on_premature_data_access_error
    def _on_upgrade_charm(self, _: UpgradeCharmEvent) -> None:
        """Handle upgrade charm event."""
        if not self.charm.unit.is_leader():
            return

        self.logger.info("Charm upgraded, triggering republish")
        self._trigger_publish()

    @defer_on_premature_data_access_error
    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Handle update status event."""
        self._trigger_publish()

    def _trigger_publish(self) -> None:
        """Trigger publishing to velero-backup relations."""
        if not self.charm.unit.is_leader():
            return
        self.charm.velero_backup_events.publish_to_all_relations()

    def get_statuses(self, scope: Scope, recompute: bool = False) -> list[StatusObject]:
        """Return the list of statuses for this component."""
        status_list: list[StatusObject] = []

        # Check if leader - non-leaders get standby status
        if not self.charm.unit.is_leader():
            return [CharmStatuses.ACTIVE_STANDBY.value]

        # Validate configuration
        try:
            CharmConfig(
                schedule=(
                    str(self.charm.config.get("schedule"))
                    if self.charm.config.get("schedule") is not None
                    else None
                ),
                paused=bool(self.charm.config.get("paused")),
                skip_immediately=bool(self.charm.config.get("skip_immediately")),
                use_owner_references_in_backup=bool(
                    self.charm.config.get("use_owner_references_in_backup")
                ),
            )
        except ValidationError as ex:
            self.logger.warning(str(ex))
            invalid_fields = [
                ".".join(str(p).replace("_", "-") for p in err["loc"]) for err in ex.errors()
            ]
            status_list.append(ConfigStatuses.invalid_config_parameters(invalid_fields))
            return status_list

        return status_list or [CharmStatuses.ACTIVE_IDLE.value]
