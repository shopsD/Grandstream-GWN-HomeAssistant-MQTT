from homeassistant.config_entries import ConfigEntry

from gwn.authentication import GwnConfig

class GwnLibInterface:

    @staticmethod
    def parse_int_list(value: str | None) -> list[int]:
        if value is None or value.strip() == "":
            return []
        return [int(item.strip()) for item in value.split(",") if item.strip()]

    @staticmethod
    def parse_str_list(value: str | None) -> list[str]:
        if value is None or value.strip() == "":
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def build_gwn_config(entry: ConfigEntry) -> GwnConfig:
        data = entry.data
        gwn_config: GwnConfig = GwnConfig(app_id=str(data["app_id"]), secret_key=str(data["secret_key"]))
        restricted_api = data.get("restricted_api")
        if restricted_api is not None:
            gwn_config.restricted_api = bool(restricted_api)
        username = data.get("username")
        if username is not None:
            gwn_config.username = str(username)
        password = data.get("password")
        if password not in (None, ""):
            gwn_config.password = str(password)
        base_url = data.get("base_url")
        if base_url is not None:
            gwn_config.base_url = str(base_url)
        page_size = data.get("page_size")
        if page_size is not None:
            gwn_config.page_size = int(page_size)
        max_pages = data.get("max_pages")
        if max_pages is not None:
            gwn_config.max_pages = int(max_pages)
        refresh_period_s = data.get("refresh_period_s")
        if refresh_period_s is not None:
            gwn_config.refresh_period_s = int(refresh_period_s)
        exclude_passphrase = data.get("exclude_passphrase")
        if exclude_passphrase is not None:
            gwn_config.exclude_passphrase = GwnLibInterface.parse_int_list(data.get("exclude_passphrase"))
        exclude_ssid = data.get("exclude_ssid")
        if exclude_ssid is not None:
            gwn_config.exclude_ssid = GwnLibInterface.parse_int_list(data.get("exclude_ssid"))
        exclude_device = data.get("exclude_device")
        if exclude_device is not None:
            gwn_config.exclude_device = [GwnConfig.normalise_mac(mac) for mac in GwnLibInterface.parse_str_list(exclude_device)]
        exclude_network = data.get("exclude_network")
        if exclude_network is not None:
            gwn_config.exclude_network = GwnLibInterface.parse_int_list(data.get("exclude_network"))
        ignore_failed_fetch_before_update = data.get("ignore_failed_fetch_before_update")
        if ignore_failed_fetch_before_update is not None:
            gwn_config.ignore_failed_fetch_before_update = bool(ignore_failed_fetch_before_update)
        ssid_name_to_device_binding = data.get("ssid_name_to_device_binding")
        if ssid_name_to_device_binding is not None:
            gwn_config.ssid_name_to_device_binding = bool(ssid_name_to_device_binding)
        no_publish = data.get("no_publish")
        if no_publish is not None:
            gwn_config.no_publish = bool(no_publish)
        return gwn_config
