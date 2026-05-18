import logging

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CLIENT_CONFIG_KEY, CLIENT_KEY, CONFIG_KEY, FLOW_ID_KEY, PLATFORMS
from .coordinator import GwnDataUpdateCoordinator

from .gwn_lib_interface import GwnLibInterface
from gwn.api import GwnClient
from gwn.authentication import GwnConfig
from gwn.constants import Constants

_LOGGER = logging.getLogger(Constants.LOG)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    gwn_client_config: dict[str, dict[str, object]] = hass.data[DOMAIN].setdefault(CLIENT_CONFIG_KEY, {})
    
    flow_id: str | None = entry.data.get(FLOW_ID_KEY)
    client_config: dict[str, Any] | None = None if flow_id is None else gwn_client_config.pop(flow_id, None)

    gwn_config: GwnConfig
    gwn_client: GwnClient

    if client_config is not None:
        gwn_config = client_config[CONFIG_KEY]
        gwn_client = client_config[CLIENT_KEY]
    else:
        gwn_config = GwnLibInterface.build_gwn_config(entry)
        gwn_client = GwnClient(gwn_config)

    coordinator: GwnDataUpdateCoordinator = GwnDataUpdateCoordinator(hass, entry, gwn_config, gwn_client)
    try:
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator
    except Exception as e:
        _LOGGER.error(f"Failed to setup coordinator: {e}")
        await coordinator.close()
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.setdefault(DOMAIN, {})        
        coordinator: GwnDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.close()
    return unload_ok
