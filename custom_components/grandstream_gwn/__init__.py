from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import GwnDataUpdateCoordinator

from .GwnLibInterface import GwnLibInterface
from gwn.api import GwnClient
from gwn.authentication import GwnConfig

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    gwn_client_config: dict[str, dict[str, object]] = hass.data[DOMAIN].setdefault("gwn_client_config", {})
    
    flow_id: str | None = entry.data.get("flow_id")
    client_config: dict[str, Any] | None = None if flow_id is None else gwn_client_config.pop(flow_id, None)

    gwn_config: GwnConfig
    gwn_client: GwnClient

    if client_config is not None:
        gwn_config = client_config["config"]
        gwn_client = client_config["client"]
    else:
        gwn_config = GwnLibInterface.build_gwn_config(entry)
        gwn_client = GwnClient(gwn_config)

    coordinator = GwnDataUpdateCoordinator(hass, entry, gwn_config, gwn_client)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
