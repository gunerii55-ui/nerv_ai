const STRINGS = {
  tr: {
    sectionEntities: "Cihaz & Takma Ad Tablosu", sectionFacts: "Botun Öğrendiği Kurallar & Hafıza",
    sectionPending: "Bekleyen Onaylar", sectionHealth: "Sistem Durumu", sectionUsage: "Son 7 Gün Kullanım",
    sectionConfig: "Bağlantı & Motor Ayarları",
    colEntityId: "Entity ID", colName: "Belirlenen İsim", colAddAlias: "Takma Ad Ekle", colAction: "Onay",
    colCategory: "Kategori", colFactText: "Öğrenilen Kural / Bilgi", colFactAction: "Aksiyon",
    filterPlaceholder: "Filtrele...", clearFilter: "Temizle", noEntities: "Filtreye uygun cihaz bulunamadı.", noFacts: "Bot henüz hafızaya özel bir kural kaydetmemiş.",
    noPending: "Bekleyen onay yok.", noUsage: "Henüz kullanım verisi birikmedi.",
    cleanupAliases: "🧹 Bozuk Takma Adlarını Temizle", clearAllFacts: "🗑️ Tüm Kuralları Temizle",
    telegramToken: "Telegram Bot Token", openaiKey: "OpenAI API Key", model: "Model", save: "Kaydet", testConn: "🔌 Bağlantıyı Test Et",
    confirm: "✅ Onayla", cancel: "❌ İptal", botStatus: "Bot Durumu", online: "Çevrimiçi", offline: "Çevrimdışı",
    dbSize: "Veritabanı Boyutu", totalActions: "Toplam Kayıtlı İşlem", onlyExposed: "Sadece expose edilenler", allEntities: "Tümü",
    lastUpdated: "Son güncelleme",
  },
  en: {
    sectionEntities: "Devices & Alias Table", sectionFacts: "Bot's Learned Rules & Memory",
    sectionPending: "Pending Confirmations", sectionHealth: "System Status", sectionUsage: "Last 7 Days Usage",
    sectionConfig: "Connection & Engine Settings",
    colEntityId: "Entity ID", colName: "Assigned Name", colAddAlias: "Add Alias", colAction: "Confirm",
    colCategory: "Category", colFactText: "Learned Rule / Info", colFactAction: "Action",
    filterPlaceholder: "Filter...", clearFilter: "Clear", noEntities: "No devices match.", noFacts: "No rules saved yet.",
    noPending: "No pending confirmations.", noUsage: "No usage data yet.",
    cleanupAliases: "🧹 Clean Up Broken Aliases", clearAllFacts: "🗑️ Clear All Rules",
    telegramToken: "Telegram Bot Token", openaiKey: "OpenAI API Key", model: "Model", save: "Save", testConn: "🔌 Test Connection",
    confirm: "✅ Confirm", cancel: "❌ Cancel", botStatus: "Bot Status", online: "Online", offline: "Offline",
    dbSize: "Database Size", totalActions: "Total Logged Actions", onlyExposed: "Exposed only", allEntities: "All",
    lastUpdated: "Last updated",
  },
};

class NervAIPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.lang = "tr";
      this.sectionsOpen = { entities: false, facts: false, pending: true, health: true, usage: false };
      this.openFilterCol = null;
      this.colFilters = { entity_id: "", name: "" };
      this.factFilter = "";
      this.sortKey = null; this.sortAsc = true;
      this.editingFactKey = null;
      this.onlyExposed = true;

      this.innerHTML = `
        <style>
          .container { padding: 24px; font-family: var(--paper-font-body1_-_font-family); color: var(--primary-text-color); }
          .topbar { display:flex; justify-content:flex-end; gap:4px; margin-bottom:8px; }
          .lang-btn { padding:4px 10px; border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); border-radius:4px; cursor:pointer; font-size:12px; }
          .lang-btn.active { background:var(--primary-color); color:white; }
          .section-header { display:flex; align-items:center; gap:8px; cursor:pointer; user-select:none; border-bottom:2px solid var(--divider-color); padding-bottom:8px; margin-top:24px; }
          .section-header .chevron { transition:transform .2s ease; display:inline-block; }
          .section-header.open .chevron { transform:rotate(90deg); }
          .section-body { max-height:0; overflow:hidden; transition:max-height .3s ease; }
          .section-body.open { max-height:6000px; overflow:visible; }
          .action-bar { margin:12px 0; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
          table { width:100%; border-collapse:collapse; margin-top:8px; background:var(--card-background-color); margin-bottom:16px; }
          th, td { padding:10px 12px; text-align:left; border-bottom:1px solid var(--divider-color); font-size:14px; }
          th { background:var(--secondary-background-color); position:relative; }
          th .th-label { cursor:pointer; }
          th .filter-icon { cursor:pointer; margin-left:6px; opacity:.6; }
          th .filter-icon.active { opacity:1; color:var(--primary-color); }
          .filter-popover { position:absolute; top:100%; left:0; background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:4px; padding:8px; z-index:10; box-shadow:0 2px 8px rgba(0,0,0,.3); min-width:180px; }
          .filter-popover input { width:100%; padding:6px; box-sizing:border-box; margin-bottom:6px; background:var(--primary-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); border-radius:4px; }
          input[type="text"].alias-input, input[type="password"].cfg-input, input[type="text"].cfg-input { width:100%; padding:6px; background:var(--card-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); border-radius:4px; box-sizing:border-box; }
          button.icon-btn { background:var(--primary-color); color:white; border:none; padding:8px 14px; border-radius:4px; cursor:pointer; }
          button.pencil-btn { background:none; border:none; cursor:pointer; font-size:15px; }
          button.danger { background:var(--error-color,#db4437); color:white; border:none; padding:6px 12px; border-radius:4px; cursor:pointer; }
          button.secondary { background:var(--secondary-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); padding:6px 12px; border-radius:4px; cursor:pointer; }
          .badge-new { background:var(--warning-color,#ff9800); color:white; font-size:10px; padding:2px 6px; border-radius:3px; margin-left:6px; }
          .count-badge { background:var(--secondary-background-color); border-radius:10px; padding:1px 8px; font-size:12px; margin-left:6px; }
          .error-box { background:var(--error-color,#db4437); color:white; padding:12px; border-radius:4px; margin:12px 0; }
          .toast { position:fixed; bottom:20px; right:20px; background:var(--card-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); padding:12px 20px; border-radius:4px; box-shadow:0 2px 8px rgba(0,0,0,.3); z-index:1000; }
          .cfg-form { display:flex; flex-direction:column; gap:12px; max-width:420px; }
          .cfg-form label { font-size:13px; font-weight:bold; }
          .health-grid { display:flex; gap:16px; flex-wrap:wrap; margin:12px 0; }
          .health-card { background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:6px; padding:12px 18px; min-width:160px; }
          .health-card .label { font-size:12px; color:var(--secondary-text-color); }
          .health-card .value { font-size:20px; font-weight:bold; }
          .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }
          .dot.on { background:#4caf50; } .dot.off { background:#db4437; }
          .pending-card { background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:6px; padding:12px 16px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; }
          footer.nervai-footer { margin-top:32px; padding-top:12px; border-top:1px solid var(--divider-color); font-size:12px; color:var(--secondary-text-color); }
          mark { background:#ffe082; color:inherit; }
        </style>
        <div class="container">
          <div class="topbar"><button class="lang-btn" data-lang="tr">TR</button><button class="lang-btn" data-lang="en">EN</button></div>
          <div id="global-error"></div>

          <div class="section-header" id="toggle-health"><span class="chevron">▶</span><span id="title-health"></span></div>
          <div class="section-body" id="body-health"><div id="health-area">…</div></div>

          <div class="section-header" id="toggle-pending"><span class="chevron">▶</span><span id="title-pending"></span><span class="count-badge" id="count-pending"></span></div>
          <div class="section-body" id="body-pending"><div id="pending-area">…</div></div>

          <div class="section-header" id="toggle-entities"><span class="chevron">▶</span><span id="title-entities"></span><span class="count-badge" id="count-entities"></span></div>
          <div class="section-body" id="body-entities">
            <div class="action-bar">
              <button class="secondary" id="cleanup-aliases-btn"></button>
              <label style="font-size:13px;"><input type="checkbox" id="only-exposed-toggle" checked> <span id="only-exposed-label"></span></label>
            </div>
            <div id="entities-area">…</div>
          </div>

          <div class="section-header" id="toggle-facts"><span class="chevron">▶</span><span id="title-facts"></span><span class="count-badge" id="count-facts"></span></div>
          <div class="section-body" id="body-facts">
            <div class="action-bar">
              <input type="text" class="alias-input" id="fact-filter-input" style="max-width:240px" placeholder="">
              <button class="danger" id="clear-facts-btn"></button>
            </div>
            <div id="facts-area">…</div>
          </div>

          <div class="section-header" id="toggle-usage"><span class="chevron">▶</span><span id="title-usage"></span></div>
          <div class="section-body" id="body-usage"><div id="usage-area">…</div></div>

          <h3 id="title-config" style="border-bottom:2px solid var(--divider-color); padding-bottom:8px; margin-top:24px;"></h3>
          <div id="config-area">…</div>

          <footer class="nervai-footer" id="footer-area"></footer>
        </div>`;
      this.content = this.querySelector(".container");

      this.querySelectorAll(".lang-btn").forEach(b => b.addEventListener("click", () => { this.lang = b.dataset.lang; this.rerenderAll(); }));
      ["entities","facts","pending","health","usage"].forEach(key => {
        this.querySelector(`#toggle-${key}`).addEventListener("click", () => this.toggleSection(key));
      });
      this.querySelector("#cleanup-aliases-btn").addEventListener("click", () => this.cleanupAliases());
      this.querySelector("#clear-facts-btn").addEventListener("click", () => this.clearAllFacts());
      this.querySelector("#fact-filter-input").addEventListener("input", (e) => { this.factFilter = e.target.value.toLowerCase(); this.renderFacts(); });
      this.querySelector("#only-exposed-toggle").addEventListener("change", (e) => { this.onlyExposed = e.target.checked; this.renderTable(); });

      document.addEventListener("click", (e) => {
        if (!e.target.closest(".filter-icon") && !e.target.closest(".filter-popover")) { this.openFilterCol = null; this.renderTable(); }
      });

      // Bölüm açık/kapalı durumu ilk yüklemede uygulanıyor
      Object.keys(this.sectionsOpen).forEach(key => {
        if (this.sectionsOpen[key]) {
          this.querySelector(`#toggle-${key}`).classList.add("open");
          this.querySelector(`#body-${key}`).classList.add("open");
        }
      });

      this.allEntities = []; this.allFacts = []; this.allPending = []; this.health = {}; this.usage = [];
      this.loadAllData();
    }
  }

  t(key) { return STRINGS[this.lang][key]; }
  escapeHtml(s) { if (s == null) return ""; return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  highlight(text, term) {
    const esc = this.escapeHtml(text);
    if (!term) return esc;
    const idx = esc.toLowerCase().indexOf(term.toLowerCase());
    if (idx === -1) return esc;
    return esc.slice(0, idx) + `<mark>${esc.slice(idx, idx + term.length)}</mark>` + esc.slice(idx + term.length);
  }
  showToast(msg) { const ex = this.querySelector(".toast"); if (ex) ex.remove(); const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; this.appendChild(t); setTimeout(() => t.remove(), 3000); }
  showError(ctx, err) { console.error(`[NervAI] ${ctx}:`, err); const b = this.querySelector("#global-error"); if (b) b.innerHTML = `<div class="error-box">⚠️ ${this.escapeHtml(ctx)}: ${this.escapeHtml(err?.message || String(err))}</div>`; }
  toggleSection(key) { this.sectionsOpen[key] = !this.sectionsOpen[key]; this.querySelector(`#toggle-${key}`).classList.toggle("open", this.sectionsOpen[key]); this.querySelector(`#body-${key}`).classList.toggle("open", this.sectionsOpen[key]); }

  rerenderAll() {
    this.querySelector("#title-entities").textContent = this.t("sectionEntities");
    this.querySelector("#title-facts").textContent = this.t("sectionFacts");
    this.querySelector("#title-pending").textContent = this.t("sectionPending");
    this.querySelector("#title-health").textContent = this.t("sectionHealth");
    this.querySelector("#title-usage").textContent = this.t("sectionUsage");
    this.querySelector("#title-config").textContent = this.t("sectionConfig");
    this.querySelector("#cleanup-aliases-btn").textContent = this.t("cleanupAliases");
    this.querySelector("#clear-facts-btn").textContent = this.t("clearAllFacts");
    this.querySelector("#fact-filter-input").placeholder = this.t("filterPlaceholder");
    this.querySelector("#only-exposed-label").textContent = this.t("onlyExposed");
    this.querySelectorAll(".lang-btn").forEach(b => b.classList.toggle("active", b.dataset.lang === this.lang));
    this.querySelector("#count-entities").textContent = this.allEntities.length;
    this.querySelector("#count-facts").textContent = this.allFacts.length;
    this.querySelector("#count-pending").textContent = this.allPending.length;
    this.renderHealth(); this.renderPending(); this.renderTable(); this.renderFacts(); this.renderUsage(); this.renderConfig();
    this.querySelector("#footer-area").textContent = `NervAI v1.2 — ${this.t("lastUpdated")}: ${new Date().toLocaleString(this.lang === "tr" ? "tr-TR" : "en-US")}`;
  }

  async loadAllData() {
    try { this.allEntities = await this._hass.callWS({ type: "nervai/get_entities" }); } catch (e) { this.showError("Cihaz listesi", e); }
    try { this.allFacts = await this._hass.callWS({ type: "nervai/get_facts" }); } catch (e) { this.showError("Kurallar", e); }
    try { this._conf = await this._hass.callWS({ type: "nervai/get_config" }); } catch (e) { this.showError("Ayarlar", e); }
    try { this.allPending = await this._hass.callWS({ type: "nervai/get_pending_actions" }); } catch (e) { this.allPending = []; }
    try { this.health = await this._hass.callWS({ type: "nervai/get_health" }); } catch (e) { this.health = {}; }
    try { this.usage = await this._hass.callWS({ type: "nervai/get_recent_usage" }); } catch (e) { this.usage = []; }
    this.rerenderAll();
  }

  renderHealth() {
    const area = this.querySelector("#health-area");
    const h = this.health || {};
    area.innerHTML = `<div class="health-grid">
      <div class="health-card"><div class="label">${this.t("botStatus")}</div><div class="value"><span class="dot ${h.bot_online ? "on" : "off"}"></span>${h.bot_online ? this.t("online") : this.t("offline")}</div></div>
      <div class="health-card"><div class="label">${this.t("dbSize")}</div><div class="value">${h.db_size_kb != null ? h.db_size_kb + " KB" : "—"}</div></div>
      <div class="health-card"><div class="label">${this.t("totalActions")}</div><div class="value">${h.total_actions != null ? h.total_actions : "—"}</div></div>
    </div>`;
  }

  renderPending() {
    const area = this.querySelector("#pending-area");
    if (!this.allPending.length) { area.innerHTML = `<p style="color:var(--secondary-text-color)">${this.t("noPending")}</p>`; return; }
    let html = "";
    this.allPending.forEach(p => {
      html += `<div class="pending-card">
        <div><b>${this.escapeHtml(p.domain)}.${this.escapeHtml(p.service)}</b> → ${this.escapeHtml(p.entity_id || "?")}</div>
        <div><button class="icon-btn confirm-btn" data-id="${this.escapeHtml(p.id)}">${this.t("confirm")}</button>
             <button class="danger cancel-btn" data-id="${this.escapeHtml(p.id)}">${this.t("cancel")}</button></div>
      </div>`;
    });
    area.innerHTML = html;
    area.querySelectorAll(".confirm-btn").forEach(b => b.addEventListener("click", () => this.resolvePending(b.dataset.id, true)));
    area.querySelectorAll(".cancel-btn").forEach(b => b.addEventListener("click", () => this.resolvePending(b.dataset.id, false)));
  }

  async resolvePending(actionId, confirm) {
    try {
      await this._hass.callWS({ type: "nervai/resolve_pending_action", action_id: actionId, confirm });
      this.allPending = this.allPending.filter(p => p.id !== actionId);
      this.renderPending();
      this.showToast(confirm ? "✅ Onaylandı." : "❌ İptal edildi.");
    } catch (e) { this.showError("İşlem güncellenemedi", e); }
  }

  renderUsage() {
    const area = this.querySelector("#usage-area");
    if (!this.usage.length) { area.innerHTML = `<p style="color:var(--secondary-text-color)">${this.t("noUsage")}</p>`; return; }
    let html = `<table><tr><th>Entity</th><th>Servis</th><th>Durum</th><th>Zaman</th></tr>`;
    this.usage.forEach(u => {
      html += `<tr><td>${this.escapeHtml(u.entity_id)}</td><td>${this.escapeHtml(u.domain)}.${this.escapeHtml(u.service)}</td><td>${this.escapeHtml(u.status)}</td><td>${this.escapeHtml(u.created_at)}</td></tr>`;
    });
    html += `</table>`;
    area.innerHTML = html;
  }

  toggleFilterPopover(col) { this.openFilterCol = this.openFilterCol === col ? null : col; this.renderTable(); }
  sortBy(key) { if (this.sortKey === key) this.sortAsc = !this.sortAsc; else { this.sortKey = key; this.sortAsc = true; } this.renderTable(); }

  renderTable() {
    const area = this.querySelector("#entities-area");
    let filtered = this.allEntities.filter(e => {
      if (this.onlyExposed && e.exposed === false) return false;
      const nameCombined = `${e.name} ${(e.aliases||[]).join(" ")}`.toLowerCase();
      if (this.colFilters.entity_id && !e.entity_id.toLowerCase().includes(this.colFilters.entity_id)) return false;
      if (this.colFilters.name && !nameCombined.includes(this.colFilters.name)) return false;
      return true;
    });
    if (this.sortKey) {
      filtered = [...filtered].sort((a,b) => {
        let av, bv;
        if (this.sortKey === "alias_count") { av = (a.aliases||[]).length; bv = (b.aliases||[]).length; }
        else { av=(a[this.sortKey]||"").toString().toLowerCase(); bv=(b[this.sortKey]||"").toString().toLowerCase(); }
        if (typeof av === "number") return this.sortAsc ? av - bv : bv - av;
        return this.sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
    }

    const filterIcon = (col) => `<span class="filter-icon ${this.colFilters[col] ? "active" : ""}" data-col="${col}">🔻</span>${this.openFilterCol === col ? `
      <div class="filter-popover">
        <input type="text" class="popover-input" data-col="${col}" placeholder="${this.t('filterPlaceholder')}" value="${this.escapeHtml(this.colFilters[col])}">
        <button class="secondary popover-clear" data-col="${col}">${this.t('clearFilter')}</button>
      </div>` : ""}`;

    // Otomatik tamamlama için tüm mevcut alias'ları datalist'e topla
    const allAliasSet = new Set();
    this.allEntities.forEach(e => (e.aliases || []).forEach(a => allAliasSet.add(a)));
    let datalistHtml = `<datalist id="alias-suggestions">${[...allAliasSet].map(a => `<option value="${this.escapeHtml(a)}">`).join("")}</datalist>`;

    let html = datalistHtml + `<table><tr>
      <th><span class="th-label" data-sort="entity_id">${this.t("colEntityId")}</span>${filterIcon("entity_id")}</th>
      <th><span class="th-label" data-sort="name">${this.t("colName")}</span>${filterIcon("name")}</th>
      <th><span class="th-label" data-sort="alias_count">${this.t("colAddAlias")}</span></th>
      <th>${this.t("colAction")}</th>
    </tr>`;

    if (!filtered.length) {
      html += `<tr><td colspan="4" style="text-align:center;padding:20px;">${this.t("noEntities")}</td></tr>`;
    } else {
      filtered.forEach(e => {
        const isNew = !e.aliases || e.aliases.length === 0;
        const nameCell = isNew
          ? `<b>${this.escapeHtml(e.name)}</b><span class="badge-new">${this.lang==="tr"?"Yeni":"New"}</span>`
          : `<b>${this.escapeHtml(e.name)}</b>, ${this.escapeHtml(e.aliases.join(", "))}`;
        html += `<tr>
          <td>${this.escapeHtml(e.entity_id)}</td>
          <td>${nameCell}</td>
          <td><input type="text" class="alias-input" list="alias-suggestions" id="newalias-${e.entity_id.replace(/\./g,"_")}" placeholder="ör: mutfak ışığı"></td>
          <td><button class="icon-btn" data-entity-id="${this.escapeHtml(e.entity_id)}">✓</button></td>
        </tr>`;
      });
    }
    html += `</table>`;
    area.innerHTML = html;

    area.querySelectorAll(".th-label").forEach(el => el.addEventListener("click", () => this.sortBy(el.dataset.sort)));
    area.querySelectorAll(".filter-icon").forEach(el => el.addEventListener("click", (ev) => { ev.stopPropagation(); this.toggleFilterPopover(el.dataset.col); }));
    area.querySelectorAll(".popover-input").forEach(inp => inp.addEventListener("input", () => { this.colFilters[inp.dataset.col] = inp.value.toLowerCase(); this.renderTable(); this.openFilterCol = inp.dataset.col; }));
    area.querySelectorAll(".popover-clear").forEach(btn => btn.addEventListener("click", (ev) => { ev.stopPropagation(); this.colFilters[btn.dataset.col] = ""; this.renderTable(); }));
    area.querySelectorAll(".icon-btn").forEach(btn => btn.addEventListener("click", () => this.addAlias(btn.dataset.entityId)));
    area.querySelectorAll(".alias-input").forEach(inp => inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { const m = this.allEntities.find(en => en.entity_id.replace(/\./g,"_") === inp.id.replace("newalias-","")); if (m) this.addAlias(m.entity_id); }
    }));
  }

  async addAlias(entityId) {
    const input = this.querySelector(`#newalias-${entityId.replace(/\./g,"_")}`);
    const val = input ? input.value.trim() : "";
    if (!val) return;
    const entity = this.allEntities.find(e => e.entity_id === entityId);
    const current = (entity && entity.aliases) ? [...entity.aliases] : [];
    if (!current.includes(val)) current.push(val);
    try {
      await this._hass.callWS({ type: "nervai/set_alias", entity_id: entityId, aliases: current });
      if (entity) entity.aliases = current;
      this.showToast(`✅ "${val}" eklendi.`);
      this.renderTable();
    } catch (e) { this.showError(`${entityId}`, e); }
  }

  async cleanupAliases() {
    try {
      const res = await this._hass.callWS({ type: "nervai/cleanup_bad_aliases" });
      this.showToast(`✅ ${res.cleaned_count} bozuk kayıt temizlendi.`);
      this.allEntities = await this._hass.callWS({ type: "nervai/get_entities" });
      this.renderTable();
    } catch (e) { this.showError("Temizlik başarısız", e); }
  }

  renderFacts() {
    const area = this.querySelector("#facts-area");
    const filtered = this.allFacts.filter(f => !this.factFilter || f.fact_text.toLowerCase().includes(this.factFilter) || f.category.toLowerCase().includes(this.factFilter));
    if (!filtered.length) { area.innerHTML = `<p style="color:var(--secondary-text-color)">${this.t("noFacts")}</p>`; return; }
    let html = `<table><tr><th>${this.t("colCategory")}</th><th>${this.t("colFactText")}</th><th>${this.t("colFactAction")}</th></tr>`;
    filtered.forEach(f => {
      const editing = this.editingFactKey === f.fact_key;
      html += `<tr>
        <td>${this.escapeHtml(f.category)}</td>
        <td>${editing ? `<input type="text" class="alias-input fact-edit-input" data-fact-key="${this.escapeHtml(f.fact_key)}" value="${this.escapeHtml(f.fact_text)}">` : this.highlight(f.fact_text, this.factFilter)}</td>
        <td>${editing
          ? `<button class="icon-btn fact-save-btn" data-fact-key="${this.escapeHtml(f.fact_key)}" data-category="${this.escapeHtml(f.category)}">✓</button>`
          : `<button class="pencil-btn fact-edit-btn" data-fact-key="${this.escapeHtml(f.fact_key)}">✏️</button><button class="danger delete-fact-btn" data-fact-key="${this.escapeHtml(f.fact_key)}">🗑️</button>`}</td>
      </tr>`;
    });
    html += `</table>`;
    area.innerHTML = html;
    area.querySelectorAll(".fact-edit-btn").forEach(b => b.addEventListener("click", () => { this.editingFactKey = b.dataset.factKey; this.renderFacts(); }));
    area.querySelectorAll(".fact-save-btn").forEach(b => b.addEventListener("click", () => this.saveFactEdit(b.dataset.factKey, b.dataset.category)));
    area.querySelectorAll(".delete-fact-btn").forEach(b => b.addEventListener("click", () => this.deleteFact(b.dataset.factKey)));
  }

  async saveFactEdit(factKey, category) {
    const input = this.querySelector(`.fact-edit-input[data-fact-key="${factKey}"]`);
    const text = input ? input.value.trim() : "";
    if (!text) return;
    try {
      await this._hass.callWS({ type: "nervai/update_fact", fact_key: factKey, category, fact_text: text });
      const f = this.allFacts.find(x => x.fact_key === factKey); if (f) f.fact_text = text;
      this.editingFactKey = null; this.showToast("✅ Güncellendi."); this.renderFacts();
    } catch (e) { this.showError("Güncelleme", e); }
  }

  async deleteFact(factKey) {
    if (!confirm("Bu kural silinsin mi?")) return;
    try { await this._hass.callWS({ type: "nervai/delete_fact", fact_key: factKey }); this.allFacts = this.allFacts.filter(f => f.fact_key !== factKey); this.renderFacts(); this.showToast("🗑️ Silindi."); }
    catch (e) { this.showError("Silme", e); }
  }

  async clearAllFacts() {
    if (!confirm(this.lang === "tr" ? "TÜM kurallar kalıcı olarak silinsin mi?" : "Delete ALL rules permanently?")) return;
    try { await this._hass.callWS({ type: "nervai/clear_all_facts" }); this.allFacts = []; this.renderFacts(); this.showToast("🗑️ Tüm kurallar temizlendi."); }
    catch (e) { this.showError("Toplu silme", e); }
  }

  renderConfig() {
    const area = this.querySelector("#config-area");
    const c = this._conf || {};
    area.innerHTML = `
      <div class="cfg-form">
        <div><label>${this.t("telegramToken")}</label><input type="password" class="cfg-input" id="cfg-telegram" placeholder="${this.escapeHtml(c.telegram_token || "tg-masked")}"></div>
        <div><label>${this.t("openaiKey")}</label><input type="password" class="cfg-input" id="cfg-openai" placeholder="${this.escapeHtml(c.token || "sk-masked")}"></div>
        <div><label>${this.t("model")}</label><input type="text" class="cfg-input" id="cfg-model" value="${this.escapeHtml(c.model || "")}"></div>
        <div style="display:flex; gap:8px;">
          <button class="icon-btn" id="cfg-save-btn">${this.t("save")}</button>
          <button class="secondary" id="cfg-test-btn">${this.t("testConn")}</button>
        </div>
      </div>`;
    this.querySelector("#cfg-save-btn").addEventListener("click", () => this.saveConfig());
    this.querySelector("#cfg-test-btn").addEventListener("click", () => this.testConnection());
  }

  async saveConfig() {
    const telegram = this.querySelector("#cfg-telegram").value.trim();
    const openai = this.querySelector("#cfg-openai").value.trim();
    const model = this.querySelector("#cfg-model").value.trim();
    try {
      await this._hass.callWS({ type: "nervai/set_config", model, token: openai || "sk-masked", telegram_token: telegram || "tg-masked" });
      this.showToast("✅ Ayarlar kaydedildi, entegrasyon yeniden başlatılıyor...");
    } catch (e) { this.showError("Ayarlar kaydedilemedi", e); }
  }

  async testConnection() {
    try {
      const res = await this._hass.callWS({ type: "nervai/test_connection" });
      this.showToast(res.ok ? "✅ Bağlantı başarılı." : `⚠️ ${res.message}`);
    } catch (e) { this.showError("Test başarısız", e); }
  }
}
customElements.define("nervai-panel", NervAIPanel);