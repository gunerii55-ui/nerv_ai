class NervAIPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <style>
          .container { padding: 24px; font-family: var(--paper-font-body1_-_font-family); color: var(--primary-text-color); }
          h2, h3 { border-bottom: 2px solid var(--divider-color); padding-bottom: 8px; margin-top: 24px; }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; background: var(--card-background-color); margin-bottom: 24px; }
          th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--divider-color); }
          th { background: var(--secondary-background-color); }
          input[type="text"] { width: 100%; padding: 6px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; }
          button { background: var(--primary-color); color: var(--text-primary-color); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 8px; }
          button.danger { background: var(--error-color, #db4437); }
          .section { margin-bottom: 32px; }
        </style>
        <div class="container">
          <h2>NervAI Operasyon ve Yönetim Konsolu</h2>
          <p>Cihaz takma adları, kurallar ve motor yapılandırması.</p>
          
          <div class="section">
            <h3>Cihaz & Takma Ad Tablosu</h3>
            <div id="entities-area">Yükleniyor...</div>
          </div>

          <div class="section">
            <h3>Motor Ayarları & Güvenlik</h3>
            <div id="config-area">Yükleniyor...</div>
          </div>
        </div>
      `;
      this.content = this.querySelector(".container");
      this.loadAllData();
    }
  }

  async loadAllData() {
    await this.loadEntities();
    await this.loadConfig();
  }

  async loadEntities() {
    const entities = await this._hass.callWS({ type: "nervai/get_entities" });
    const area = this.querySelector("#entities-area");
    
    let html = `<table><tr><th>Entity ID</th><th>Orijinal İsim</th><th>Domain</th><th>Takma Adlar (Virgülle Ayırın)</th><th>Aksiyon</th></tr>`;
    entities.forEach(e => {
      html += `
        <tr>
          <td>${e.entity_id}</td>
          <td>${e.name}</td>
          <td>${e.domain}</td>
          <td><input type="text" id="alias-${e.entity_id.replace('.', '_')}" value="${e.aliases.join(", ")}"></td>
          <td><button onclick="window.nervAIController.saveAlias('${e.entity_id}')">Kaydet</button></td>
        </tr>`;
    });
    html += `</table>`;
    area.innerHTML = html;
  }

  async saveAlias(entityId) {
    const inputId = `#alias-${entityId.replace('.', '_')}`;
    const val = this.querySelector(inputId).value;
    const aliases = val.split(",").map(s => s.trim()).filter(s => s.length > 0);
    
    await this._hass.callWS({
      type: "nervai/set_alias",
      entity_id: entityId,
      aliases: aliases
    });
    alert(`${entityId} için takma adlar güncellendi.`);
    this.loadEntities();
  }

  async loadConfig() {
    const conf = await this._hass.callWS({ type: "nervai/get_config" });
    const area = this.querySelector("#config-area");
    
    area.innerHTML = `
      <p><b>Sağlayıcı:</b> ${conf.provider} | <b>Model:</b> ${conf.model}</p>
      <button class="danger" onclick="window.nervAIController.resetChat()">Yetkili Sohbeti (Chat ID) Sıfırla</button>
    `;
  }

  async resetChat() {
    if (confirm("Yetkili chat oturumu sıfırlansın mı?")) {
      await this._hass.callWS({ type: "nervai/reset_chat" });
      alert("Chat oturumu sıfırlandı.");
    }
  }
}

customElements.define("nervai-panel", NervAIPanel);
// Global controller bridge for inline HTML click handlers
window.nervAIController = {
  saveAlias: (id) => document.querySelector("nervai-panel").saveAlias(id),
  resetChat: () => document.querySelector("nervai-panel").resetChat()
};