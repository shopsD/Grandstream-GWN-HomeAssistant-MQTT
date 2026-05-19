import re
import voluptuous as vol
from dataclasses import dataclass, field
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    APP_ID_CONFIG_KEY,
    BASE_URL_CONFIG_KEY,
    CLIENT_CONFIG_KEY,
    CLIENT_KEY,
    CONFIG_KEY,
    DOMAIN,
    EXCLUDE_DEVICE_CONFIG_KEY,
    EXCLUDE_NETWORK_CONFIG_KEY,
    EXCLUDE_PASSPHRASE_CONFIG_KEY,
    EXCLUDE_SSID_CONFIG_KEY,
    FLOW_ID_KEY,
    IGNORE_FAILED_FETCH_BEFORE_UPDATE_CONFIG_KEY,
    MAX_PAGES_CONFIG_KEY,
    NO_PUBLISH_CONFIG_KEY,
    PAGE_SIZE_CONFIG_KEY,
    PASSWORD_CONFIG_KEY,
    REFRESH_PERIOD_S_CONFIG_KEY,
    RESTRICTED_API_CONFIG_KEY,
    SECRET_KEY_CONFIG_KEY,
    SSID_NAME_TO_DEVICE_BINDING_CONFIG_KEY,
    USERNAME_CONFIG_KEY
)
from .gwn_lib_interface import GwnLibInterface
from gwn.api import GwnClient
from gwn.authentication import GwnConfig

MAC_MATCHER: re.Pattern[str] = re.compile(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")

@dataclass(slots=True)
class FlowData:
    gwn_config: GwnConfig | None = None
    gwn_client: GwnClient | None = None
    data: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    user_input: dict[str, Any] = field(default_factory=dict)
    authenticated: bool = False

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def _check_numeric_list(list_string: str | None) -> bool:
        return list_string is not None and (list_string == "" or list_string.replace(",","").replace(" ","").isnumeric())

    @staticmethod
    def _check_mac_list(list_string: str | None) -> bool:
        if list_string is None:
            return False
        if list_string == "":
            return True
        return all(MAC_MATCHER.fullmatch(mac.strip()) for mac in list_string.split(","))

    @staticmethod
    async def build_and_validate_config(flow_id: str, user_input: dict[str, Any] | None = None, previous_username: str | None = None, previous_password: str | None = None) -> FlowData:
        errors: dict[str, str] = {}
        if user_input is not None:

            data: dict[str, Any] = {
                APP_ID_CONFIG_KEY: str(user_input[APP_ID_CONFIG_KEY]),
                SECRET_KEY_CONFIG_KEY: str(user_input[SECRET_KEY_CONFIG_KEY]),
                FLOW_ID_KEY: flow_id
            }

            page_size = user_input.get(PAGE_SIZE_CONFIG_KEY)
            if page_size is not None:
                if int(page_size) < 1:
                    errors[PAGE_SIZE_CONFIG_KEY] = "required_ge_1"
                else:
                    data[PAGE_SIZE_CONFIG_KEY] = int(page_size)

            max_pages = user_input.get(MAX_PAGES_CONFIG_KEY)
            if max_pages is not None:
                if int(max_pages) < 0:
                    errors[MAX_PAGES_CONFIG_KEY] = "required_ge_0"
                else:
                    data[MAX_PAGES_CONFIG_KEY] = int(max_pages)
            refresh_period_s = user_input.get(REFRESH_PERIOD_S_CONFIG_KEY)
            if refresh_period_s is not None:
                if int(refresh_period_s) < 0:
                    errors[REFRESH_PERIOD_S_CONFIG_KEY] = "required_ge_0"
                else:
                    data[REFRESH_PERIOD_S_CONFIG_KEY] = int(refresh_period_s)

            username = user_input.get(USERNAME_CONFIG_KEY)
            password = user_input.get(PASSWORD_CONFIG_KEY)

            has_username: bool = username not in (None, "")
            has_password: bool = password not in (None, "")
            has_previous_password: bool = previous_password not in (None, "")
            
            hash_password: bool = True
            # if the username has changed, then validate as if its new otherwise
            # if there the password has not changed then use the old one and the old username
            if has_username and not has_password and has_previous_password and previous_username == username:
                has_password = True
                hash_password = False
                password = previous_password
            
            if has_username and not has_password:
                errors[PASSWORD_CONFIG_KEY] = "password_missing"
            elif has_password and not has_username:
                errors[USERNAME_CONFIG_KEY] = "username_missing"
            elif has_password and has_username:
                data[USERNAME_CONFIG_KEY] = str(username)
                data[PASSWORD_CONFIG_KEY] = GwnConfig.hash_password(str(password)) if hash_password else password

            restricted_api = user_input.get(RESTRICTED_API_CONFIG_KEY)
            if restricted_api is not None and bool(restricted_api):
                if not has_username or not has_password:
                    errors[RESTRICTED_API_CONFIG_KEY] = "requires_username_password"
                else:
                    data[RESTRICTED_API_CONFIG_KEY] = bool(restricted_api)

            exclude_passphrase = user_input.get(EXCLUDE_PASSPHRASE_CONFIG_KEY)
            if ConfigFlow._check_numeric_list(exclude_passphrase):
                data[EXCLUDE_PASSPHRASE_CONFIG_KEY] = GwnLibInterface.parse_int_list(exclude_passphrase)
            else:
                errors[EXCLUDE_PASSPHRASE_CONFIG_KEY] = "comma_separated_numbers"

            exclude_ssid = user_input.get(EXCLUDE_SSID_CONFIG_KEY)
            if ConfigFlow._check_numeric_list(exclude_ssid):
                data[EXCLUDE_SSID_CONFIG_KEY] = GwnLibInterface.parse_int_list(exclude_ssid)
            else:
                errors[EXCLUDE_SSID_CONFIG_KEY] = "comma_separated_numbers"

            exclude_device = user_input.get(EXCLUDE_DEVICE_CONFIG_KEY)
            if ConfigFlow._check_mac_list(exclude_device):
                data[EXCLUDE_DEVICE_CONFIG_KEY] = GwnLibInterface.parse_str_list(exclude_device)
            else:
                errors[EXCLUDE_DEVICE_CONFIG_KEY] = "comma_separated_macs"

            exclude_network = user_input.get(EXCLUDE_NETWORK_CONFIG_KEY)
            if ConfigFlow._check_numeric_list(exclude_network):
                data[EXCLUDE_NETWORK_CONFIG_KEY] = GwnLibInterface.parse_int_list(exclude_network)
            else:
                errors[EXCLUDE_NETWORK_CONFIG_KEY] = "comma_separated_numbers"

            base_url = user_input.get(BASE_URL_CONFIG_KEY)
            if base_url is not None:
                data[BASE_URL_CONFIG_KEY] = str(base_url)

            ignore_failed_fetch_before_update = user_input.get(IGNORE_FAILED_FETCH_BEFORE_UPDATE_CONFIG_KEY)
            if ignore_failed_fetch_before_update is not None:
                data[IGNORE_FAILED_FETCH_BEFORE_UPDATE_CONFIG_KEY] = bool(ignore_failed_fetch_before_update)

            ssid_name_to_device_binding = user_input.get(SSID_NAME_TO_DEVICE_BINDING_CONFIG_KEY)
            if ssid_name_to_device_binding is not None:
                data[SSID_NAME_TO_DEVICE_BINDING_CONFIG_KEY] = bool(ssid_name_to_device_binding)

            no_publish = user_input.get(NO_PUBLISH_CONFIG_KEY)
            if no_publish is not None:
                data[NO_PUBLISH_CONFIG_KEY] = bool(no_publish)
            if len(errors) == 0:
                gwn_config: GwnConfig = GwnLibInterface.build_gwn_config(data)
                gwn_client: GwnClient = GwnClient(gwn_config) # prevent a double login so preserve the client if the authentication succeeds
                if await gwn_client.authenticate():
                   return FlowData(gwn_config=gwn_config, gwn_client=gwn_client, data=data, user_input=dict(user_input), authenticated=True)
                await gwn_client.close()
                errors["base"] = "user_pass_authentication_failed" if gwn_client.api_authenticated else "api_authentication_failed"
            return FlowData(data=data, user_input=dict(user_input), errors=errors)
        return FlowData()

    @staticmethod
    def create_config_schema(input_overrides: dict[str, Any] | None = None) -> vol.Schema:
        defaults: GwnConfig = GwnLibInterface.build_gwn_config(input_overrides) if input_overrides is not None else GwnConfig("", "")

        return vol.Schema(
            {
                vol.Required(APP_ID_CONFIG_KEY, default= defaults.app_id): str,
                vol.Required(SECRET_KEY_CONFIG_KEY, default= defaults.secret_key): str,
                vol.Optional(RESTRICTED_API_CONFIG_KEY, default= defaults.restricted_api): bool,
                vol.Optional(USERNAME_CONFIG_KEY, default= defaults.username if defaults.username is not None else ""): str,
                vol.Optional(PASSWORD_CONFIG_KEY, default=""): str,
                vol.Optional(BASE_URL_CONFIG_KEY, default= defaults.base_url): str,
                vol.Optional(PAGE_SIZE_CONFIG_KEY, default= defaults.page_size): int,
                vol.Optional(MAX_PAGES_CONFIG_KEY, default= defaults.max_pages): int,
                vol.Optional(REFRESH_PERIOD_S_CONFIG_KEY, default= defaults.refresh_period_s): int,
                vol.Optional(EXCLUDE_PASSPHRASE_CONFIG_KEY, default= ",".join(str(id) for id in defaults.exclude_passphrase)): str,
                vol.Optional(EXCLUDE_SSID_CONFIG_KEY, default= ",".join(str(id) for id in defaults.exclude_ssid)): str,
                vol.Optional(EXCLUDE_DEVICE_CONFIG_KEY, default= ",".join(defaults.exclude_device)): str,
                vol.Optional(EXCLUDE_NETWORK_CONFIG_KEY, default= ",".join(str(id) for id in defaults.exclude_network)): str,
                vol.Optional(IGNORE_FAILED_FETCH_BEFORE_UPDATE_CONFIG_KEY, default= defaults.ignore_failed_fetch_before_update): bool,
                vol.Optional(SSID_NAME_TO_DEVICE_BINDING_CONFIG_KEY, default= defaults.ssid_name_to_device_binding): bool,
                vol.Optional(NO_PUBLISH_CONFIG_KEY, default= defaults.no_publish): bool
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            flow_data: FlowData = await ConfigFlow.build_and_validate_config(self.flow_id, user_input)

            if flow_data.authenticated and flow_data.gwn_config is not None:
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN].setdefault(CLIENT_CONFIG_KEY, {})
                self.hass.data[DOMAIN][CLIENT_CONFIG_KEY][self.flow_id] = {CLIENT_KEY: flow_data.gwn_client, CONFIG_KEY: flow_data.gwn_config}
                return self.async_create_entry(title=flow_data.gwn_config.base_url, data=flow_data.data)

            return self.async_show_form(step_id="user", data_schema=ConfigFlow.create_config_schema(flow_data.user_input), errors=flow_data.errors)
        return self.async_show_form(step_id="user", data_schema=ConfigFlow.create_config_schema(), errors={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "OptionsFlowHandler":
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry: ConfigEntry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current_data: dict[str, Any] = dict(self._config_entry.data)
        flow_id: str = str(current_data.get(FLOW_ID_KEY, self._config_entry.entry_id))
        current_config: GwnConfig = GwnLibInterface.build_gwn_config(current_data)
        previous_password: str | None = current_config.password
        previous_username: str | None = current_config.username
        if user_input is not None:
            flow_data: FlowData = await ConfigFlow.build_and_validate_config(flow_id, user_input, previous_username, previous_password)

            if flow_data.authenticated:
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN].setdefault(CLIENT_CONFIG_KEY, {})
                self.hass.data[DOMAIN][CLIENT_CONFIG_KEY][flow_id] = {CLIENT_KEY: flow_data.gwn_client, CONFIG_KEY: flow_data.gwn_config}

                self.hass.config_entries.async_update_entry(self._config_entry, data=flow_data.data)
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})

            return self.async_show_form(step_id="init", data_schema=ConfigFlow.create_config_schema(flow_data.user_input), errors=flow_data.errors)
        return self.async_show_form(step_id="init", data_schema=ConfigFlow.create_config_schema(current_data), errors={})
