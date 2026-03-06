const loginCard = document.getElementById("loginCard");
const board = document.getElementById("board");
const juryCodeEl = document.getElementById("juryCode");
const juryNameEl = document.getElementById("juryName");
const loginBtn = document.getElementById("loginBtn");
const loginError = document.getElementById("loginError");
const refreshBtn = document.getElementById("refreshBtn");
const logoutBtn = document.getElementById("logoutBtn");
const classListEl = document.getElementById("classList");
const criteriaListEl = document.getElementById("criteriaList");
const classTitleEl = document.getElementById("classTitle");
const classStatusEl = document.getElementById("classStatus");
const classMetaEl = document.getElementById("classMeta");
const activeHintEl = document.getElementById("activeHint");
const mySummaryEl = document.getElementById("mySummary");
const myProgressEl = document.getElementById("myProgress");
const statusBarEl = document.getElementById("statusBar");
const juryLabelEl = document.getElementById("juryLabel");
const notifyEl = document.getElementById("notify");
const notifyTextEl = document.getElementById("notifyText");
const notifyGoBtn = document.getElementById("notifyGo");
const notifyCloseBtn = document.getElementById("notifyClose");

const STORAGE_KEY = "juri-web-auth";
const AUTO_REFRESH_MS = 10000;

const state = {
  code: "",
  name: "",
  data: null,
  voteMap: {},
  selectedClass: "",
  refreshTimer: null,
  isBootstrapping: false,
  isRefreshingClasses: false,
  notifiedOpen: {},
  pendingOpenClassId: "",
};

function setStatus(message, isError = false) {
  statusBarEl.textContent = message;
  statusBarEl.style.color = isError ? "#f87171" : "";
}

function loadAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (err) {
    return null;
  }
}

function saveAuth(code, name) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ code, name }));
}

function clearAuth() {
  localStorage.removeItem(STORAGE_KEY);
}

function buildVoteMap(votes) {
  const map = {};
  votes.forEach((v) => {
    if (!map[v.class_id]) map[v.class_id] = {};
    map[v.class_id][String(v.criterion_id)] = Number(v.score);
  });
  return map;
}

function getScore(classId, criterionId) {
  return state.voteMap[classId]?.[String(criterionId)];
}

function getClassById(classId) {
  return (state.data?.classes || []).find((c) => c.class_id === classId);
}

function statusText(cls) {
  if (cls.is_open) return "ОТКРЫТО";
  if (cls.is_finished) return "ЗАВЕРШЕНО";
  return "ЗАКРЫТО";
}

function pickDefaultClass(data, preferred) {
  if (!data) return "";
  if (preferred && data.classes.some((c) => c.class_id === preferred)) return preferred;
  if (data.active_class_id) return data.active_class_id;
  const open = data.classes.find((c) => c.is_open);
  if (open) return open.class_id;
  return data.classes.length ? data.classes[0].class_id : "";
}

function detectOpenedClass(prevData, nextData) {
  if (!prevData || !nextData) return null;
  const prevOpen = new Set((prevData.classes || []).filter((c) => c.is_open).map((c) => c.class_id));
  const nextOpen = (nextData.classes || []).filter((c) => c.is_open);
  const newlyOpened = nextOpen.find((c) => !prevOpen.has(c.class_id));
  if (newlyOpened) return newlyOpened;
  if (prevData.active_class_id !== nextData.active_class_id && nextData.active_class_id) {
    return (
      (nextData.classes || []).find((c) => c.class_id === nextData.active_class_id) || {
        class_id: nextData.active_class_id,
        song_title: "—",
      }
    );
  }
  return null;
}

function hideNotification() {
  notifyEl.hidden = true;
  state.pendingOpenClassId = "";
}

function showNotification(cls) {
  if (!cls || !cls.class_id) return;
  if (state.notifiedOpen[cls.class_id]) return;
  state.notifiedOpen[cls.class_id] = true;
  state.pendingOpenClassId = cls.class_id;
  notifyTextEl.textContent = `Голосование открыто для класса ${cls.class_id}! Нажмите, чтобы перейти к голосованию.`;
  notifyEl.hidden = false;
}

function focusClass(classId) {
  if (!classId) return;
  state.selectedClass = classId;
  renderAll();
  criteriaListEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function fetchBootstrap() {
  const params = new URLSearchParams({
    jury_code: state.code,
    jury_name: state.name,
  });
  const res = await fetch(`/api/bootstrap?${params.toString()}`, {
    cache: "no-store",
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "bootstrap_failed");
  }
  return data;
}

async function bootstrap(options = {}) {
  const { silent = false } = options;
  if (state.isBootstrapping) return;
  state.isBootstrapping = true;
  if (!silent) setStatus("Загрузка данных...");
  try {
    const prevData = state.data;
    const prevSelected = state.selectedClass;
    const data = await fetchBootstrap();
    const openedClass = detectOpenedClass(prevData, data);
    const openIds = new Set((data.classes || []).filter((c) => c.is_open).map((c) => c.class_id));
    Object.keys(state.notifiedOpen).forEach((classId) => {
      if (!openIds.has(classId)) delete state.notifiedOpen[classId];
    });
    if (state.pendingOpenClassId && !openIds.has(state.pendingOpenClassId)) {
      hideNotification();
    }
    state.data = data;
    state.voteMap = buildVoteMap(data.votes || []);
    state.selectedClass = pickDefaultClass(data, prevSelected);
    loginCard.hidden = true;
    board.hidden = false;
    juryLabelEl.textContent = `Код: ${state.code}${state.name ? ` · ${state.name}` : ""}`;
    renderAll();
    if (openedClass) showNotification(openedClass);
    if (!silent) setStatus("Готово к оцениванию");
  } finally {
    state.isBootstrapping = false;
  }
}

async function refreshClassesOnly() {
  if (state.isBootstrapping || state.isRefreshingClasses) return;
  if (!state.data) return;
  state.isRefreshingClasses = true;
  try {
    const prevData = state.data;
    const data = await fetchBootstrap();
    const openedClass = detectOpenedClass(prevData, data);
    const openIds = new Set((data.classes || []).filter((c) => c.is_open).map((c) => c.class_id));
    Object.keys(state.notifiedOpen).forEach((classId) => {
      if (!openIds.has(classId)) delete state.notifiedOpen[classId];
    });
    if (state.pendingOpenClassId && !openIds.has(state.pendingOpenClassId)) {
      hideNotification();
    }

    state.data.classes = data.classes;
    state.data.active_class_id = data.active_class_id;
    renderClassList();
    if (openedClass) showNotification(openedClass);
  } finally {
    state.isRefreshingClasses = false;
  }
}

function renderAll() {
  renderClassList();
  renderClassDetails();
  renderSummary();
}

function renderClassList() {
  classListEl.innerHTML = "";
  if (!state.data) return;
  const activeId = state.data.active_class_id || "";
  activeHintEl.textContent = activeId ? `Открыт класс: ${activeId}` : "Нет открытого класса";

  state.data.classes.forEach((cls) => {
    const card = document.createElement("div");
    card.className = "class-item";
    if (cls.is_open) card.classList.add("class-item--open");
    else if (cls.is_finished) card.classList.add("class-item--finished");
    else card.classList.add("class-item--closed");
    if (cls.class_id === state.selectedClass) card.classList.add("class-item--active");
    card.dataset.classId = cls.class_id;

    const idEl = document.createElement("div");
    idEl.className = "class-item__id";
    idEl.textContent = cls.class_id;

    const songEl = document.createElement("div");
    songEl.className = "class-item__song";
    songEl.textContent = cls.song_title || "—";

    const statusEl = document.createElement("div");
    statusEl.className = "class-item__status";
    statusEl.textContent = statusText(cls);

    card.appendChild(idEl);
    card.appendChild(songEl);
    card.appendChild(statusEl);
    classListEl.appendChild(card);
  });
}

function renderClassDetails() {
  criteriaListEl.innerHTML = "";
  classMetaEl.textContent = "";
  classStatusEl.textContent = "";
  myProgressEl.textContent = "";

  const cls = getClassById(state.selectedClass);
  if (!cls || !state.data) {
    classTitleEl.textContent = "Выберите класс";
    return;
  }

  classTitleEl.textContent = `Класс ${cls.class_id}`;
  classStatusEl.textContent = statusText(cls);
  classMetaEl.textContent = `Песня: ${cls.song_title || "—"} · № в очереди: ${cls.performance_order}`;

  const criteria = state.data.criteria || [];
  criteria.forEach((crit) => {
    const row = document.createElement("div");
    row.className = "criteria__row";

    const nameEl = document.createElement("div");
    nameEl.className = "criteria__name";
    nameEl.textContent = crit.name;

    const rangeEl = document.createElement("div");
    rangeEl.className = "criteria__range";
    rangeEl.textContent = `${crit.min_score}-${crit.max_score}`;

    const inputWrap = document.createElement("div");
    inputWrap.className = "criteria__input";
    const select = document.createElement("select");
    const currentScore = getScore(cls.class_id, crit.id);
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Выберите";
    placeholder.disabled = true;
    placeholder.selected = currentScore === undefined;
    select.appendChild(placeholder);
    for (let value = crit.min_score; value <= crit.max_score; value += 1) {
      const opt = document.createElement("option");
      opt.value = String(value);
      opt.textContent = String(value);
      if (currentScore !== undefined && Number(currentScore) === value) {
        opt.selected = true;
      }
      select.appendChild(opt);
    }
    select.disabled = !cls.is_open;
    inputWrap.appendChild(select);

    const statusEl = document.createElement("div");
    statusEl.className = "criteria__status";
    statusEl.textContent = currentScore !== undefined ? "Сохранено" : "—";

    select.addEventListener("change", async () => {
      if (select.disabled) return;
      const raw = select.value.trim();
      if (!raw) {
        statusEl.textContent = "—";
        return;
      }
      const score = Number(raw);
      if (Number.isNaN(score)) {
        statusEl.textContent = "Ошибка";
        return;
      }
      statusEl.textContent = "Сохранение...";
      try {
        await submitScore(cls.class_id, crit.id, score);
        if (!state.voteMap[cls.class_id]) state.voteMap[cls.class_id] = {};
        state.voteMap[cls.class_id][String(crit.id)] = score;
        statusEl.textContent = "Сохранено";
        renderSummary();
        setStatus(`Оценка сохранена: ${cls.class_id}, ${crit.name}`);
      } catch (err) {
        statusEl.textContent = "Ошибка";
        setStatus("Не удалось сохранить оценку", true);
      }
    });

    row.appendChild(nameEl);
    row.appendChild(rangeEl);
    row.appendChild(inputWrap);
    row.appendChild(statusEl);
    criteriaListEl.appendChild(row);
  });

  const votedCount = Object.keys(state.voteMap[cls.class_id] || {}).length;
  myProgressEl.textContent = `Оценено критериев: ${votedCount}/${criteria.length}`;
}

function renderSummary() {
  mySummaryEl.innerHTML = "";
  if (!state.data) return;

  const rows = [];
  state.data.classes.forEach((cls) => {
    const scores = state.voteMap[cls.class_id];
    if (!scores) return;
    const total = Object.values(scores).reduce((sum, value) => sum + Number(value || 0), 0);
    const count = Object.keys(scores).length;
    rows.push({ class_id: cls.class_id, total, count });
  });

  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "panel__meta";
    empty.textContent = "Пока нет оценок.";
    mySummaryEl.appendChild(empty);
    return;
  }

  rows.sort((a, b) => a.class_id.localeCompare(b.class_id));
  rows.forEach((row) => {
    const line = document.createElement("div");
    line.className = "summary__row";
    line.textContent = `${row.class_id} — ${row.total} балл. (${row.count})`;
    mySummaryEl.appendChild(line);
  });
}

async function submitScore(classId, criterionId, score) {
  const res = await fetch("/api/score", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      jury_code: state.code,
      jury_name: state.name,
      class_id: classId,
      criterion_id: criterionId,
      score,
    }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "save_failed");
  }
  return data;
}

async function handleLogin() {
  loginError.textContent = "";
  const code = juryCodeEl.value.trim();
  const name = juryNameEl.value.trim();
  if (!code) {
    loginError.textContent = "Введите код жюри";
    return;
  }
  state.code = code;
  state.name = name;
  saveAuth(code, name);
  try {
    await bootstrap();
    if (!state.refreshTimer) {
      state.refreshTimer = setInterval(() => {
        if (board.hidden) return;
        refreshClassesOnly().catch(() => {});
      }, AUTO_REFRESH_MS);
    }
  } catch (err) {
    loginError.textContent = "Не удалось войти. Проверьте код.";
  }
}

loginBtn.addEventListener("click", handleLogin);

[juryCodeEl, juryNameEl].forEach((el) => {
  el.addEventListener("keydown", (event) => {
    if (event.key === "Enter") handleLogin();
  });
});

classListEl.addEventListener("click", (event) => {
  const card = event.target.closest(".class-item");
  if (!card) return;
  const classId = card.dataset.classId;
  if (!classId || classId === state.selectedClass) return;
  state.selectedClass = classId;
  renderAll();
  if (classId === state.pendingOpenClassId) hideNotification();
});

refreshBtn.addEventListener("click", async () => {
  try {
    await bootstrap();
  } catch (err) {
    setStatus("Не удалось обновить данные", true);
  }
});

logoutBtn.addEventListener("click", () => {
  clearAuth();
  state.code = "";
  state.name = "";
  state.data = null;
  state.voteMap = {};
  state.selectedClass = "";
  state.notifiedOpen = {};
  board.hidden = true;
  loginCard.hidden = false;
  juryCodeEl.value = "";
  juryNameEl.value = "";
  loginError.textContent = "";
  hideNotification();
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
});

const stored = loadAuth();
if (stored && stored.code) {
  state.code = stored.code;
  state.name = stored.name || "";
  juryCodeEl.value = state.code;
  juryNameEl.value = state.name;
  bootstrap().then(() => {
    if (!state.refreshTimer) {
      state.refreshTimer = setInterval(() => {
        if (board.hidden) return;
        refreshClassesOnly().catch(() => {});
      }, AUTO_REFRESH_MS);
    }
  }).catch(() => {
    clearAuth();
  });
}

notifyGoBtn.addEventListener("click", () => {
  if (!state.pendingOpenClassId) return;
  focusClass(state.pendingOpenClassId);
  hideNotification();
});

notifyCloseBtn.addEventListener("click", hideNotification);
