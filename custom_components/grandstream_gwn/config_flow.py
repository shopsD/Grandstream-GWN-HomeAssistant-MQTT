import logging
import re
import voluptuous as vol
from dataclasses import dataclass, field
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

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
    MAX_PAGES_CONFIG_KEY,
    PAGE_SIZE_CONFIG_KEY,
    PASSWORD_CONFIG_KEY,
    REFRESH_PERIOD_S_CONFIG_KEY,
    RESTRICTED_API_CONFIG_KEY,
    SECRET_KEY_CONFIG_KEY,
    USERNAME_CONFIG_KEY
)
from .gwn_lib_interface import GwnLibInterface
from gwn.api import GwnClient
from gwn.authentication import GwnConfig
from gwn.constants import Constants

MAC_MATCHER: re.Pattern[str] = re.compile(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
_LOGGER = logging.getLogger(Constants.LOG)

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
    def _check_numeric_list(list_string: str) -> bool:
        return list_string == "" or list_string.replace(",","").replace(" ","").isnumeric()

    @staticmethod
    def _check_mac_list(list_string: str) -> bool:
        return list_string == "" or all(MAC_MATCHER.fullmatch(mac.strip()) for mac in list_string.split(","))

    @staticmethod
    def _normalise_url(url: str) -> str:
        return url.strip().rstrip("/").lower()

    @staticmethod
    async def build_and_validate_config(flow_id: str, existing_entries: list[ConfigEntry] = [], user_input: dict[str, Any] | None = None, previous_username: str | None = None, previous_password: str | None = None) -> FlowData:
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
                _LOGGER.debug("Config Flow: Reusing previous password")
            
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
            if exclude_passphrase is not None:
                if ConfigFlow._check_numeric_list(exclude_passphrase):
                    data[EXCLUDE_PASSPHRASE_CONFIG_KEY] = exclude_passphrase
                else:
                    errors[EXCLUDE_PASSPHRASE_CONFIG_KEY] = "comma_separated_numbers"

            exclude_ssid = user_input.get(EXCLUDE_SSID_CONFIG_KEY)
            if exclude_ssid is not None:
                if ConfigFlow._check_numeric_list(exclude_ssid):
                    data[EXCLUDE_SSID_CONFIG_KEY] = exclude_ssid
                else:
                    errors[EXCLUDE_SSID_CONFIG_KEY] = "comma_separated_numbers"

            exclude_device = user_input.get(EXCLUDE_DEVICE_CONFIG_KEY)
            if exclude_device is not None:
                if ConfigFlow._check_mac_list(exclude_device):
                    data[EXCLUDE_DEVICE_CONFIG_KEY] = exclude_device
                else:
                    errors[EXCLUDE_DEVICE_CONFIG_KEY] = "comma_separated_macs"

            exclude_network = user_input.get(EXCLUDE_NETWORK_CONFIG_KEY)
            if exclude_network is not None:
                if ConfigFlow._check_numeric_list(exclude_network):
                    data[EXCLUDE_NETWORK_CONFIG_KEY] = exclude_network
                else:
                    errors[EXCLUDE_NETWORK_CONFIG_KEY] = "comma_separated_numbers"

            base_url = user_input.get(BASE_URL_CONFIG_KEY)
            if base_url is not None:
                base_url = ConfigFlow._normalise_url(str(base_url))
                if any(str(entry.data.get(BASE_URL_CONFIG_KEY, "")) == base_url for entry in existing_entries):
                    errors[BASE_URL_CONFIG_KEY] = "base_url_exists"
                else:
                    data[BASE_URL_CONFIG_KEY] = base_url

            if len(errors) == 0:
                gwn_config: GwnConfig = GwnLibInterface.build_gwn_config(data)
                gwn_client: GwnClient = GwnClient(gwn_config) # prevent a double login so preserve the client if the authentication succeeds
                authenticated: bool = False
                try:
                    authenticated = await gwn_client.authenticate()
                except Exception as e:
                    _LOGGER.error(f"Config Flow: Failed to Authenticate against {base_url}: {e}")
                if authenticated:
                    _LOGGER.debug(f"Config Flow: Successfully Authenticated against {base_url}")
                    return FlowData(gwn_config=gwn_config, gwn_client=gwn_client, data=data, user_input=dict(user_input), authenticated=True)
                await gwn_client.close()
                errors["base"] = "user_pass_authentication_failed" if gwn_client.api_authenticated else "api_authentication_failed"
            return FlowData(data=data, user_input=dict(user_input), errors=errors)
        return FlowData()

    @staticmethod
    def create_config_schema(input_overrides: dict[str, Any] | None = None, read_only: bool = False) -> vol.Schema:
        defaults: GwnConfig = GwnConfig("", "")
        if input_overrides is None:
            _LOGGER.debug("Config Flow: No overridden inputs for config flow. Defaults will be used")
            input_overrides = {}
        return vol.Schema(
            {
                vol.Required(APP_ID_CONFIG_KEY, default=input_overrides.get(APP_ID_CONFIG_KEY, defaults.app_id)): str,
                vol.Required(SECRET_KEY_CONFIG_KEY, default=input_overrides.get(SECRET_KEY_CONFIG_KEY, defaults.secret_key)): str,
                vol.Optional(RESTRICTED_API_CONFIG_KEY, default=input_overrides.get(RESTRICTED_API_CONFIG_KEY, defaults.restricted_api)): bool,
                vol.Optional(USERNAME_CONFIG_KEY, description={"suggested_value": input_overrides.get(USERNAME_CONFIG_KEY, "" if defaults.username is None else defaults.username)}): str,
                vol.Optional(PASSWORD_CONFIG_KEY, default=""): str,
                vol.Optional(BASE_URL_CONFIG_KEY, default=input_overrides.get(BASE_URL_CONFIG_KEY, defaults.base_url)): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, read_only=read_only)),
                vol.Optional(PAGE_SIZE_CONFIG_KEY, default=input_overrides.get(PAGE_SIZE_CONFIG_KEY, defaults.page_size)): int,
                vol.Optional(MAX_PAGES_CONFIG_KEY, default=input_overrides.get(MAX_PAGES_CONFIG_KEY, defaults.max_pages)): int,
                vol.Optional(REFRESH_PERIOD_S_CONFIG_KEY, default=input_overrides.get(REFRESH_PERIOD_S_CONFIG_KEY, defaults.refresh_period_s)): int,
                vol.Optional(EXCLUDE_PASSPHRASE_CONFIG_KEY, description={"suggested_value": input_overrides.get(EXCLUDE_PASSPHRASE_CONFIG_KEY, ",".join(str(id) for id in defaults.exclude_passphrase))}): str,
                vol.Optional(EXCLUDE_SSID_CONFIG_KEY, description={"suggested_value": input_overrides.get(EXCLUDE_SSID_CONFIG_KEY, ",".join(str(id) for id in defaults.exclude_ssid))}): str,
                vol.Optional(EXCLUDE_DEVICE_CONFIG_KEY, description={"suggested_value": input_overrides.get(EXCLUDE_DEVICE_CONFIG_KEY, ",".join(defaults.exclude_device))}): str,
                vol.Optional(EXCLUDE_NETWORK_CONFIG_KEY, description={"suggested_value": input_overrides.get(EXCLUDE_NETWORK_CONFIG_KEY, ",".join(str(id) for id in defaults.exclude_network))}): str,
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=ConfigFlow.create_config_schema(), errors={})

        existing_entries: list[ConfigEntry] = self.hass.config_entries.async_entries(DOMAIN)
        flow_data: FlowData = await ConfigFlow.build_and_validate_config(self.flow_id, existing_entries, user_input)

        if not flow_data.authenticated or flow_data.gwn_config is None:
            return self.async_show_form(step_id="user", data_schema=ConfigFlow.create_config_schema(flow_data.user_input), errors=flow_data.errors)

        self.hass.data.setdefault(DOMAIN, {})
        self.hass.data[DOMAIN].setdefault(CLIENT_CONFIG_KEY, {})
        self.hass.data[DOMAIN][CLIENT_CONFIG_KEY][self.flow_id] = {CLIENT_KEY: flow_data.gwn_client, CONFIG_KEY: flow_data.gwn_config}
        return self.async_create_entry(title=flow_data.gwn_config.base_url, data=flow_data.data)

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
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=ConfigFlow.create_config_schema(current_data, True), errors={})
        # base url can't be editied since True is passed in to the create_config_schema so no need to fetch all existing entries to check against
        flow_data: FlowData = await ConfigFlow.build_and_validate_config(flow_id, [], user_input, previous_username, previous_password)

        if not flow_data.authenticated:
            return self.async_show_form(step_id="init", data_schema=ConfigFlow.create_config_schema(flow_data.user_input, True), errors=flow_data.errors)
        self.hass.data.setdefault(DOMAIN, {})
        self.hass.data[DOMAIN].setdefault(CLIENT_CONFIG_KEY, {})
        self.hass.data[DOMAIN][CLIENT_CONFIG_KEY][flow_id] = {CLIENT_KEY: flow_data.gwn_client, CONFIG_KEY: flow_data.gwn_config}

        self.hass.config_entries.async_update_entry(self._config_entry, data=flow_data.data)
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        return self.async_create_entry(title="", data={})
