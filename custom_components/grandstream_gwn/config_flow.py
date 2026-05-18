import re
import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN
from .GwnLibInterface import GwnLibInterface
from gwn.api import GwnClient
from gwn.authentication import GwnConfig

MAC_MATCHER=re.compile('^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}(,([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})*$')

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def _check_numeric_list(self, list_string: str | None) -> bool:
        return list_string is not None and (list_string == "" or list_string.replace(",","").isnumeric())

    def _check_mac_list(self, list_string: str | None) -> bool:
        return list_string is not None and (list_string == "" or bool(MAC_MATCHER.match(list_string)))

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            gwn_config: GwnConfig = GwnConfig(app_id=str(user_input["app_id"]), secret_key=str(user_input["secret_key"]))
            data: dict[str, Any] = {
                "app_id": gwn_config.app_id,
                "secret_key": gwn_config.secret_key,
                "flow_id": self.flow_id
            }

            page_size = user_input.get("page_size")
            if page_size is not None:
                if int(page_size) < 1:
                    errors["page_size"] = "required_ge_1"
                else:
                    gwn_config.page_size = int(page_size)
                    data["page_size"] = gwn_config.page_size

            max_pages = user_input.get("max_pages")
            if max_pages is not None:
                if int(max_pages) < 0:
                    errors["max_pages"] = "required_ge_0"
                else:
                    gwn_config.max_pages = int(max_pages)
                    data["max_pages"] = gwn_config.max_pages
            refresh_period_s = user_input.get("refresh_period_s")
            if refresh_period_s is not None:
                if int(refresh_period_s) < 0:
                    errors["refresh_period_s"] = "required_ge_0"
                else:
                    gwn_config.refresh_period_s = int(refresh_period_s)
                    data["refresh_period_s"] = gwn_config.refresh_period_s

            username = user_input.get("username")
            password = user_input.get("password")

            has_username = username not in (None, "")
            has_password = password not in (None, "")
            if has_username and not has_password:
                errors["password"] = "required_with_username"
            elif has_password and not has_username:
                errors["username"] = "required_with_password"
            elif has_password and has_username:
                gwn_config.username = str(username)
                gwn_config.password = GwnConfig.hash_password(str(password))
                data["username"] = gwn_config.username
                data["password"] = gwn_config.password

            restricted_api = user_input.get("restricted_api")
            if restricted_api is not None and bool(restricted_api):
                if not has_username or not has_password:
                    errors["restricted_api"] = "requires_password_username"
                else:
                    gwn_config.restricted_api = bool(restricted_api)
                    data["restricted_api"] = gwn_config.restricted_api

            exclude_passphrase = user_input.get("exclude_passphrase")
            if self._check_numeric_list(exclude_passphrase):
                gwn_config.exclude_passphrase = GwnLibInterface.parse_int_list(exclude_passphrase)
                data["exclude_passphrase"] = gwn_config.exclude_passphrase
            else:
                errors["exclude_passphrase"] = "not_list_of_ints"

            exclude_ssid = user_input.get("exclude_ssid")
            if self._check_numeric_list(exclude_ssid):
                gwn_config.exclude_ssid = GwnLibInterface.parse_int_list(exclude_ssid)
                data["exclude_ssid"] = gwn_config.exclude_ssid
            else:
                errors["exclude_ssid"] = "not_list_of_ints"

            exclude_device = user_input.get("exclude_device")
            if self._check_mac_list(exclude_device):
                gwn_config.exclude_device = GwnLibInterface.parse_str_list(exclude_device)
                data["exclude_device"] = gwn_config.exclude_device
            else:
                errors["exclude_device"] = "not_list_of_macs"

            exclude_network = user_input.get("exclude_network")
            if self._check_numeric_list(exclude_network):
                gwn_config.exclude_network = GwnLibInterface.parse_int_list(exclude_network)
                data["exclude_network"] = gwn_config.exclude_network
            else:
                errors["exclude_network"] = "not_list_of_ints"

            base_url = user_input.get("base_url")
            if base_url is not None:
                gwn_config.base_url = str(base_url)
                data["base_url"] = gwn_config.base_url

            ignore_failed_fetch_before_update = user_input.get("ignore_failed_fetch_before_update")
            if ignore_failed_fetch_before_update is not None:
                gwn_config.ignore_failed_fetch_before_update = bool(ignore_failed_fetch_before_update)
                data["ignore_failed_fetch_before_update"] = gwn_config.ignore_failed_fetch_before_update

            ssid_name_to_device_binding = user_input.get("ssid_name_to_device_binding")
            if ssid_name_to_device_binding is not None:
                gwn_config.ssid_name_to_device_binding = bool(ssid_name_to_device_binding)
                data["ssid_name_to_device_binding"] = gwn_config.ssid_name_to_device_binding

            no_publish = user_input.get("no_publish")
            if no_publish is not None:
                gwn_config.no_publish = bool(no_publish)
                data["no_publish"] = gwn_config.no_publish

            if len(errors) == 0:
                gwn_client: GwnClient = GwnClient(gwn_config)
                if await gwn_client.authenticate():
                    self.hass.data.setdefault(DOMAIN, {})
                    self.hass.data[DOMAIN].setdefault("gwn_client_config", {})
                    self.hass.data[DOMAIN]["gwn_client_config"][self.flow_id] = {"client": gwn_client, "config": gwn_config}
                    return self.async_create_entry(title=gwn_config.base_url, data=data)
                await gwn_client.close()
                errors["base"] = "user_pass_authentication_failed" if gwn_client.api_authenticated else "api_authentication_failed"


        defaults: GwnConfig = GwnConfig("dummy", "dummy") # dummy to initialise the defaults
        schema = vol.Schema(
            {
                vol.Required("app_id"): str,
                vol.Required("secret_key"): str,
                vol.Optional("restricted_api", default=defaults.restricted_api): bool,
                vol.Optional("username", default=defaults.username): str,
                vol.Optional("password", default=defaults.password): str,
                vol.Optional("base_url", default=defaults.base_url): str,
                vol.Optional("page_size", default=defaults.page_size): int,
                vol.Optional("max_pages", default=defaults.max_pages): int,
                vol.Optional("refresh_period_s", default=defaults.refresh_period_s): int,
                vol.Optional("exclude_passphrase", default=",".join(str(id) for id in defaults.exclude_passphrase)): str,
                vol.Optional("exclude_ssid", default=",".join(str(id) for id in defaults.exclude_ssid)): str,
                vol.Optional("exclude_device", default=",".join(defaults.exclude_device)): str,
                vol.Optional("exclude_network", default=",".join(str(id) for id in defaults.exclude_network)): str,
                vol.Optional("ignore_failed_fetch_before_update", default=defaults.ignore_failed_fetch_before_update): bool,
                vol.Optional("ssid_name_to_device_binding", default=defaults.ssid_name_to_device_binding): bool,
                vol.Optional("no_publish", default=defaults.no_publish): bool
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
