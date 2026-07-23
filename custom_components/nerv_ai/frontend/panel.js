class NervAIPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <style>
          .container { padding: 24px; font-family: var(--paper-font-body1_-_font-family); color: var(--primary-text-color); }
          h2, h3 { border-bottom: 2px solid var(--divider-color); padding-bottom: 8px; margin-top: 24px; }
          .filter-bar { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; align-items: center; }
          .filter-btn { background: var(--secondary-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); padding: 6px 12px; border-radius: 4px; cursor: pointer; }
          .filter-btn.active { background: var(--primary-color); color: var(--text-primary-color); border-color: var(--primary-color); }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; background: var(--card-background-color); margin-bottom: 24px; }
          th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--divider-color); }
          th { background: var(--secondary-background-color); }
          input[type="text"] { width: 100%; padding: 6px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box; }
          button { background: var(--primary-color); color: var(--text-primary-color); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
          button.danger { background: var(--error-color, #db4437); }
          .section { margin-bottom: 32px; }
        </style>
        <div class="container">
          <h2>NervAI Operasyon ve Yönetim Konsolu</h2>
          <p>Cihaz takma adları ve motor yapılandırması.</p>
          
          <div class="section">
            <h3>Cihaz & Takma Ad Tablosu</h3>
            <div id="filter-container" class="filter-bar"></div>
            <div id="entities-area">Yükleniyor...</div>
          </div>

          <div class="section">
            <h3>Motor Ayarları & Güvenlik</h3>
            <div id="config-area">Yükleniyor...</div>
          </div>
        </div>
      `;
      this.content = this.querySelector(".container");
      this.allEntities = [];
      this.currentDomainFilter = "all";
      this.loadAllData();
    }
  }

  async loadAllData() {
    await this.loadEntities();
    await this.loadConfig();
  }

  async loadEntities() {
    this.allEntities = await this._hass.callWS({ type: "nervai/get_entities" });
    this.renderFilters();
    this.renderTable();
  }

  renderFilters() {
    const filterContainer = this.querySelector("#filter-container");
    const domains = ["all", ...new Set(this.allEntities.map(e => e.domain))];
    
    let html = `<span style="font-weight:500; margin-right:4px;">Domain Filtresi:</span>`;
    domains.forEach(d => {
      const activeClass = this.currentDomainFilter === d ? "active" : "";
      const label = d === "all" ? "Tümü" : d;
      html += `<button class="filter-btn ${activeClass}" onclick="window.nervAIController.setFilter('${d}')">${label}</button>`;
    });
    filterContainer.innerHTML = html;
  }

  setDomainFilter(domain) {
    this.currentDomainFilter = domain;
    this.renderFilters();
    this.renderTable();
  }

  renderTable() {
    const area = this.querySelector("#entities-area");
    const filtered = this.currentDomainFilter === "all" 
      ? this.allEntities 
      : this.allEntities.filter(e => e.domain === this.currentDomainFilter);

    let html = `<table><tr><th>Entity ID</th><th>Orijinal İsim</th><th>Takma Adlar (Virgülle Ayırın)</th><th>Aksiyon</th></tr>`;
    
    if (filtered.length === 0) {
      html += `<tr><td colspan="4" style="text-align:center; padding:20px;">Bu filtreye uygun cihaz bulunamadı.</td></tr>`;
    } else {
      filtered.forEach(e => {
        const aliasesStr = Array.isArray(e.aliases) ? e.aliases.join(", ") : "";
        html += `
          <tr>
            <td>${e.entity_id}</td>
            <td>${e.name}</td>
            <td><input type="text" id="alias-${e.entity_id.replace(/\./g, '_')}" value="${aliasesStr}" placeholder="örn: salon klima, yatak odası"></td>
            <td><button onclick="window.nervAIController.saveAlias('${e.entity_id}')">Kaydet</button></td>
          </tr>`;
      });
    }
    html += `</table>`;
    area.innerHTML = html;
  }

  async saveAlias(entityId) {
    const safeId = entityId.replace(/\./g, '_');
    const inputElem = this.querySelector(`#alias-${safeId}`);
    const val = inputElem ? inputElem.value : "";
    const aliases = val.split(",").map(s => s.trim()).filter(s => s.length > 0);
    
    await this._hass.callWS({
      type: "nervai/set_alias",
      entity_id: entityId,
      aliases: aliases
    });
    
    const entity = this.allEntities.find(e => e.entity_id === entityId);
    if (entity) {
      entity.aliases = aliases;
    }
    alert(`${entityId} için takma adlar güncellendi.`);
    this.renderTable();
  }

  async loadConfig() {
    const conf = await this._hass.callWS({ type: "nervai/get_config" });
    const area = this.querySelector("#config-area");
    
    area.innerHTML = `
      <p><b>Model:</b> ${conf.model}</p>
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

window.nervAIController = {
  setFilter: (d) => document.querySelector("nervai-panel").setDomainFilter(d),
  saveAlias: (id) => document.querySelector("nervai-panel").saveAlias(id),
  resetChat: () => document.querySelector("nervai-panel").resetChat()
};