class NervAIPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <style>
          .container { padding: 24px; font-family: var(--paper-font-body1_-_font-family); color: var(--primary-text-color); }
          h2, h3 { border-bottom: 2px solid var(--divider-color); padding-bottom: 8px; margin-top: 24px; }
          .filter-bar { margin: 16px 0; }
          .filter-input { width: 100%; max-width: 400px; padding: 8px 12px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box; font-size: 14px; }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; background: var(--card-background-color); margin-bottom: 24px; }
          th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--divider-color); }
          th { background: var(--secondary-background-color); }
          input[type="text"].alias-input { width: 100%; padding: 6px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box; }
          button { background: var(--primary-color); color: var(--text-primary-color); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
          button.danger { background: var(--error-color, #db4437); }
          .section { margin-bottom: 32px; }
          .fact-category { font-weight: bold; text-transform: uppercase; font-size: 11px; padding: 2px 6px; background: var(--secondary-background-color); border-radius: 4px; }
        </style>
        <div class="container">
          <h2>NervAI Operasyon ve Yönetim Konsolu</h2>
          <p>Cihaz takma adları, bot hafızası ve sistem ayarları.</p>
          
          <div class="section">
            <h3>Cihaz & Takma Ad Tablosu</h3>
            <div class="filter-bar">
              <input type="text" id="entity-search" class="filter-input" placeholder="Cihaz veya alias ara (örn: sensor, klima)..." oninput="window.nervAIController.handleSearch(this.value)">
            </div>
            <div id="entities-area">Yükleniyor...</div>
          </div>

          <div class="section">
            <h3>Botun Öğrendiği Kurallar & Hafıza (Facts)</h3>
            <div id="facts-area">Yükleniyor...</div>
          </div>

          <div class="section">
            <h3>Motor Ayarları & Güvenlik</h3>
            <div id="config-area">Yükleniyor...</div>
          </div>
        </div>
      `;
      this.content = this.querySelector(".container");
      this.allEntities = [];
      this.allFacts = [];
      this.searchQuery = "";
      this.loadAllData();
    }
  }

  async loadAllData() {
    await this.loadEntities();
    await this.loadFacts();
    await this.loadConfig();
  }

  async loadEntities() {
    this.allEntities = await this._hass.callWS({ type: "nervai/get_entities" });
    this.renderTable();
  }

  async loadFacts() {
    this.allFacts = await this._hass.callWS({ type: "nervai/get_facts" });
    this.renderFacts();
  }

  handleSearch(query) {
    this.searchQuery = query.toLowerCase().trim();
    this.renderTable();
  }

  renderTable() {
    const area = this.querySelector("#entities-area");
    const filtered = this.allEntities.filter(e => {
      if (!this.searchQuery) return true;
      const matchId = e.entity_id.toLowerCase().includes(this.searchQuery);
      const matchName = e.name.toLowerCase().includes(this.searchQuery);
      const matchDomain = e.domain.toLowerCase().includes(this.searchQuery);
      const matchAlias = e.aliases && e.aliases.some(a => a.toLowerCase().includes(this.searchQuery));
      return matchId || matchName || matchDomain || matchAlias;
    });

    let html = `<table><tr><th>Entity ID</th><th>Orijinal İsim</th><th>Takma Adlar (Virgülle Ayırın)</th><th>Aksiyon</th></tr>`;
    
    if (filtered.length === 0) {
      html += `<tr><td colspan="4" style="text-align:center; padding:20px;">Arama kriterine uygun cihaz bulunamadı.</td></tr>`;
    } else {
      filtered.forEach(e => {
        const aliasesStr = Array.isArray(e.aliases) ? e.aliases.join(", ") : "";
        html += `
          <tr>
            <td>${e.entity_id}</td>
            <td>${e.name}</td>
            <td><input type="text" class="alias-input" id="alias-${e.entity_id.replace(/\./g, '_')}" value="${aliasesStr}"></td>
            <td><button onclick="window.nervAIController.saveAlias('${e.entity_id}')">Kaydet</button></td>
          </tr>`;
      });
    }
    html += `</table>`;
    area.innerHTML = html;
  }

  renderFacts() {
    const area = this.querySelector("#facts-area");
    if (!this.allFacts || this.allFacts.length === 0) {
      area.innerHTML = `<p style="color: var(--secondary-text-color);">Bot henüz hafızaya özel bir kural veya eşleme kaydetmemiş.</p>`;
      return;
    }

    let html = `<table><tr><th>Kategori</th><th>Öğrenilen Kural / Bilgi</th><th>Anahtar (Key)</th><th>Aksiyon</th></tr>`;
    this.allFacts.forEach(f => {
      html += `
        <tr>
          <td><span class="fact-category">${f.category}</span></td>
          <td>${f.fact_text}</td>
          <td><code>${f.fact_key}</code></td>
          <td><button class="danger" onclick="window.nervAIController.deleteFact('${f.fact_key}')">Sil</button></td>
        </tr>`;
    });
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
    alert(`${entityId} takma adları güncellendi.`);
    this.renderTable();
  }

  async deleteFact(factKey) {
    if (confirm(`Bu kural hafızadan silinsin mi? (${factKey})`)) {
      await this._hass.callWS({
        type: "nervai/delete_fact",
        fact_key: factKey
      });
      await this.loadFacts();
      alert("Kural hafızadan silindi.");
    }
  }

  async loadConfig() {
    const conf = await this._hass.callWS({ type: "nervai/get_config" });
    const area = this.querySelector("#config-area");
    
    area.innerHTML = `
      <p><b>Aktif Model:</b> ${conf.model}</p>
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
  handleSearch: (q) => document.querySelector("nervai-panel").handleSearch(q),
  saveAlias: (id) => document.querySelector("nervai-panel").saveAlias(id),
  deleteFact: (key) => document.querySelector("nervai-panel").deleteFact(key),
  resetChat: () => document.querySelector("nervai-panel").resetChat()
};