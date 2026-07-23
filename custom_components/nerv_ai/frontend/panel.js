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
          th { background: var(--secondary-background-color); cursor: pointer; user-select: none; }
          input[type="text"].alias-input { width: 100%; padding: 6px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box; }
          button { background: var(--primary-color); color: var(--text-primary-color); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
          button.danger { background: var(--error-color, #db4437); }
          .section { margin-bottom: 32px; }
          .fact-category { font-weight: bold; text-transform: uppercase; font-size: 11px; padding: 2px 6px; background: var(--secondary-background-color); border-radius: 4px; }
          .badge-new { background: var(--warning-color, #ff9800); color: white; font-size: 10px; padding: 2px 6px; border-radius: 3px; margin-left: 6px; }
          .error-box { background: var(--error-color, #db4437); color: white; padding: 12px; border-radius: 4px; margin: 12px 0; }
          .toast { position: fixed; bottom: 20px; right: 20px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); z-index: 1000; }
        </style>
        <div class="container">
          <h2>NervAI Operasyon ve Yönetim Konsolu</h2>
          <p>Cihaz takma adları, bot hafızası ve sistem ayarları.</p>
          <div id="global-error"></div>

          <div class="section">
            <h3>Cihaz &amp; Takma Ad Tablosu</h3>
            <div class="filter-bar">
              <input type="text" id="entity-search" class="filter-input" placeholder="Cihaz, alan veya alias ara (örn: sensor, klima, salon)...">
            </div>
            <div id="entities-area">Yükleniyor...</div>
          </div>

          <div class="section">
            <h3>Botun Öğrendiği Kurallar &amp; Hafıza (Facts)</h3>
            <div id="facts-area">Yükleniyor...</div>
          </div>

          <div class="section">
            <h3>Motor Ayarları &amp; Güvenlik</h3>
            <div id="config-area">Yükleniyor...</div>
          </div>
        </div>
      `;
      this.content = this.querySelector(".container");
      this.allEntities = [];
      this.allFacts = [];
      this.searchQuery = "";
      this.sortKey = null;
      this.sortAsc = true;

      this.querySelector("#entity-search").addEventListener("input", (e) => {
        this.handleSearch(e.target.value);
      });

      console.log("[NervAI Panel] Bileşen oluşturuldu, veri yükleniyor...");
      this.loadAllData();
    }
  }

  escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  showToast(message) {
    const existing = this.querySelector(".toast");
    if (existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    this.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  showError(context, err) {
    console.error(`[NervAI Panel] ${context} hatası:`, err);
    const box = this.querySelector("#global-error");
    if (box) {
      box.innerHTML = `<div class="error-box">⚠️ ${this.escapeHtml(context)}: ${this.escapeHtml(err?.message || String(err))} (Detay için F12 &gt; Console'a bakın)</div>`;
    }
  }

  async loadAllData() {
    await this.loadEntities();
    await this.loadFacts();
    await this.loadConfig();
  }

  async loadEntities() {
    try {
      this.allEntities = await this._hass.callWS({ type: "nervai/get_entities" });
      console.log(`[NervAI Panel] ${this.allEntities.length} entity yüklendi.`);
      this.renderTable();
    } catch (err) {
      this.showError("Cihaz listesi yüklenemedi", err);
    }
  }

  async loadFacts() {
    try {
      this.allFacts = await this._hass.callWS({ type: "nervai/get_facts" });
      console.log(`[NervAI Panel] ${this.allFacts.length} kural yüklendi.`);
      this.renderFacts();
    } catch (err) {
      this.showError("Kurallar yüklenemedi", err);
    }
  }

  handleSearch(query) {
    this.searchQuery = query.toLowerCase().trim();
    this.renderTable();
  }

  sortBy(key) {
    if (this.sortKey === key) {
      this.sortAsc = !this.sortAsc;
    } else {
      this.sortKey = key;
      this.sortAsc = true;
    }
    this.renderTable();
  }

  renderTable() {
    const area = this.querySelector("#entities-area");
    let filtered = this.allEntities.filter(e => {
      if (!this.searchQuery) return true;
      const matchId = e.entity_id.toLowerCase().includes(this.searchQuery);
      const matchName = (e.name || "").toLowerCase().includes(this.searchQuery);
      const matchDomain = e.domain.toLowerCase().includes(this.searchQuery);
      const matchArea = (e.area || "").toLowerCase().includes(this.searchQuery);
      const matchAlias = e.aliases && e.aliases.some(a => a.toLowerCase().includes(this.searchQuery));
      return matchId || matchName || matchDomain || matchArea || matchAlias;
    });

    if (this.sortKey) {
      filtered = [...filtered].sort((a, b) => {
        const av = (a[this.sortKey] || "").toString().toLowerCase();
        const bv = (b[this.sortKey] || "").toString().toLowerCase();
        return this.sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
    }

    let html = `<table>
      <tr>
        <th data-sort="entity_id">Entity ID</th>
        <th data-sort="name">Orijinal İsim</th>
        <th>Takma Adlar (virgülle ayırın)</th>
        <th>Aksiyon</th>
      </tr>`;

    if (filtered.length === 0) {
      html += `<tr><td colspan="4" style="text-align:center; padding:20px;">Arama kriterine uygun cihaz bulunamadı.</td></tr>`;
    } else {
      filtered.forEach(e => {
        const aliasesStr = Array.isArray(e.aliases) ? e.aliases.join(", ") : "";
        const isNew = !e.aliases || e.aliases.length === 0;
        html += `
          <tr>
            <td>${this.escapeHtml(e.entity_id)}${isNew ? '<span class="badge-new">Yeni</span>' : ''}</td>
            <td>${this.escapeHtml(e.name)}</td>
            <td><input type="text" class="alias-input" id="alias-${e.entity_id.replace(/\./g, '_')}" value="${this.escapeHtml(aliasesStr)}"></td>
            <td><button class="save-alias-btn" data-entity-id="${this.escapeHtml(e.entity_id)}">Kaydet</button></td>
          </tr>`;
      });
    }
    html += `</table>`;
    area.innerHTML = html;

    area.querySelectorAll("th[data-sort]").forEach(th => {
      th.addEventListener("click", () => this.sortBy(th.dataset.sort));
    });

    area.querySelectorAll(".save-alias-btn").forEach(btn => {
      btn.addEventListener("click", () => this.saveAlias(btn.dataset.entityId));
    });

    area.querySelectorAll(".alias-input").forEach(input => {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          const entityId = input.id.replace("alias-", "").replace(/_/g, ".");
          const match = this.allEntities.find(en => en.entity_id.replace(/\./g, '_') === input.id.replace("alias-", ""));
          if (match) this.saveAlias(match.entity_id);
        }
      });
    });
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
          <td><span class="fact-category">${this.escapeHtml(f.category)}</span></td>
          <td>${this.escapeHtml(f.fact_text)}</td>
          <td><code>${this.escapeHtml(f.fact_key)}</code></td>
          <td><button class="danger delete-fact-btn" data-fact-key="${this.escapeHtml(f.fact_key)}">Sil</button></td>
        </tr>`;
    });
    html += `</table>`;
    area.innerHTML = html;

    area.querySelectorAll(".delete-fact-btn").forEach(btn => {
      btn.addEventListener("click", () => this.deleteFact(btn.dataset.factKey));
    });
  }

  async saveAlias(entityId) {
    const safeId = entityId.replace(/\./g, '_');
    const inputElem = this.querySelector(`#alias-${safeId}`);
    const val = inputElem ? inputElem.value : "";
    const aliases = val.split(",").map(s => s.trim()).filter(s => s.length > 0);

    try {
      await this._hass.callWS({ type: "nervai/set_alias", entity_id: entityId, aliases: aliases });
      const entity = this.allEntities.find(e => e.entity_id === entityId);
      if (entity) entity.aliases = aliases;
      this.showToast(`✅ ${entityId} takma adları güncellendi.`);
      this.renderTable();
    } catch (err) {
      this.showError(`${entityId} kaydedilemedi`, err);
    }
  }

  async deleteFact(factKey) {
    if (!confirm(`Bu kural hafızadan silinsin mi? (${factKey})`)) return;
    try {
      await this._hass.callWS({ type: "nervai/delete_fact", fact_key: factKey });
      await this.loadFacts();
      this.showToast("🗑️ Kural hafızadan silindi.");
    } catch (err) {
      this.showError("Kural silinemedi", err);
    }
  }

  async loadConfig() {
    try {
      const conf = await this._hass.callWS({ type: "nervai/get_config" });
      const area = this.querySelector("#config-area");
      area.innerHTML = `
        <p><b>Aktif Sağlayıcı:</b> ${this.escapeHtml(conf.provider)} <em style="color:var(--secondary-text-color)">(değiştirme desteği yakında)</em></p>
        <p><b>Aktif Model:</b> ${this.escapeHtml(conf.model)}</p>
        <button class="danger" id="reset-chat-btn">Yetkili Sohbeti (Chat ID) Sıfırla</button>
      `;
      this.querySelector("#reset-chat-btn").addEventListener("click", () => this.resetChat());
    } catch (err) {
      this.showError("Ayarlar yüklenemedi", err);
    }
  }

  async resetChat() {
    if (!confirm("Yetkili chat oturumu sıfırlansın mı? Bir sonraki /start yazan kişi yeni yetkili olacak.")) return;
    try {
      await this._hass.callWS({ type: "nervai/reset_chat" });
      this.showToast("✅ Chat oturumu sıfırlandı.");
    } catch (err) {
      this.showError("Sıfırlama başarısız", err);
    }
  }
}

customElements.define("nervai-panel", NervAIPanel);