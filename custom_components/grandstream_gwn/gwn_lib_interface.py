from typing import Any

from .const import (
    APP_ID_CONFIG_KEY,
    BASE_URL_CONFIG_KEY,
    EXCLUDE_DEVICE_CONFIG_KEY,
    EXCLUDE_NETWORK_CONFIG_KEY,
    EXCLUDE_PASSPHRASE_CONFIG_KEY,
    EXCLUDE_SSID_CONFIG_KEY,
    MAX_PAGES_CONFIG_KEY,
    PAGE_SIZE_CONFIG_KEY,
    PASSWORD_CONFIG_KEY,
    REFRESH_PERIOD_S_CONFIG_KEY,
    RESTRICTED_API_CONFIG_KEY,
    SECRET_KEY_CONFIG_KEY,
    USERNAME_CONFIG_KEY
)
from .integration_config import IntegrationConfig
from gwn.authentication import GwnConfig

class GwnLibInterface:

    @staticmethod
    def _build_gwn_config(data: dict[str, Any]) -> GwnConfig:

        gwn_config: GwnConfig = GwnConfig(app_id=str(data[APP_ID_CONFIG_KEY]), secret_key=str(data[SECRET_KEY_CONFIG_KEY]))
        restricted_api = data.get(RESTRICTED_API_CONFIG_KEY)
        if restricted_api is not None:
            gwn_config.restricted_api = bool(restricted_api)
        username = data.get(USERNAME_CONFIG_KEY)
        if username is not None:
            gwn_config.username = str(username)
        password = data.get(PASSWORD_CONFIG_KEY)
        if password not in (None, ""):
            gwn_config.password = str(password)
        base_url = data.get(BASE_URL_CONFIG_KEY)
        if base_url is not None:
            gwn_config.base_url = str(base_url)
        page_size = data.get(PAGE_SIZE_CONFIG_KEY)
        if page_size is not None:
            gwn_config.page_size = int(page_size)
        max_pages = data.get(MAX_PAGES_CONFIG_KEY)
        if max_pages is not None:
            gwn_config.max_pages = int(max_pages)
        exclude_passphrase = data.get(EXCLUDE_PASSPHRASE_CONFIG_KEY)
        if exclude_passphrase is not None:
            gwn_config.exclude_passphrase = GwnLibInterface.parse_int_list(data.get(EXCLUDE_PASSPHRASE_CONFIG_KEY))
        exclude_ssid = data.get(EXCLUDE_SSID_CONFIG_KEY)
        if exclude_ssid is not None:
            gwn_config.exclude_ssid = GwnLibInterface.parse_int_list(data.get(EXCLUDE_SSID_CONFIG_KEY))
        exclude_device = data.get(EXCLUDE_DEVICE_CONFIG_KEY)
        if exclude_device is not None:
            gwn_config.exclude_device = [GwnConfig.normalise_mac(mac) for mac in GwnLibInterface.parse_str_list(exclude_device)]
        exclude_network = data.get(EXCLUDE_NETWORK_CONFIG_KEY)
        if exclude_network is not None:
            gwn_config.exclude_network = GwnLibInterface.parse_int_list(data.get(EXCLUDE_NETWORK_CONFIG_KEY))

        # Hardcode these values
        gwn_config.ignore_failed_fetch_before_update = False
        gwn_config.ssid_name_to_device_binding = True
        gwn_config.no_publish = False
        return gwn_config

    @staticmethod
    def parse_int_list(value: str | list[int] | None) -> list[int]:
        if isinstance(value, list):
            return value
        if value is None or value.strip() == "":
            return []
        return [int(item.strip()) for item in value.split(",") if item.strip()]

    @staticmethod
    def parse_str_list(value: str | list[str] | None) -> list[str]:
        if isinstance(value, list):
            return value
        if value is None or value.strip() == "":
            return []
        return [GwnConfig.normalise_mac(item.strip()) for item in value.split(",") if item.strip()]

    @staticmethod
    def build_integration_config(data: dict[str, Any]) -> IntegrationConfig:
        integration_config: IntegrationConfig = IntegrationConfig(gwn_config=GwnLibInterface._build_gwn_config(data))
        refresh_period_s = data.get(REFRESH_PERIOD_S_CONFIG_KEY)
        if refresh_period_s is not None:
            integration_config.refresh_period_s = int(refresh_period_s)
        return integration_config
