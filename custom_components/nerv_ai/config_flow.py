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
    async def async_step_init(self, user_input=None):
        errors = {}
        registry = er.async_get(self.hass)
        
        if user_input is not None:
            for entity_id, new_aliases in user_input.items():
                entry = registry.async_get(entity_id)
                if entry and new_aliases:
                    existing = set(entry.aliases) if entry.aliases else set()
                    if isinstance(new_aliases, list):
                        for a in new_aliases:
                            existing.add(a.strip())
                    else:
                        existing.add(new_aliases.strip())
                    registry.async_update_entity(entity_id, aliases=existing)
            return self.async_create_entry(title="", data={})

        valid_domains = [
            "light", "switch", "cover", "lock", "climate", 
            "fan", "alarm_control_panel", "media_player", "vacuum", "sensor"
        ]
        
        schema_fields = {}
        for state in self.hass.states.async_all():
            if state.domain in valid_domains:
                entry = registry.async_get(state.entity_id)
                current_aliases = list(entry.aliases) if entry and entry.aliases else [state.name]
                
                schema_fields[vol.Optional(state.entity_id, default=current_aliases)] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=current_aliases,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        multiple=True
                    )
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
            errors=errors
        )