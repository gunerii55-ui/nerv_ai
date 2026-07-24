const STRINGS = {
  tr: {
    sectionEntities: "Cihaz & Takma Ad Tablosu",
    sectionFacts: "Botun Öğrendiği Kurallar & Hafıza",
    sectionConfig: "Motor Ayarları & Güvenlik",
    colEntityId: "Entity ID",
    colBotName: "Botun Belirlediği İsim",
    colAliases: "Takma Adlar",
    colAddAlias: "Takma Ad Ekle",
    colAction: "Onay",
    colCategory: "Kategori",
    colFactText: "Öğrenilen Kural / Bilgi",
    colFactAction: "Aksiyon",
    filterPlaceholder: "Filtrele...",
    noEntities: "Filtreye uygun cihaz bulunamadı.",
    noFacts: "Bot henüz hafızaya özel bir kural kaydetmemiş.",
    resetChat: "Yetkili Sohbeti (Chat ID) Sıfırla",
    activeProvider: "Aktif Sağlayıcı",
    activeModel: "Aktif Model",
    comingSoon: "(değiştirme desteği yakında)",
  },
  en: {
    sectionEntities: "Devices & Alias Table",
    sectionFacts: "Bot's Learned Rules & Memory",
    sectionConfig: "Engine Settings & Security",
    colEntityId: "Entity ID",
    colBotName: "Bot-Assigned Name",
    colAliases: "Aliases",
    colAddAlias: "Add Alias",
    colAction: "Confirm",
    colCategory: "Category",
    colFactText: "Learned Rule / Info",
    colFactAction: "Action",
    filterPlaceholder: "Filter...",
    noEntities: "No devices match the filter.",
    noFacts: "The bot hasn't saved any rules to memory yet.",
    resetChat: "Reset Authorized Chat (Chat ID)",
    activeProvider: "Active Provider",
    activeModel: "Active Model",
    comingSoon: "(switching support coming soon)",
  },
};

class NervAIPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.lang = "tr";
      this.sectionsOpen = { entities: false, facts: false };
      this.colFilters = { entity_id: "", name: "", aliases: "" };
      this.factFilter = "";
      this.sortKey = null;
      this.sortAsc = true;
      this.editingFactKey = null;

      this.innerHTML = `
        <style>
          .container { padding: 24px; font-family: var(--paper-font-body1_-_font-family); color: var(--primary-text-color); }
          .topbar { display: flex; justify-content: flex-end; gap: 4px; margin-bottom: 8px; }
          .lang-btn { padding: 4px 10px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); border-radius: 4px; cursor: pointer; font-size: 12px; }
          .lang-btn.active { background: var(--primary-color); color: var(--text-primary-color); }
          .section-header { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; border-bottom: 2px solid var(--divider-color); padding-bottom: 8px; margin-top: 24px; }
          .section-header .chevron { transition: transform 0.2s ease; display: inline-block; }
          .section-header.open .chevron { transform: rotate(90deg); }
          .section-body { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
          .section-body.open { max-height: 4000px; }
          .filter-bar { margin: 16px 0; display: flex; gap: 12px; flex-wrap: wrap; }
          .filter-input { flex: 1; min-width: 140px; padding: 6px 10px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; font-size: 13px; }
          table { width: 100%; border-collapse: collapse; margin-top: 8px; background: var(--card-background-color); margin-bottom: 16px; }
          th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--divider-color); font-size: 14px; }
          th { background: var(--secondary-background-color); cursor: pointer; user-select: none; }
          input[type="text"].alias-input { width: 100%; padding: 6px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box; }
          button.icon-btn { background: var(--primary-color); color: white; border: none; width: 32px; height: 32px; border-radius: 4px; cursor: pointer; font-size: 14px; }
          button.pencil-btn { background: none; border: none; cursor: pointer; font-size: 15px; }
          button.danger { background: var(--error-color, #db4437); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
          .badge-new { background: var(--warning-color, #ff9800); color: white; font-size: 10px; padding: 2px 6px; border-radius: 3px; margin-left: 6px; }
          .error-box { background: var(--error-color, #db4437); color: white; padding: 12px; border-radius: 4px; margin: 12px 0; }
          .toast { position: fixed; bottom: 20px; right: 20px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); z-index: 1000; }
        </style>
        <div class="container">
          <div class="topbar">
            <button class="lang-btn" data-lang="tr">TR</button>
            <button class="lang-btn" data-lang="en">EN</button>
          </div>
          <div id="global-error"></div>

          <div class="section-header" id="toggle-entities"><span class="chevron">▶</span><span id="title-entities"></span></div>
          <div class="section-body" id="body-entities">
            <div class="filter-bar" id="entities-filter-bar"></div>
            <div id="entities-area">…</div>
          </div>

          <div class="section-header" id="toggle-facts"><span class="chevron">▶</span><span id="title-facts"></span></div>
          <div class="section-body" id="body-facts">
            <div class="filter-bar" id="facts-filter-bar"></div>
            <div id="facts-area">…</div>
          </div>

          <h3 id="title-config" style="border-bottom:2px solid var(--divider-color); padding-bottom:8px; margin-top:24px;"></h3>
          <div id="config-area">…</div>
        </div>
      `;
      this.content = this.querySelector(".container");

      this.querySelectorAll(".lang-btn").forEach(btn => {
        btn.addEventListener("click", () => { this.lang = btn.dataset.lang; this.rerenderAll(); });
      });
      this.querySelector("#toggle-entities").addEventListener("click", () => this.toggleSection("entities"));
      this.querySelector("#toggle-facts").addEventListener("click", () => this.toggleSection("facts"));

      this.allEntities = [];
      this.allFacts = [];
      console.log("[NervAI Panel] Bileşen oluşturuldu, veri yükleniyor...");
      this.loadAllData();
    }
  }

  t(key) { return STRINGS[this.lang][key]; }

  escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  showToast(msg) {
    const existing = this.querySelector(".toast");
    if (existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = msg;
    this.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  showError(context, err) {
    console.error(`[NervAI Panel] ${context}:`, err);
    const box = this.querySelector("#global-error");
    if (box) box.innerHTML = `<div class="error-box">⚠️ ${this.escapeHtml(context)}: ${this.escapeHtml(err?.message || String(err))}</div>`;
  }

  toggleSection(key) {
    this.sectionsOpen[key] = !this.sectionsOpen[key];
    const header = this.querySelector(`#toggle-${key}`);
    const body = this.querySelector(`#body-${key}`);
    header.classList.toggle("open", this.sectionsOpen[key]);
    body.classList.toggle("open", this.sectionsOpen[key]);
  }

  rerenderAll() {
    this.querySelector("#title-entities").textContent = this.t("sectionEntities");
    this.querySelector("#title-facts").textContent = this.t("sectionFacts");
    this.querySelector("#title-config").textContent = this.t("sectionConfig");
    this.querySelectorAll(".lang-btn").forEach(b => b.classList.toggle("active", b.dataset.lang === this.lang));
    this.renderEntityFilterBar();
    this.renderFactFilterBar();
    this.renderTable();
    this.renderFacts();
    this.renderConfigLabels();
  }

  async loadAllData() {
    await this.loadEntities();
    await this.loadFacts();
    await this.loadConfig();
    this.rerenderAll();
  }

  async loadEntities() {
    try {
      this.allEntities = await this._hass.callWS({ type: "nervai/get_entities" });
    } catch (err) { this.showError("Cihaz listesi yüklenemedi", err); }
  }

  async loadFacts() {
    try {
      this.allFacts = await this._hass.callWS({ type: "nervai/get_facts" });
    } catch (err) { this.showError("Kurallar yüklenemedi", err); }
  }

  renderEntityFilterBar() {
    const bar = this.querySelector("#entities-filter-bar");
    bar.innerHTML = `
      <input type="text" class="filter-input" data-col="entity_id" placeholder="Entity ID ${this.t('filterPlaceholder')}" value="${this.escapeHtml(this.colFilters.entity_id)}">
      <input type="text" class="filter-input" data-col="name" placeholder="${this.t('colBotName')}..." value="${this.escapeHtml(this.colFilters.name)}">
      <input type="text" class="filter-input" data-col="aliases" placeholder="${this.t('colAliases')}..." value="${this.escapeHtml(this.colFilters.aliases)}">
    `;
    bar.querySelectorAll(".filter-input").forEach(inp => {
      inp.addEventListener("input", () => { this.colFilters[inp.dataset.col] = inp.value.toLowerCase(); this.renderTable(); });
    });
  }

  renderFactFilterBar() {
    const bar = this.querySelector("#facts-filter-bar");
    bar.innerHTML = `<input type="text" class="filter-input" id="fact-filter-input" placeholder="${this.t('filterPlaceholder')}" value="${this.escapeHtml(this.factFilter)}">`;
    bar.querySelector("#fact-filter-input").addEventListener("input", (e) => { this.factFilter = e.target.value.toLowerCase(); this.renderFacts(); });
  }

  sortBy(key) {
    if (this.sortKey === key) this.sortAsc = !this.sortAsc; else { this.sortKey = key; this.sortAsc = true; }
    this.renderTable();
  }

  renderTable() {
    const area = this.querySelector("#entities-area");
    let filtered = this.allEntities.filter(e => {
      const aliasesStr = (e.aliases || []).join(", ").toLowerCase();
      if (this.colFilters.entity_id && !e.entity_id.toLowerCase().includes(this.colFilters.entity_id)) return false;
      if (this.colFilters.name && !(e.name || "").toLowerCase().includes(this.colFilters.name)) return false;
      if (this.colFilters.aliases && !aliasesStr.includes(this.colFilters.aliases)) return false;
      return true;
    });

    if (this.sortKey) {
      filtered = [...filtered].sort((a, b) => {
        const av = (a[this.sortKey] || "").toString().toLowerCase();
        const bv = (b[this.sortKey] || "").toString().toLowerCase();
        return this.sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
    }

    let html = `<table><tr>
      <th data-sort="entity_id">${this.t("colEntityId")}</th>
      <th data-sort="name">${this.t("colBotName")}</th>
      <th>${this.t("colAliases")}</th>
      <th>${this.t("colAddAlias")}</th>
      <th>${this.t("colAction")}</th>
    </tr>`;

    if (filtered.length === 0) {
      html += `<tr><td colspan="5" style="text-align:center; padding:20px;">${this.t("noEntities")}</td></tr>`;
    } else {
      filtered.forEach(e => {
        const aliasesStr = Array.isArray(e.aliases) && e.aliases.length ? e.aliases.join(", ") : "—";
        const isNew = !e.aliases || e.aliases.length === 0;
        html += `<tr>
          <td>${this.escapeHtml(e.entity_id)}${isNew ? `<span class="badge-new">${this.lang === "tr" ? "Yeni" : "New"}</span>` : ""}</td>
          <td>${this.escapeHtml(e.name)}</td>
          <td>${this.escapeHtml(aliasesStr)}</td>
          <td><input type="text" class="alias-input" id="newalias-${e.entity_id.replace(/\./g, "_")}" placeholder="ör: mutfak ışığı"></td>
          <td><button class="icon-btn" data-entity-id="${this.escapeHtml(e.entity_id)}">✓</button></td>
        </tr>`;
      });
    }
    html += `</table>`;
    area.innerHTML = html;

    area.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", () => this.sortBy(th.dataset.sort)));
    area.querySelectorAll(".icon-btn").forEach(btn => btn.addEventListener("click", () => this.addAlias(btn.dataset.entityId)));
    area.querySelectorAll(".alias-input").forEach(input => {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          const entityId = input.id.replace("newalias-", "").replace(/_/g, ".");
          const match = this.allEntities.find(en => en.entity_id.replace(/\./g, "_") === input.id.replace("newalias-", ""));
          if (match) this.addAlias(match.entity_id);
        }
      });
    });
  }

  async addAlias(entityId) {
    const safeId = entityId.replace(/\./g, "_");
    const input = this.querySelector(`#newalias-${safeId}`);
    const newAlias = input ? input.value.trim() : "";
    if (!newAlias) return;

    const entity = this.allEntities.find(e => e.entity_id === entityId);
    const current = (entity && entity.aliases) ? [...entity.aliases] : [];
    if (!current.includes(newAlias)) current.push(newAlias);

    try {
      await this._hass.callWS({ type: "nervai/set_alias", entity_id: entityId, aliases: current });
      if (entity) entity.aliases = current;
      this.showToast(`✅ "${newAlias}" eklendi.`);
      this.renderTable();
    } catch (err) { this.showError(`${entityId} kaydedilemedi`, err); }
  }

  renderFacts() {
    const area = this.querySelector("#facts-area");
    const filtered = this.allFacts.filter(f =>
      !this.factFilter ||
      f.fact_text.toLowerCase().includes(this.factFilter) ||
      f.category.toLowerCase().includes(this.factFilter)
    );

    if (!filtered.length) {
      area.innerHTML = `<p style="color: var(--secondary-text-color);">${this.t("noFacts")}</p>`;
      return;
    }

    let html = `<table><tr><th>${this.t("colCategory")}</th><th>${this.t("colFactText")}</th><th>${this.t("colFactAction")}</th></tr>`;
    filtered.forEach(f => {
      const isEditing = this.editingFactKey === f.fact_key;
      html += `<tr>
        <td>${this.escapeHtml(f.category)}</td>
        <td>${isEditing
          ? `<input type="text" class="alias-input fact-edit-input" data-fact-key="${this.escapeHtml(f.fact_key)}" value="${this.escapeHtml(f.fact_text)}">`
          : this.escapeHtml(f.fact_text)}</td>
        <td>
          ${isEditing
            ? `<button class="icon-btn fact-save-btn" data-fact-key="${this.escapeHtml(f.fact_key)}" data-category="${this.escapeHtml(f.category)}">✓</button>`
            : `<button class="pencil-btn fact-edit-btn" data-fact-key="${this.escapeHtml(f.fact_key)}">✏️</button>
               <button class="danger delete-fact-btn" data-fact-key="${this.escapeHtml(f.fact_key)}">🗑️</button>`}
        </td>
      </tr>`;
    });
    html += `</table>`;
    area.innerHTML = html;

    area.querySelectorAll(".fact-edit-btn").forEach(btn => btn.addEventListener("click", () => { this.editingFactKey = btn.dataset.factKey; this.renderFacts(); }));
    area.querySelectorAll(".fact-save-btn").forEach(btn => btn.addEventListener("click", () => this.saveFactEdit(btn.dataset.factKey, btn.dataset.category)));
    area.querySelectorAll(".delete-fact-btn").forEach(btn => btn.addEventListener("click", () => this.deleteFact(btn.dataset.factKey)));
  }

  async saveFactEdit(factKey, category) {
    const input = this.querySelector(`.fact-edit-input[data-fact-key="${factKey}"]`);
    const newText = input ? input.value.trim() : "";
    if (!newText) return;
    try {
      await this._hass.callWS({ type: "nervai/update_fact", fact_key: factKey, category: category, fact_text: newText });
      const fact = this.allFacts.find(f => f.fact_key === factKey);
      if (fact) fact.fact_text = newText;
      this.editingFactKey = null;
      this.showToast("✅ Kural güncellendi.");
      this.renderFacts();
    } catch (err) { this.showError("Kural güncellenemedi", err); }
  }

  async deleteFact(factKey) {
    if (!confirm(`Bu kural silinsin mi?`)) return;
    try {
      await this._hass.callWS({ type: "nervai/delete_fact", fact_key: factKey });
      await this.loadFacts();
      this.renderFacts();
      this.showToast("🗑️ Kural silindi.");
    } catch (err) { this.showError("Kural silinemedi", err); }
  }

  async loadConfig() {
    try { this._conf = await this._hass.callWS({ type: "nervai/get_config" }); }
    catch (err) { this.showError("Ayarlar yüklenemedi", err); }
  }

  renderConfigLabels() {
    const area = this.querySelector("#config-area");
    const c = this._conf || {};
    area.innerHTML = `
      <p><b>${this.t("activeProvider")}:</b> ${this.escapeHtml(c.provider)} <em style="color:var(--secondary-text-color)">${this.t("comingSoon")}</em></p>
      <p><b>${this.t("activeModel")}:</b> ${this.escapeHtml(c.model)}</p>
      <button class="danger" id="reset-chat-btn">${this.t("resetChat")}</button>
    `;
    this.querySelector("#reset-chat-btn").addEventListener("click", () => this.resetChat());
  }

  async resetChat() {
    if (!confirm("Emin misiniz?")) return;
    try { await this._hass.callWS({ type: "nervai/reset_chat" }); this.showToast("✅ Sıfırlandı."); }
    catch (err) { this.showError("Sıfırlama başarısız", err); }
  }
}

customElements.define("nervai-panel", NervAIPanel);