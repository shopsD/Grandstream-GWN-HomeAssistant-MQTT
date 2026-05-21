from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry, EntityRegistry

from .const import DOMAIN

class GwnCommon:

    @staticmethod
    def update_entities(entity_type: str, entry: ConfigEntry, cached_unique_ids: set[str], current_unique_ids: set[str], new_entities: list[Any], entity_registry: EntityRegistry, async_add_entities: AddEntitiesCallback) -> set[str]:
        # Remove any device that is not in the cache since it likely means they are have been removed from gwn manager (removed network, device or ssid)
        removed_unique_ids: set[str] = cached_unique_ids - current_unique_ids
        registered_entries = async_entries_for_config_entry(entity_registry, entry.entry_id)
        registered_unique_ids: set[str] = {
            registry_entry.unique_id
            for registry_entry in registered_entries if registry_entry.platform == DOMAIN
        }

        removed_unique_ids = removed_unique_ids.union(registered_unique_ids - current_unique_ids)
        for unique_id in removed_unique_ids:
            entity_id: str | None = entity_registry.async_get_entity_id(entity_type, DOMAIN, unique_id)
            if entity_id is not None:
                entity_registry.async_remove(entity_id)
        if len(new_entities) > 0:
            async_add_entities(new_entities)
        return current_unique_ids
