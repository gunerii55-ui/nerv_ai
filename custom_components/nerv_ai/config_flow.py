"""Config flow for NervAI integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_TELEGRAM_TOKEN = "telegram_token"
CONF_OPENAI_API_KEY = "openai_api_key"

class NervAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NervAI."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # TODO: Burada girilen API Key ve Token'ın doğruluğu (ping atılarak) test edilebilir.
            # Şimdilik doğrudan kabul ediyoruz.
            return self.async_create_entry(title="NervAI", data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_TELEGRAM_TOKEN): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_OPENAI_API_KEY): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )