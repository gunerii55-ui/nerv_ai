import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

class NervAIConfigFlow(config_entries.ConfigFlow, domain="nerv_ai"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="NervAI", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return NervAIOptionsFlow()


class NervAIOptionsFlow(config_entries.OptionsFlow):
    def __init__(self):
        self.selected_entity = None

    async def async_step_init(self, user_input=None):
        """Adım 1: Düzenlenecek cihazı seç."""
        errors = {}
        if user_input is not None:
            self.selected_entity = user_input.get("entity_id")
            return await self.async_step_edit_aliases()

        valid_domains = [
            "light", "switch", "cover", "lock", "climate", 
            "fan", "alarm_control_panel", "media_player", "vacuum", "sensor"
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=valid_domains)
                )
            }),
            errors=errors
        )

    async def async_step_edit_aliases(self, user_input=None):
        """Adım 2: Seçilen cihazın takma adlarını yönet."""
        registry = er.async_get(self.hass)
        entry = registry.async_get(self.selected_entity)
        current_aliases = list(entry.aliases) if entry and entry.aliases else []

        if user_input is not None:
            new_alias = user_input.get("new_alias")
            if new_alias and entry:
                existing = set(entry.aliases) if entry.aliases else set()
                existing.add(new_alias.strip())
                registry.async_update_entity(self.selected_entity, aliases=existing)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_aliases",
            data_schema=vol.Schema({
                vol.Optional("current_aliases", default=", ".join(current_aliases)): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required("new_alias"): selector.TextSelector(),
            })
        )