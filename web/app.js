const startBtn = document.getElementById("startBtn");
const replayBtn = document.getElementById("replayBtn");
const statusText = document.getElementById("statusText");
const awardsEl = document.getElementById("awards");
const tableBody = document.getElementById("tableBody");
const metaEl = document.getElementById("meta");
const rollOverlay = document.getElementById("rollOverlay");
const rollFill = document.getElementById("rollFill");

const DRUM_DURATION = 4200;

const emptyData = {
  title: "Итоги голосования",
  generated_at: "—",
  jury_voted: 0,
  jury_total: 0,
  classes: [],
};

let state = {
  results: [],
  meta: emptyData,
  running: false,
};

function sortResults(rows) {
  return rows
    .map((r) => ({
      ...r,
      total: Number(r.total || 0),
      vocal_total: Number(r.vocal_total || 0),
      video_total: Number(r.video_total || 0),
      vocal_video_total: Number(r.vocal_video_total || 0),
      performance_total: Number(r.performance_total || 0),
      performance_order: Number(r.performance_order || 0),
      parallel: Number(r.parallel || 0),
      song_title: r.song_title || "—",
      class_id: r.class_id || "—",
    }))
    .sort((a, b) => {
      if (b.total !== a.total) return b.total - a.total;
      const aPerformance = a.performance_total || 0;
      const bPerformance = b.performance_total || 0;
      if (bPerformance !== aPerformance) return bPerformance - aPerformance;
      if (a.performance_order !== b.performance_order) {
        return a.performance_order - b.performance_order;
      }
      return a.class_id.localeCompare(b.class_id, "ru", { numeric: true });
    });
}

function buildAwards(rows) {
  if (!rows.length) {
    return { grand_prix: null, parallels: [] };
  }
  const ordered = sortResults(rows);
  const grand_prix = ordered[0] || null;
  const byParallel = {};
  ordered.forEach((row) => {
    if (grand_prix && row.class_id === grand_prix.class_id) return;
    const parallel = Number(row.parallel || 0);
    if (!byParallel[parallel]) byParallel[parallel] = [];
    byParallel[parallel].push(row);
  });
  const parallels = Object.keys(byParallel)
    .map((p) => Number(p))
    .sort((a, b) => a - b)
    .map((parallel) => {
      const list = byParallel[parallel] || [];
      return {
        parallel,
        gold: list[0] || null,
        silver: list[1] || null,
      };
    });
  return { grand_prix, parallels };
}

function resolveAward(row, lookup) {
  if (!row) return null;
  const base = lookup.get(row.class_id) || row;
  return {
    ...base,
    ...row,
    total: Number((row.total ?? base.total) || 0),
    vocal_total: Number((row.vocal_total ?? base.vocal_total) || 0),
    video_total: Number((row.video_total ?? base.video_total) || 0),
    vocal_video_total: Number((row.vocal_video_total ?? base.vocal_video_total) || 0),
    performance_total: Number((row.performance_total ?? base.performance_total) || 0),
    performance_order: Number((row.performance_order ?? base.performance_order) || 0),
    parallel: Number((row.parallel ?? base.parallel) || 0),
    song_title: (row.song_title ?? base.song_title) || "—",
    class_id: row.class_id || base.class_id || "—",
  };
}

async function loadResults() {
  try {
    const res = await fetch("results.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no data");
    const data = await res.json();
    return data;
  } catch (err) {
    return emptyData;
  }
}

function render(results, meta) {
  awardsEl.innerHTML = "";
  tableBody.innerHTML = "";

  const metaParts = [];
  if (meta.jury_total) {
    metaParts.push(`Жюри: ${meta.jury_voted || 0}/${meta.jury_total}`);
  }
  if (meta.generated_at) {
    metaParts.push(`Обновлено: ${meta.generated_at}`);
  }
  metaEl.textContent = metaParts.join(" · ");

  const awards = meta.awards && (meta.awards.grand_prix || meta.awards.parallels?.length)
    ? meta.awards
    : buildAwards(results);
  const lookup = new Map(results.map((row) => [row.class_id, row]));

  const grand = resolveAward(awards.grand_prix, lookup);
  const grandCard = document.createElement("div");
  grandCard.className = "award-card award-card--grand";
  grandCard.innerHTML = `
    <div class="award-card__label">Гран-при</div>
    <div class="award-card__class">${grand ? grand.class_id : "—"}</div>
    <div class="award-card__song">${grand ? grand.song_title : "—"}</div>
    ${
      grand
        ? `<div class="award-card__score" data-score="${grand.total}">0</div>`
        : `<div class="award-card__score">—</div>`
    }
  `;
  awardsEl.appendChild(grandCard);

  const parallels = Array.isArray(awards.parallels) ? awards.parallels : [];
  parallels.forEach((item) => {
    const parallel = item?.parallel ?? "—";
    const gold = resolveAward(item?.gold, lookup);
    const silver = resolveAward(item?.silver, lookup);

    const card = document.createElement("div");
    card.className = "parallel-card";
    card.innerHTML = `
      <div class="parallel-card__title">${parallel} параллель</div>
      <div class="parallel-card__slot">
        <div class="parallel-card__medal">🥇 Золото</div>
        <div class="parallel-card__class">${gold ? gold.class_id : "—"}</div>
        <div class="parallel-card__song">${gold ? gold.song_title : "—"}</div>
        ${
          gold
            ? `<div class="parallel-card__score" data-score="${gold.total}">0</div>`
            : `<div class="parallel-card__score">—</div>`
        }
      </div>
      <div class="parallel-card__slot">
        <div class="parallel-card__medal">🥈 Серебро</div>
        <div class="parallel-card__class">${silver ? silver.class_id : "—"}</div>
        <div class="parallel-card__song">${silver ? silver.song_title : "—"}</div>
        ${
          silver
            ? `<div class="parallel-card__score" data-score="${silver.total}">0</div>`
            : `<div class="parallel-card__score">—</div>`
        }
      </div>
    `;
    awardsEl.appendChild(card);
  });

  results.forEach((row, index) => {
    const item = document.createElement("div");
    item.className = "table__row";
    item.innerHTML = `
      <div>${index + 1}</div>
      <div>${row.class_id}</div>
      <div>${row.song_title}</div>
      <div class="table__score" data-score="${row.total}">0</div>
    `;
    tableBody.appendChild(item);
  });
}

function animateScores() {
  const scoreEls = document.querySelectorAll("[data-score]");
  scoreEls.forEach((el, idx) => {
    const target = Number(el.getAttribute("data-score")) || 0;
    const delay = idx * 80;
    countUp(el, target, 1400, delay);
  });
}

function revealRows() {
  document.querySelectorAll(".award-card, .parallel-card").forEach((card, idx) => {
    setTimeout(() => card.classList.add("reveal"), 200 + idx * 160);
  });
  document.querySelectorAll(".table__row").forEach((row, idx) => {
    setTimeout(() => row.classList.add("reveal"), 500 + idx * 60);
  });
}

function countUp(el, target, duration, delay) {
  const start = performance.now() + delay;
  const end = start + duration;

  function frame(now) {
    if (now < start) {
      requestAnimationFrame(frame);
      return;
    }
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(target * eased);
    el.textContent = value.toString();
    if (progress < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

function playDrumRoll(durationMs) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const now = ctx.currentTime;
    const end = now + durationMs / 1000;
    const startInterval = 0.18;
    const endInterval = 0.06;

    function createHit(time, velocity) {
      const noiseLength = Math.floor(ctx.sampleRate * 0.12);
      const buffer = ctx.createBuffer(1, noiseLength, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < noiseLength; i += 1) {
        const decay = 1 - i / noiseLength;
        data[i] = (Math.random() * 2 - 1) * decay * 0.9;
      }

      const source = ctx.createBufferSource();
      source.buffer = buffer;

      const filter = ctx.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.value = 1800;
      filter.Q.value = 0.9;

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(velocity, time);
      gain.gain.exponentialRampToValueAtTime(0.001, time + 0.12);

      source.connect(filter).connect(gain).connect(ctx.destination);
      source.start(time);
      source.stop(time + 0.12);
    }

    let t = now + 0.05;
    while (t < end) {
      const progress = (t - now) / (end - now);
      const interval = startInterval - (startInterval - endInterval) * progress;
      const velocity = 0.7 + progress * 0.3;
      createHit(t, velocity);
      t += interval;
    }
  } catch (err) {
    // Без звука, если браузер блокирует AudioContext
  }
}

function startRoll() {
  rollOverlay.classList.add("show");
  rollFill.style.width = "0%";
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / DRUM_DURATION, 1);
    rollFill.style.width = `${Math.floor(progress * 100)}%`;
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function stopRoll() {
  rollOverlay.classList.remove("show");
  rollFill.style.width = "0%";
}

async function runShow() {
  if (state.running) return;
  state.running = true;
  statusText.textContent = "Подсчёт результатов...";
  startBtn.disabled = true;
  replayBtn.disabled = true;

  const data = await loadResults();
  const rows = sortResults(data.classes || []);
  state.results = rows;
  state.meta = data;

  render(rows, data);
  startRoll();
  playDrumRoll(DRUM_DURATION);

  setTimeout(() => {
    stopRoll();
    revealRows();
    animateScores();
    statusText.textContent = "Результаты показаны";
    replayBtn.disabled = false;
    state.running = false;
  }, DRUM_DURATION + 300);
}

startBtn.addEventListener("click", runShow);
replayBtn.addEventListener("click", () => {
  runShow();
});

(async () => {
  const data = await loadResults();
  const rows = sortResults(data.classes || []);
  render(rows, data);
})();
