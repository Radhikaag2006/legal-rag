(() => {
  "use strict";

  /* ---------------- helpers ---------------- */
  const $ = (id) => document.getElementById(id);
  const el = {
    app: $("app"), chatList: $("chatList"), chatSearch: $("chatSearch"), corpus: $("corpusInfo"),
    title: $("chatTitle"), thread: $("thread"), inner: $("threadInner"), input: $("input"),
    send: $("sendBtn"), attach: $("attachBtn"), fileInput: $("fileInput"), chips: $("fileChips"),
    filterBtn: $("filterBtn"), filterPop: $("filterPop"), filterDot: $("filterDot"),
    courtList: $("courtList"), yearMin: $("yearMin"), yearMax: $("yearMax"), topK: $("topK"),
    modeSeg: $("modeSeg"), composer: $("composer"),
    viewer: $("viewer"), vTitle: $("vTitle"), vSub: $("vSub"), vOpen: $("vOpen"),
    vBody: $("vBody"), vPassage: $("vPassage"), vPassageText: $("vPassageText"), toast: $("toast"),
  };

  const ICON = {
    edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z"/></svg>',
    trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12M9 7V4h6v3"/></svg>',
    x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    copy: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/></svg>',
    download: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7 11l5 5 5-5M5 20h14"/></svg>',
    open: '<svg viewBox="0 0 24 24" style="width:14px;height:14px"><path d="M9 6l6 6-6 6"/></svg>',
  };

  const state = {
    chats: [], currentId: null, title: "New chat", messages: [], files: [],
    info: null, busy: false, uploading: 0,
    mode: load("mode", "lawyer"),
    filters: load("filters", { courts: [], yearMin: null, yearMax: null, topK: 5 }),
  };

  function load(key, fallback) {
    try { const v = localStorage.getItem("nyaya:" + key); return v ? JSON.parse(v) : fallback; }
    catch { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem("nyaya:" + key, JSON.stringify(value)); } catch { /* ignore */ }
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(path, opts = {}) {
    const init = { ...opts };
    if (opts.json !== undefined) {
      init.method = init.method || "POST";
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(opts.json);
      delete init.json;
    }
    let res;
    try { res = await fetch(path, init); }
    catch { throw new Error("Cannot reach the server. Is it still running?"); }
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") msg = body.detail;
        else if (Array.isArray(body.detail)) msg = body.detail.map((d) => (d.msg || "").replace(/^Value error, /, "")).join("; ");
      } catch { /* not json */ }
      throw new Error(msg);
    }
    return res.json();
  }

  let toastTimer;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.toast.hidden = true), 4500);
  }

  /* ---------------- markdown (small, safe) ---------------- */
  function inline(text) {
    let s = esc(text);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>")
         .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
         .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?![*\w])/g, "$1<em>$2</em>");
    s = s.replace(/(?:\[S\d+\]\s*)+/g, (m) => {
      const nums = [...m.matchAll(/S(\d+)/g)].map((x) => x[1]);
      return '<span class="cites">' + nums.map((n) => `<button class="cite" data-n="${n}" title="Open source ${n}">${n}</button>`).join("") + "</span> ";
    });
    return s;
  }

  function markdown(src) {
    const lines = String(src).replace(/\r/g, "").split("\n");
    let html = "", list = null, para = [];
    const flushPara = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para = []; } };
    const closeList = () => { if (list) { html += `</${list}>`; list = null; } };

    for (const raw of lines) {
      const line = raw.trimEnd();
      let m;
      if (!line.trim()) { flushPara(); closeList(); continue; }
      if ((m = line.match(/^#{1,4}\s+(.*)$/))) { flushPara(); closeList(); html += `<h3>${inline(m[1])}</h3>`; continue; }
      if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) {
        flushPara(); if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
        html += `<li>${inline(m[1])}</li>`; continue;
      }
      if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
        flushPara(); if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
        html += `<li>${inline(m[1])}</li>`; continue;
      }
      if ((m = line.match(/^>\s?(.*)$/))) { flushPara(); closeList(); html += `<blockquote>${inline(m[1])}</blockquote>`; continue; }
      closeList(); para.push(line.trim());
    }
    flushPara(); closeList();
    return html;
  }

  /* ---------------- sidebar ---------------- */
  function groupLabel(ts) {
    const d = new Date(ts * 1000), now = new Date();
    const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day(now) - day(d)) / 86400000);
    if (diff <= 0) return "Today";
    if (diff === 1) return "Yesterday";
    if (diff <= 7) return "Previous 7 days";
    return "Earlier";
  }

  function renderChats() {
    const q = el.chatSearch.value.trim().toLowerCase();
    const items = state.chats.filter((c) => !q || c.title.toLowerCase().includes(q));
    if (!items.length) {
      el.chatList.innerHTML = `<div class="empty-list">${q ? "No chats match your search." : "Your conversations will appear here."}</div>`;
      return;
    }
    let html = "", last = "";
    for (const c of items) {
      const g = groupLabel(c.updated);
      if (g !== last) { html += `<div class="group-label">${g}</div>`; last = g; }
      html += `<div class="chat-item ${c.id === state.currentId ? "active" : ""}" data-id="${c.id}">
        <span class="t" title="${esc(c.title)}">${esc(c.title)}</span>
        <span class="acts">
          <button data-act="rename" title="Rename" aria-label="Rename chat">${ICON.edit}</button>
          <button data-act="delete" title="Delete" aria-label="Delete chat">${ICON.trash}</button>
        </span></div>`;
    }
    el.chatList.innerHTML = html;
  }

  async function refreshChats() {
    try { state.chats = await api("/api/chats"); renderChats(); } catch { /* sidebar is non-critical */ }
  }

  el.chatList.addEventListener("click", async (e) => {
    const item = e.target.closest(".chat-item");
    if (!item) return;
    const id = item.dataset.id;
    const act = e.target.closest("button")?.dataset.act;

    if (act === "delete") {
      if (!confirm("Delete this chat and its uploaded documents?")) return;
      try { await api(`/api/chats/${id}`, { method: "DELETE" }); } catch (err) { return toast(err.message); }
      if (id === state.currentId) newChat();
      return refreshChats();
    }
    if (act === "rename") return startRename(item, id);
    if (e.target.classList.contains("rename")) return;
    openChat(id);
    el.app.classList.remove("sidebar-open");
  });

  function startRename(item, id) {
    const span = item.querySelector(".t");
    const input = document.createElement("input");
    input.className = "rename"; input.value = span.textContent; input.maxLength = 120;
    span.replaceWith(input); input.focus(); input.select();
    let done = false;
    const finish = async (commit) => {
      if (done) return; done = true;
      const v = input.value.trim();
      if (commit && v && v !== span.textContent) {
        try { await api(`/api/chats/${id}`, { method: "PATCH", json: { title: v } }); if (id === state.currentId) { state.title = v; el.title.textContent = v; } }
        catch (err) { toast(err.message); }
      }
      refreshChats();
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") finish(true); if (e.key === "Escape") finish(false); });
    input.addEventListener("blur", () => finish(true));
  }

  el.chatSearch.addEventListener("input", renderChats);
  $("newChat").addEventListener("click", () => { newChat(); el.app.classList.remove("sidebar-open"); el.input.focus(); });
  $("menuBtn").addEventListener("click", () => el.app.classList.add("sidebar-open"));
  $("scrim").addEventListener("click", () => el.app.classList.remove("sidebar-open"));

  /* ---------------- chat lifecycle ---------------- */
  function newChat() {
    state.currentId = null; state.title = "New chat"; state.messages = []; state.files = [];
    closeViewer(); renderAll(); renderChats();
  }

  async function openChat(id) {
    try {
      const chat = await api(`/api/chats/${id}`);
      state.currentId = chat.id; state.title = chat.title; state.files = chat.files;
      state.messages = chat.messages.map((m) => ({ role: m.role, content: m.content, payload: m.payload }));
    } catch (err) { return toast(err.message); }
    closeViewer(); renderAll(); renderChats(); scrollDown(true);
  }

  async function ensureChat() {
    if (state.currentId) return state.currentId;
    const c = await api("/api/chats", { method: "POST" });
    state.currentId = c.id;
    return c.id;
  }

  /* ---------------- rendering the thread ---------------- */
  function renderAll() {
    el.title.textContent = state.title;
    el.modeSeg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.mode === state.mode));
    renderChips();
    renderThread();
  }

  function renderThread(extra = "") {
    updateSummaryBtn();
    if (!state.messages.length && !extra) {
      el.inner.innerHTML = welcome();
      return;
    }
    el.inner.innerHTML = state.messages.map(renderMessage).join("") + extra;
  }

  function welcome() {
    const ex = [
      ["What is the Basic Structure Doctrine and which cases established it?", "Constitutional law"],
      ["How have courts interpreted reasonable classification under Article 14?", "Fundamental rights"],
      ["Can Parliament amend Fundamental Rights?", "Constitutional law"],
      ["On what grounds can anticipatory bail be granted?", "Criminal procedure"],
    ];
    return `<div class="welcome">
      <h2>What would you like to research?</h2>
      <p>Ask about Indian case law and get an answer where every statement points to the judgment, and the page, it came from. You can also attach your own document — a notice, contract or draft — and ask questions about it.</p>
      <div class="examples">${ex.map((e) => `<button class="example" data-q="${esc(e[0])}">${esc(e[0])}<span>${e[1]}</span></button>`).join("")}</div>
    </div>`;
  }

  function renderMessage(m, idx) {
    if (m.role === "user") return `<div class="msg user"><div class="bubble">${esc(m.content)}</div></div>`;
    const p = m.payload || { answer: m.content, sources: [] };
    const sources = p.sources || [];
    const cited = sources.filter((s) => s.cited);
    const other = sources.filter((s) => !s.cited);
    const secs = p.timings?.total ? ` · ${Number(p.timings.total).toFixed(1)}s` : "";
    const label = p.mode === "student" ? "Study notes" : "Research memo";

    const row = (s, dim) => {
      const where = s.source_type === "upload" ? "Your document" : esc(s.court);
      const when = s.date ? ` · ${esc(s.date)}` : "";
      const pg = s.page ? ` · p. ${s.page}` : "";
      return `<button class="auth-row ${dim ? "dim" : ""}" data-n="${s.number}">
        <span class="num">${s.number}</span>
        <span class="body"><div class="name">${esc(s.case_title)}</div><div class="sub">${where}${when}${pg}</div></span>
        <span class="go">${s.viewable ? "View PDF" : "Details"} ${ICON.open}</span></button>`;
    };

    return `<div class="msg assistant" data-idx="${idx}">
      <div class="meta">${label}${secs}</div>
      ${p.answered === false ? '<div class="notice">The indexed judgments do not contain enough to answer this reliably. Try rephrasing, or widening the court/year filters.</div>' : ""}
      <div class="prose">${markdown(p.answer)}</div>
      ${sources.length ? `<div class="auth"><h4>Authorities · ${cited.length} cited</h4>
        ${cited.map((s) => row(s, false)).join("")}
        ${other.length ? `<details class="more"><summary>${other.length} more retrieved, not cited</summary>${other.map((s) => row(s, true)).join("")}</details>` : ""}
      </div>` : ""}
      <div class="actions">
        <button data-act="copy">${ICON.copy} Copy</button>
        <button data-act="memo">${ICON.download} Download memo</button>
      </div></div>`;
  }

  const workingHTML = '<div class="msg assistant" id="working"><div class="working"><span class="pulse"></span>Researching the judgments…</div></div>';

  function scrollDown(instant) {
    requestAnimationFrame(() => el.thread.scrollTo({ top: el.thread.scrollHeight, behavior: instant ? "auto" : "smooth" }));
  }

  el.inner.addEventListener("click", (e) => {
    const ex = e.target.closest(".example");
    if (ex) { el.input.value = ex.dataset.q; autosize(); return send(); }

    const msgEl = e.target.closest(".msg.assistant");
    if (!msgEl) return;
    const m = state.messages[Number(msgEl.dataset.idx)];
    const sources = m?.payload?.sources || [];

    const srcBtn = e.target.closest("[data-n]");
    if (srcBtn) {
      const s = sources.find((x) => x.number === Number(srcBtn.dataset.n));
      if (s) openViewer(s);
      return;
    }
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "copy") navigator.clipboard?.writeText(m.content).then(() => toast("Copied to clipboard"));
    if (act === "memo") downloadMemo(state.messages[Number(msgEl.dataset.idx) - 1]?.content || "", m);
  });

  function downloadMemo(question, m) {
    const p = m.payload, lines = ["# Legal Research Memo", "", `*Generated ${new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}*`, "", `**Question:** ${question}`, "", p.answer.replace(/\[S(\d+)\]/g, "[$1]"), "", "---", "## Authorities", ""];
    for (const s of p.sources) {
      const link = s.pdf_url ? location.origin + s.pdf_url + (s.page ? `#page=${s.page}` : "") : (s.external_url || "");
      lines.push(`${s.number}. **${s.case_title}** — ${s.court}${s.date ? ", " + s.date : ""}${s.page ? ", p. " + s.page : ""}${s.cited ? "" : " *(retrieved, not cited)*"}${link ? "  \n   " + link : ""}`);
    }
    lines.push("", "> AI-assisted research. Verify every authority against the official report. Not legal advice.");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/markdown" }));
    a.download = "research-memo.md"; a.click(); URL.revokeObjectURL(a.href);
  }

  /* ---------------- viewer ---------------- */
  function openViewer(s) {
    el.vTitle.textContent = s.case_title;
    const bits = [s.source_type === "upload" ? "Your document" : s.court, s.date, s.page ? `page ${s.page}` : ""].filter(Boolean);
    el.vSub.textContent = bits.join(" · ");

    const passage = (s.excerpts || [])[0];
    el.vPassage.hidden = !passage;
    el.vPassage.open = true;
    el.vPassageText.textContent = passage ? passage.trim().slice(0, 900) + (passage.length > 900 ? "…" : "") : "";

    if (s.viewable && s.pdf_url) {
      const url = s.pdf_url + (s.page ? `#page=${s.page}` : "");
      el.vOpen.href = url; el.vOpen.hidden = false;
      el.vBody.innerHTML = "";
      const frame = document.createElement("iframe");
      frame.title = s.case_title; frame.src = url;
      el.vBody.appendChild(frame);
    } else {
      el.vOpen.hidden = !s.pdf_url; if (s.pdf_url) el.vOpen.href = s.pdf_url;
      const alt = s.external_url ? `You can read it on <a href="${esc(s.external_url)}" target="_blank" rel="noopener">Indian Kanoon</a>.` : "";
      const dl = s.pdf_url ? `<a href="${esc(s.pdf_url)}" target="_blank" rel="noopener">Download the file</a> to view it.` : "";
      el.vBody.innerHTML = `<div class="viewer-msg">A PDF preview isn't available for this source. ${dl} ${alt}</div>`;
    }
    el.app.classList.add("viewer-open");
  }

  function closeViewer() {
    el.app.classList.remove("viewer-open");
    setTimeout(() => { if (!el.app.classList.contains("viewer-open")) el.vBody.innerHTML = ""; }, 250);
  }
  $("vClose").addEventListener("click", closeViewer);

  /* ---------------- composer ---------------- */
  function autosize() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 200) + "px";
    el.send.disabled = state.busy || !el.input.value.trim();
  }
  el.input.addEventListener("input", autosize);
  el.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
  });
  el.send.addEventListener("click", send);

  el.modeSeg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    state.mode = b.dataset.mode; save("mode", state.mode); renderAll();
  });

  async function send() {
    const text = el.input.value.trim();
    if (!text || state.busy) return;
    state.busy = true; closePopover();

    try { await ensureChat(); }
    catch (err) { state.busy = false; return toast(err.message); }

    state.messages.push({ role: "user", content: text });
    el.input.value = ""; autosize(); el.send.disabled = true;
    renderThread(workingHTML); scrollDown();

    const f = state.filters;
    const body = {
      question: text, mode: state.mode, top_k: Number(f.topK) || 5,
      courts: f.courts.length ? f.courts : null,
      year_min: f.yearMin || null, year_max: f.yearMax || null,
    };

    try {
      const res = await api(`/api/chats/${state.currentId}/messages`, { json: body });
      state.messages.push({ role: "assistant", content: res.content, payload: res.payload });
      renderThread();
    } catch (err) {
      state.messages.pop();                       // server did not save this turn
      renderThread(`<div class="error"><strong>Couldn't complete that.</strong> ${esc(err.message)}</div>`);
      el.input.value = text;                      // let the user retry in one click
    }
    state.busy = false; autosize(); scrollDown();

    await refreshChats();
    const cur = state.chats.find((c) => c.id === state.currentId);
    if (cur) { state.title = cur.title; el.title.textContent = cur.title; }
  }

  /* ---------------- filters ---------------- */
  function buildFilters() {
    const info = state.info; if (!info) return;
    el.courtList.innerHTML = info.courts.map((c) =>
      `<label><input type="checkbox" value="${esc(c)}" ${state.filters.courts.includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
    el.yearMin.placeholder = info.year_min; el.yearMax.placeholder = info.year_max;
    el.yearMin.value = state.filters.yearMin || ""; el.yearMax.value = state.filters.yearMax || "";
    el.topK.value = String(state.filters.topK || 5);
    updateFilterDot();
  }
  function readFilters() {
    state.filters = {
      courts: [...el.courtList.querySelectorAll("input:checked")].map((i) => i.value),
      yearMin: el.yearMin.value ? Number(el.yearMin.value) : null,
      yearMax: el.yearMax.value ? Number(el.yearMax.value) : null,
      topK: Number(el.topK.value),
    };
    save("filters", state.filters); updateFilterDot();
  }
  function updateFilterDot() {
    const f = state.filters;
    el.filterDot.hidden = !(f.courts.length || f.yearMin || f.yearMax);
  }
  function closePopover() { el.filterPop.hidden = true; }
  el.filterBtn.addEventListener("click", (e) => { e.stopPropagation(); el.filterPop.hidden = !el.filterPop.hidden; });
  el.filterPop.addEventListener("click", (e) => e.stopPropagation());
  el.filterPop.addEventListener("change", readFilters);
  el.filterPop.addEventListener("input", (e) => { if (e.target.type === "number") readFilters(); });
  $("clearFilters").addEventListener("click", () => {
    state.filters = { courts: [], yearMin: null, yearMax: null, topK: 5 }; save("filters", state.filters); buildFilters();
  });
  document.addEventListener("click", closePopover);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closePopover(); closeViewer(); } });

  /* ---------------- uploads ---------------- */
  function renderChips() {
    const chips = state.files.map((f) => `<span class="chip" data-id="${f.id}">
        <button class="open" title="${esc(f.filename)}">${esc(f.filename)}</button>
        ${f.pages ? `<small>${f.pages} p.</small>` : ""}
        <button class="x" title="Remove" aria-label="Remove file">${ICON.x}</button></span>`);
    if (state.uploading) chips.push(`<span class="chip busy">Reading ${state.uploading} file${state.uploading > 1 ? "s" : ""}…</span>`);
    el.chips.innerHTML = chips.join("");
  }

  el.chips.addEventListener("click", async (e) => {
    const chip = e.target.closest(".chip[data-id]"); if (!chip) return;
    const f = state.files.find((x) => x.id === chip.dataset.id); if (!f) return;
    if (e.target.closest(".x")) {
      try { await api(`/api/chats/${state.currentId}/files/${f.id}`, { method: "DELETE" }); } catch (err) { return toast(err.message); }
      state.files = state.files.filter((x) => x.id !== f.id); return renderChips();
    }
    openViewer({ case_title: f.filename, source_type: "upload", court: "", date: "", page: null, excerpts: [], viewable: f.viewable, pdf_url: f.url });
  });

  async function uploadFiles(fileList) {
    const files = [...fileList]; if (!files.length) return;
    try { await ensureChat(); } catch (err) { return toast(err.message); }
    for (const file of files) {
      state.uploading++; renderChips();
      const fd = new FormData(); fd.append("file", file);
      try {
        const rec = await api(`/api/chats/${state.currentId}/files`, { method: "POST", body: fd });
        state.files.push(rec);
        toast(`Added “${rec.filename}”. You can now ask questions about it.`);
      } catch (err) { toast(`${file.name}: ${err.message}`); }
      state.uploading--; renderChips();
    }
    refreshChats();
  }

  el.attach.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", () => { uploadFiles(el.fileInput.files); el.fileInput.value = ""; });

  let dragDepth = 0;
  window.addEventListener("dragenter", (e) => { if (e.dataTransfer?.types?.includes("Files")) { dragDepth++; el.composer.classList.add("drag"); } });
  window.addEventListener("dragleave", () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) el.composer.classList.remove("drag"); });
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => {
    e.preventDefault(); dragDepth = 0; el.composer.classList.remove("drag");
    if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files);
  });

  /* ---------------- summary ---------------- */
  const sum = {
    modal: $("sumModal"), body: $("sumBody"), foot: $("sumFoot"), verify: $("sumVerify"),
    btn: $("summaryBtn"), data: null, running: false,
  };

  function updateSummaryBtn() {
    sum.btn.disabled = !state.messages.some((m) => m.role === "assistant" && m.payload?.answered !== false);
  }

  function closeSummary() { sum.modal.hidden = true; }

  async function openSummary() {
    if (sum.running || !state.currentId) return;
    sum.running = true; sum.data = null;
    sum.foot.hidden = true; sum.modal.hidden = false;
    sum.body.innerHTML = `<div class="sum-wait"><span class="pulse"></span>
      <div><strong>Writing and fact-checking your summary…</strong><br>
      Every statement is checked against the judgment extracts. This can take up to a minute.</div></div>`;
    try {
      const d = await api(`/api/chats/${state.currentId}/summary`, { method: "POST" });
      sum.data = d;
      const cited = d.authorities.filter((a) => a.cited);
      const row = (a) => `<button class="auth-row ${a.cited ? "" : "dim"}" data-n="${a.number}">
        <span class="num">${a.number}</span>
        <span class="body"><div class="name">${esc(a.case_title)}</div>
        <div class="sub">${esc(a.source_type === "upload" ? "Your document" : a.court)}${a.date ? " · " + esc(a.date) : ""}${a.page ? " · p. " + a.page : ""}</div></span>
        <span class="go">${a.viewable ? "View PDF" : "Details"} ${ICON.open}</span></button>`;
      sum.body.innerHTML = `<div class="sum-title">${esc(d.title)} · ${d.questions} question${d.questions > 1 ? "s" : ""}</div>
        <div class="prose">${markdown(d.summary)}</div>
        <div class="auth"><h4>Authorities · ${cited.length} cited</h4>${d.authorities.map(row).join("")}</div>`;
      const nq = (d.unverified_quotes || []).length;
      sum.verify.textContent = (d.verified
        ? "Checked against the source extracts. Still verify before relying on it."
        : "Automatic fact-check was unavailable. Review carefully.")
        + (nq ? ` ${nq} quoted phrase${nq > 1 ? "s" : ""} could not be matched word-for-word to the source: ${d.unverified_quotes.map((q) => "“" + q.slice(0, 50) + (q.length > 50 ? "…" : "") + "”").join(", ")}.` : "");
      sum.verify.style.color = nq ? "var(--danger)" : "";
      sum.foot.hidden = false;
    } catch (err) {
      sum.body.innerHTML = `<div class="error"><strong>Couldn't create the summary.</strong> ${esc(err.message)}</div>`;
    }
    sum.running = false;
  }

  async function downloadSummary(fmt, button) {
    if (!sum.data) return;
    const d = sum.data;
    const label = button.textContent;
    button.disabled = true; button.textContent = "Preparing…";
    try {
      const res = await fetch(`/api/export/${fmt}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: d.title, summary: d.summary, authorities: d.authorities }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Failed (${res.status})`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await res.blob());
      const safe = d.title.replace(/[\\/:*?"<>|]/g, "").slice(0, 50) || "research";
      a.download = `Summary - ${safe}.${fmt}`;
      a.click(); URL.revokeObjectURL(a.href);
    } catch (err) { toast(err.message); }
    button.disabled = false; button.textContent = label;
  }

  sum.btn.addEventListener("click", openSummary);
  $("sumClose").addEventListener("click", closeSummary);
  sum.modal.addEventListener("click", (e) => { if (e.target === sum.modal) closeSummary(); });
  $("sumPdf").addEventListener("click", (e) => downloadSummary("pdf", e.currentTarget));
  $("sumDocx").addEventListener("click", (e) => downloadSummary("docx", e.currentTarget));
  $("sumCopy").addEventListener("click", () => {
    if (!sum.data) return;
    navigator.clipboard?.writeText(sum.data.summary.replace(/\[S(\d+)\]/g, "[$1]")).then(() => toast("Copied to clipboard"));
  });
  sum.body.addEventListener("click", (e) => {
    const b = e.target.closest("[data-n]");
    if (!b || !sum.data) return;
    const a = sum.data.authorities.find((x) => x.number === Number(b.dataset.n));
    if (!a) return;
    closeSummary();
    openViewer(a);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSummary(); });

  /* ---------------- boot ---------------- */
  async function boot() {
    renderAll(); renderChats(); autosize();
    await refreshChats();
    try {
      state.info = await api("/api/info");
      el.corpus.textContent = `${state.info.judgments.toLocaleString()} judgments · ${state.info.passages.toLocaleString()} passages indexed`;
      buildFilters();
    } catch (err) {
      el.corpus.textContent = "Research engine unavailable";
      el.inner.insertAdjacentHTML("afterbegin", `<div class="error">${esc(err.message)}</div>`);
    }
  }
  boot();
})();
