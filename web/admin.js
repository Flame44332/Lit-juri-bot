const loginCard = document.getElementById("loginCard");
const adminApp = document.getElementById("adminApp");
const adminLoginEl = document.getElementById("adminLogin");
const adminPasswordEl = document.getElementById("adminPassword");
const loginBtn = document.getElementById("loginBtn");
const loginError = document.getElementById("loginError");
const adminLabelEl = document.getElementById("adminLabel");
const refreshBtn = document.getElementById("refreshBtn");
const logoutBtn = document.getElementById("logoutBtn");
const statusBarEl = document.getElementById("statusBar");
const navEl = document.getElementById("nav");

const classesListEl = document.getElementById("classesList");
const queueListEl = document.getElementById("queueList");
const swapAEl = document.getElementById("swapA");
const swapBEl = document.getElementById("swapB");
const swapBtn = document.getElementById("swapBtn");
const orderClassEl = document.getElementById("orderClass");
const orderValueEl = document.getElementById("orderValue");
const orderBtn = document.getElementById("orderBtn");

const criteriaListEl = document.getElementById("criteriaList");
const critNameEl = document.getElementById("critName");
const critMinEl = document.getElementById("critMin");
const critMaxEl = document.getElementById("critMax");
const critGroupEl = document.getElementById("critGroup");
const critAddBtn = document.getElementById("critAddBtn");
const critRenameIdEl = document.getElementById("critRenameId");
const critRenameNameEl = document.getElementById("critRenameName");
const critRenameBtn = document.getElementById("critRenameBtn");
const critDeleteIdEl = document.getElementById("critDeleteId");
const critDeleteBtn = document.getElementById("critDeleteBtn");

const adminCreateNameEl = document.getElementById("adminCreateName");
const adminCreateBtn = document.getElementById("adminCreateBtn");
const adminsListEl = document.getElementById("adminsList");
const juryListEl = document.getElementById("juryList");
const juryProfileNameEl = document.getElementById("juryProfileName");
const juryProfileCreateBtn = document.getElementById("juryProfileCreateBtn");
const juryProfilesListEl = document.getElementById("juryProfilesList");

const inviteCreateBtn = document.getElementById("inviteCreateBtn");
const inviteInfoEl = document.getElementById("inviteInfo");
const invitesListEl = document.getElementById("invitesList");

const activeClassHintEl = document.getElementById("activeClassHint");
const openClassEl = document.getElementById("openClass");
const openBtn = document.getElementById("openBtn");
const closeClassEl = document.getElementById("closeClass");
const closeBtn = document.getElementById("closeBtn");
const nextBtn = document.getElementById("nextBtn");
const votingStatusEl = document.getElementById("votingStatus");

const resultsMetaEl = document.getElementById("resultsMeta");
const resultsListEl = document.getElementById("resultsList");
const resultsRefreshBtn = document.getElementById("resultsRefresh");
const resultsFinalBtn = document.getElementById("resultsFinal");

const resetBtn = document.getElementById("resetBtn");
const resetHintEl = document.getElementById("resetHint");
const logsListEl = document.getElementById("logsList");

const STORAGE_TOKEN = "juri-admin-token";

const state = {
  token: "",
  data: null,
  section: "classes",
  resetArmed: false,
  resetTimer: null,
};

function setStatus(message, isError = false) {
  statusBarEl.textContent = message;
  statusBarEl.style.color = isError ? "#f87171" : "";
}

function statusText(cls) {
  if (cls.is_open) return "ОТКРЫТО";
  if (cls.is_finished) return "ЗАВЕРШЕНО";
  return "ЗАКРЫТО";
}

function loadToken() {
  return localStorage.getItem(STORAGE_TOKEN) || "";
}

function saveToken(token) {
  localStorage.setItem(STORAGE_TOKEN, token);
}

function clearToken() {
  localStorage.removeItem(STORAGE_TOKEN);
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "request_failed");
  }
  return data;
}

async function downloadExport(type) {
  const res = await fetch(`/api/admin/export?type=${encodeURIComponent(type)}`, {
    headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
  });
  if (!res.ok) {
    setStatus("Не удалось экспортировать", true);
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${type}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function showSection(name) {
  state.section = name;
  document.querySelectorAll("[data-section]").forEach((el) => {
    const section = el.dataset.section;
    if (!section) return;
    if (el.classList.contains("nav__btn")) {
      el.classList.toggle("nav__btn--active", section === name);
      return;
    }
    el.hidden = section !== name;
  });
}

function fillSelect(select, items, labelFn, valueFn) {
  select.innerHTML = "";
  items.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = valueFn(item);
    opt.textContent = labelFn(item);
    select.appendChild(opt);
  });
}

function renderClasses() {
  classesListEl.innerHTML = "";
  const classes = state.data?.classes || [];
  classes.forEach((cls) => {
    const row = document.createElement("div");
    row.className = "row";

    const idEl = document.createElement("div");
    idEl.className = "row__id";
    idEl.textContent = cls.class_id;

    const songInput = document.createElement("input");
    songInput.type = "text";
    songInput.value = cls.song_title || "";

    const orderInput = document.createElement("input");
    orderInput.type = "number";
    orderInput.min = "1";
    orderInput.value = cls.performance_order || 0;

    const actions = document.createElement("div");
    actions.className = "row__actions";

    const statusEl = document.createElement("div");
    statusEl.className = "row__status";
    statusEl.textContent = statusText(cls);

    const saveSongBtn = document.createElement("button");
    saveSongBtn.className = "btn btn--ghost btn--small";
    saveSongBtn.textContent = "Песня";
    saveSongBtn.addEventListener("click", async () => {
      try {
        await api("/api/admin/class/song", {
          method: "POST",
          body: { class_id: cls.class_id, song_title: songInput.value },
        });
        await loadData();
        setStatus("Песня сохранена");
      } catch (err) {
        setStatus("Не удалось сохранить песню", true);
      }
    });

    const saveOrderBtn = document.createElement("button");
    saveOrderBtn.className = "btn btn--primary btn--small";
    saveOrderBtn.textContent = "Номер";
    saveOrderBtn.addEventListener("click", async () => {
      try {
        await api("/api/admin/class/order", {
          method: "POST",
          body: { class_id: cls.class_id, order: orderInput.value },
        });
        await loadData();
        setStatus("Номер сохранен");
      } catch (err) {
        setStatus("Не удалось сохранить номер", true);
      }
    });

    actions.appendChild(statusEl);
    actions.appendChild(saveSongBtn);
    actions.appendChild(saveOrderBtn);

    row.appendChild(idEl);
    row.appendChild(songInput);
    row.appendChild(orderInput);
    row.appendChild(actions);
    classesListEl.appendChild(row);
  });
}

function renderQueue() {
  const classes = state.data?.classes || [];
  queueListEl.innerHTML = "";
  classes.forEach((cls) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `
      <div class="row__id">${cls.performance_order}</div>
      <div>${cls.class_id} — ${cls.song_title || "—"}</div>
      <div></div>
      <div class="row__status">${statusText(cls)}</div>
    `;
    queueListEl.appendChild(item);
  });
  fillSelect(swapAEl, classes, (c) => c.class_id, (c) => c.class_id);
  fillSelect(swapBEl, classes, (c) => c.class_id, (c) => c.class_id);
  fillSelect(orderClassEl, classes, (c) => c.class_id, (c) => c.class_id);
}

function renderCriteria() {
  const criteria = state.data?.criteria || [];
  criteriaListEl.innerHTML = "";
  criteria.forEach((crit) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `
      <div class="row__id">${crit.id}</div>
      <div>${crit.name}</div>
      <div>${crit.min_score}-${crit.max_score}</div>
      <div class="row__status">${crit.group_key || "—"}</div>
    `;
    criteriaListEl.appendChild(item);
  });
  fillSelect(critRenameIdEl, criteria, (c) => `${c.id}. ${c.name}`, (c) => c.id);
  fillSelect(critDeleteIdEl, criteria, (c) => `${c.id}. ${c.name}`, (c) => c.id);
}

function renderUsers() {
  adminsListEl.innerHTML = "";
  (state.data?.admins || []).forEach((admin) => {
    const item = document.createElement("div");
    item.className = "row";
    const linked = admin.telegram_id ? "✅" : "—";
    item.innerHTML = `
      <div class="row__id">${admin.username}</div>
      <div>${admin.password}</div>
      <div></div>
      <div class="row__status">привязан: ${linked}</div>
    `;
    adminsListEl.appendChild(item);
  });

  juryListEl.innerHTML = "";
  (state.data?.jury || []).forEach((jury) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `
      <div class="row__id">${jury.jury_code || jury.telegram_id}</div>
      <div>${jury.name || "—"}</div>
      <div>${jury.username ? `@${jury.username}` : "—"}</div>
      <div class="row__status">жюри</div>
    `;
    juryListEl.appendChild(item);
  });

  juryProfilesListEl.innerHTML = "";
  (state.data?.jury_profiles || []).forEach((profile) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `
      <div class="row__id">${profile.name || "—"}</div>
      <div>Код: ${profile.code || "—"}</div>
      <div>${profile.created_at || ""}</div>
      <div class="row__status">жюри</div>
    `;
    juryProfilesListEl.appendChild(item);
  });
}

function renderInvites() {
  invitesListEl.innerHTML = "";
  (state.data?.invites || []).forEach((invite) => {
    const item = document.createElement("div");
    item.className = "row";

    const idEl = document.createElement("div");
    idEl.className = "row__id";
    idEl.textContent = invite.code;

    const usesEl = document.createElement("div");
    usesEl.textContent = `Использований: ${invite.uses}${invite.max_uses ? `/${invite.max_uses}` : ""}`;

    const dateEl = document.createElement("div");
    dateEl.textContent = invite.created_at || "";

    const actions = document.createElement("div");
    actions.className = "row__actions";
    const status = document.createElement("div");
    status.className = "row__status";
    status.textContent = invite.is_active ? "АКТИВЕН" : "ВЫКЛ";
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "btn btn--ghost btn--small";
    toggleBtn.textContent = invite.is_active ? "Отключить" : "Включить";
    toggleBtn.addEventListener("click", async () => {
      try {
        await api("/api/admin/invites/toggle", {
          method: "POST",
          body: { code: invite.code },
        });
        await loadData();
      } catch (err) {
        setStatus("Не удалось переключить код", true);
      }
    });
    actions.appendChild(status);
    actions.appendChild(toggleBtn);

    item.appendChild(idEl);
    item.appendChild(usesEl);
    item.appendChild(dateEl);
    item.appendChild(actions);
    invitesListEl.appendChild(item);
  });
}

function renderVoting() {
  const classes = state.data?.classes || [];
  const openClasses = classes.filter((c) => c.is_open);
  activeClassHintEl.textContent = state.data?.settings?.active_class_id
    ? `Открыт класс: ${state.data.settings.active_class_id}`
    : "Нет открытого класса";
  fillSelect(openClassEl, classes, (c) => c.class_id, (c) => c.class_id);
  fillSelect(closeClassEl, openClasses, (c) => c.class_id, (c) => c.class_id);

  votingStatusEl.innerHTML = "";
  classes.forEach((cls) => {
    const item = document.createElement("div");
    item.className = "row";
    const progress = cls.progress_total ? `${cls.progress_voted}/${cls.progress_total}` : "—";
    item.innerHTML = `
      <div class="row__id">${cls.class_id}</div>
      <div>${cls.song_title || "—"}</div>
      <div>${progress}</div>
      <div class="row__status">${statusText(cls)}</div>
    `;
    votingStatusEl.appendChild(item);
  });
}

function renderResults() {
  const res = state.data?.results;
  if (!res) return;
  resultsMetaEl.textContent = `Жюри с оценками: ${res.jury_voted}/${res.jury_total} · ${res.generated_at}`;
  resultsListEl.innerHTML = "";
  (res.classes || []).forEach((row, idx) => {
    const item = document.createElement("div");
    item.className = "row";
    const vocalVideo = row.vocal_video_total ?? ((row.vocal_total || 0) + (row.video_total || 0));
    const performance = row.performance_total ?? 0;
    item.innerHTML = `
      <div class="row__id">${idx + 1}</div>
      <div>${row.class_id} — ${row.song_title}</div>
      <div>${row.total}</div>
      <div class="row__status">вокал+видео: ${vocalVideo}, яркость: ${performance}</div>
    `;
    resultsListEl.appendChild(item);
  });
}

function renderLogs() {
  logsListEl.innerHTML = "";
  (state.data?.logs || []).forEach((log) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `
      <div class="row__id">${log.at || ""}</div>
      <div>${log.action}</div>
      <div>${log.actor_telegram_id || "—"}</div>
      <div class="row__status">${log.meta || ""}</div>
    `;
    logsListEl.appendChild(item);
  });
}

function renderAll() {
  renderClasses();
  renderQueue();
  renderCriteria();
  renderUsers();
  renderInvites();
  renderVoting();
  renderResults();
  renderLogs();
}

async function loadData() {
  setStatus("Загрузка данных...");
  const data = await api("/api/admin/bootstrap");
  state.data = data;
  adminLabelEl.textContent = `Админ: ${data.admin?.username || ""}`;
  renderAll();
  setStatus("Готово");
}

async function handleLogin() {
  loginError.textContent = "";
  const username = adminLoginEl.value.trim();
  const password = adminPasswordEl.value.trim();
  if (!username || !password) {
    loginError.textContent = "Введите логин и пароль";
    return;
  }
  try {
    const res = await api("/api/admin/login", {
      method: "POST",
      body: { username, password },
    });
    state.token = res.token;
    saveToken(res.token);
    loginCard.hidden = true;
    adminApp.hidden = false;
    await loadData();
  } catch (err) {
    loginError.textContent = "Не удалось войти";
  }
}

loginBtn.addEventListener("click", handleLogin);

[adminLoginEl, adminPasswordEl].forEach((el) => {
  el.addEventListener("keydown", (event) => {
    if (event.key === "Enter") handleLogin();
  });
});

navEl.addEventListener("click", (event) => {
  const btn = event.target.closest(".nav__btn");
  if (!btn) return;
  showSection(btn.dataset.section);
});

refreshBtn.addEventListener("click", () => {
  loadData().catch(() => setStatus("Не удалось обновить", true));
});

logoutBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/logout", { method: "POST" });
  } catch (err) {
    // ignore
  }
  clearToken();
  state.token = "";
  adminLoginEl.value = "";
  adminPasswordEl.value = "";
  adminApp.hidden = true;
  loginCard.hidden = false;
});

swapBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/queue/swap", {
      method: "POST",
      body: { class_id_a: swapAEl.value, class_id_b: swapBEl.value },
    });
    await loadData();
    setStatus("Очередь обновлена");
  } catch (err) {
    setStatus("Не удалось поменять", true);
  }
});

orderBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/class/order", {
      method: "POST",
      body: { class_id: orderClassEl.value, order: orderValueEl.value },
    });
    await loadData();
    setStatus("Номер обновлен");
  } catch (err) {
    setStatus("Не удалось изменить номер", true);
  }
});

critAddBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/criteria/add", {
      method: "POST",
      body: {
        name: critNameEl.value,
        min_score: critMinEl.value,
        max_score: critMaxEl.value,
        group_key: critGroupEl.value,
      },
    });
    critNameEl.value = "";
    critMinEl.value = "";
    critMaxEl.value = "";
    critGroupEl.value = "";
    await loadData();
    setStatus("Критерий добавлен");
  } catch (err) {
    setStatus("Не удалось добавить критерий", true);
  }
});

critRenameBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/criteria/rename", {
      method: "POST",
      body: { id: critRenameIdEl.value, name: critRenameNameEl.value },
    });
    critRenameNameEl.value = "";
    await loadData();
    setStatus("Критерий переименован");
  } catch (err) {
    setStatus("Не удалось переименовать", true);
  }
});

critDeleteBtn.addEventListener("click", async () => {
  if (!confirm("Удалить критерий?")) return;
  try {
    await api("/api/admin/criteria/delete", {
      method: "POST",
      body: { id: critDeleteIdEl.value },
    });
    await loadData();
    setStatus("Критерий удален");
  } catch (err) {
    setStatus("Не удалось удалить критерий", true);
  }
});

adminCreateBtn.addEventListener("click", async () => {
  try {
    const res = await api("/api/admin/admins/create", {
      method: "POST",
      body: { username: adminCreateNameEl.value },
    });
    adminCreateNameEl.value = "";
    await loadData();
    setStatus(`Создан админ: ${res.username} / ${res.password}`);
  } catch (err) {
    setStatus("Не удалось создать админа", true);
  }
});

juryProfileCreateBtn.addEventListener("click", async () => {
  try {
    const res = await api("/api/admin/jury/create", {
      method: "POST",
      body: { name: juryProfileNameEl.value },
    });
    juryProfileNameEl.value = "";
    await loadData();
    setStatus(`Жюри создано: ${res.name} (код: ${res.code})`);
  } catch (err) {
    setStatus("Не удалось создать жюри", true);
  }
});

inviteCreateBtn.addEventListener("click", async () => {
  try {
    const res = await api("/api/admin/invites/create", { method: "POST" });
    inviteInfoEl.textContent = `Новый код: ${res.code}`;
    await loadData();
  } catch (err) {
    setStatus("Не удалось создать код", true);
  }
});

openBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/voting/open", {
      method: "POST",
      body: { class_id: openClassEl.value },
    });
    await loadData();
    setStatus("Голосование открыто");
  } catch (err) {
    setStatus("Не удалось открыть", true);
  }
});

closeBtn.addEventListener("click", async () => {
  try {
    await api("/api/admin/voting/close", {
      method: "POST",
      body: { class_id: closeClassEl.value },
    });
    await loadData();
    setStatus("Голосование закрыто");
  } catch (err) {
    setStatus("Не удалось закрыть", true);
  }
});

nextBtn.addEventListener("click", async () => {
  try {
    const res = await api("/api/admin/voting/next", { method: "POST" });
    await loadData();
    setStatus(`Открыт следующий: ${res.class_id}`);
  } catch (err) {
    setStatus("Не удалось открыть следующий", true);
  }
});

resultsRefreshBtn.addEventListener("click", async () => {
  try {
    const res = await api("/api/admin/results/partial", { method: "POST" });
    state.data.results = res.results;
    renderResults();
    setStatus("Результаты обновлены");
  } catch (err) {
    setStatus("Не удалось обновить результаты", true);
  }
});

resultsFinalBtn.addEventListener("click", async () => {
  try {
    const res = await api("/api/admin/results/final", { method: "POST" });
    state.data.results = res.results;
    renderResults();
    setStatus("Финальные итоги сформированы");
  } catch (err) {
    if (String(err.message).includes("final_not_ready")) {
      if (confirm("Не все классы завершены. Посчитать финал принудительно?")) {
        try {
          const res = await api("/api/admin/results/final", {
            method: "POST",
            body: { force: true },
          });
          state.data.results = res.results;
          renderResults();
          setStatus("Финальные итоги сформированы");
        } catch (innerErr) {
          setStatus("Не удалось сформировать финал", true);
        }
      }
      return;
    }
    setStatus("Не удалось сформировать финал", true);
  }
});

resetBtn.addEventListener("click", async () => {
  if (!state.resetArmed) {
    state.resetArmed = true;
    resetHintEl.textContent = "Нажмите еще раз для подтверждения";
    if (state.resetTimer) clearTimeout(state.resetTimer);
    state.resetTimer = setTimeout(() => {
      state.resetArmed = false;
      resetHintEl.textContent = "";
    }, 5000);
    return;
  }
  try {
    await api("/api/admin/settings/reset", { method: "POST" });
    state.resetArmed = false;
    resetHintEl.textContent = "";
    await loadData();
    setStatus("Голоса сброшены");
  } catch (err) {
    setStatus("Не удалось сбросить", true);
  }
});

adminApp.addEventListener("click", (event) => {
  const exportBtn = event.target.closest("[data-export]");
  if (exportBtn) {
    downloadExport(exportBtn.dataset.export);
  }
});

const storedToken = loadToken();
if (storedToken) {
  state.token = storedToken;
  loginCard.hidden = true;
  adminApp.hidden = false;
  loadData().catch(() => {
    clearToken();
    adminApp.hidden = true;
    loginCard.hidden = false;
  });
}

showSection(state.section);
