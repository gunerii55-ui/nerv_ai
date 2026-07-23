import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

class NervAIConfigFlow(config_entries.ConfigFlow, domain="nervai"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="NervAI", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return NervAIOptionsFlow(config_entry)


class NervAIOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            entity_id = user_input.get("entity_id")
            new_alias = user_input.get("alias")
            
            if entity_id and new_alias:
                registry = er.async_get(self.hass)
                entry = registry.async_get(entity_id)
                if entry:
                    existing = set(entry.aliases) if entry.aliases else set()
                    existing.add(new_alias.strip())
                    registry.async_update_entity(entity_id, aliases=existing)
                    
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=[
                            "light", "switch", "cover", "lock", "climate", 
                            "fan", "alarm_control_panel", "media_player", 
                            "vacuum", "sensor", "binary_sensor", "camera"
                        ]
                    )
                ),
                vol.Required("alias"): selector.TextSelector(),
            })
        )