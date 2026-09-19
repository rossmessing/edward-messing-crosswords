(function () {
  "use strict";

  const DIFFICULTIES = ["easy", "medium"];
  const STORAGE_KEY = "crossjam-progress";

  const el = {
    home: document.getElementById("screen-home"),
    game: document.getElementById("screen-game"),
    complete: document.getElementById("overlay-complete"),
    btnEasy: document.getElementById("btn-easy"),
    btnMedium: document.getElementById("btn-medium"),
    easyProgress: document.getElementById("easy-progress"),
    mediumProgress: document.getElementById("medium-progress"),
    btnBack: document.getElementById("btn-back"),
    grid: document.getElementById("grid"),
    attemptDisplay: document.getElementById("attempt-display"),
    wheel: document.getElementById("wheel"),
    btnClear: document.getElementById("btn-clear"),
    btnShuffle: document.getElementById("btn-shuffle"),
    btnNext: document.getElementById("btn-next"),
    btnMenu: document.getElementById("btn-menu"),
    bonusCounter: document.getElementById("bonus-counter"),
    bonusCount: document.getElementById("bonus-count"),
  };

  let manifests = {}; // difficulty -> [ids]
  let state = null; // current puzzle play state

  // ---------- progress persistence ----------

  function loadProgress() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {
      /* ignore corrupt/unavailable storage */
    }
    return {};
  }

  function saveProgress(progress) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
    } catch (e) {
      /* ignore unavailable storage */
    }
  }

  function getIndex(difficulty) {
    const progress = loadProgress();
    return (progress[difficulty] && progress[difficulty].index) || 0;
  }

  function advanceIndex(difficulty) {
    const progress = loadProgress();
    const total = manifests[difficulty].length;
    const current = (progress[difficulty] && progress[difficulty].index) || 0;
    progress[difficulty] = { index: (current + 1) % total };
    saveProgress(progress);
  }

  // ---------- data loading ----------

  async function loadManifests() {
    for (const difficulty of DIFFICULTIES) {
      const res = await fetch(`puzzles/${difficulty}/manifest.json`);
      manifests[difficulty] = await res.json();
    }
  }

  async function loadPuzzle(difficulty, index) {
    const id = manifests[difficulty][index];
    const res = await fetch(`puzzles/${difficulty}/${id}.json`);
    return res.json();
  }

  // ---------- home screen ----------

  function renderHomeProgress() {
    for (const difficulty of DIFFICULTIES) {
      const total = manifests[difficulty].length;
      const index = Math.min(getIndex(difficulty), total - 1);
      const label = `Puzzle ${index + 1} of ${total}`;
      if (difficulty === "easy") el.easyProgress.textContent = label;
      if (difficulty === "medium") el.mediumProgress.textContent = label;
    }
  }

  function showHome() {
    el.game.hidden = true;
    el.complete.hidden = true;
    el.home.hidden = false;
    renderHomeProgress();
  }

  // ---------- game screen ----------

  async function startPuzzle(difficulty) {
    const index = getIndex(difficulty);
    const puzzle = await loadPuzzle(difficulty, index);
    beginState(difficulty, puzzle);
    el.home.hidden = true;
    el.complete.hidden = true;
    el.game.hidden = false;
  }

  function buildGridCells(puzzle) {
    const { width, height } = puzzle.grid;
    const cells = Array.from({ length: height }, () =>
      Array.from({ length: width }, () => null)
    );
    for (const w of puzzle.words) {
      for (let i = 0; i < w.word.length; i++) {
        const r = w.dir === "down" ? w.row + i : w.row;
        const c = w.dir === "down" ? w.col : w.col + i;
        cells[r][c] = { letter: w.word[i], revealed: false };
      }
    }
    return cells;
  }

  function beginState(difficulty, puzzle) {
    state = {
      difficulty,
      puzzle,
      cells: buildGridCells(puzzle),
      foundWords: new Set(),
      foundBonusWords: new Set(),
      letters: shuffledLetters(puzzle.letters),
      usedTiles: new Set(),
      attempt: [],
      layout: computeLayout(puzzle),
    };
    renderGrid();
    renderWheel();
    renderAttempt();
    renderBonusCounter();
  }

  function shuffledLetters(letters) {
    const arr = letters.slice();
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  // Sizes the grid and wheel to fit whatever vertical space is actually
  // available, so Clear/Shuffle never get pushed off-screen and no tile
  // in the wheel ever depends on scrolling to become reachable.
  function computeLayout(puzzle) {
    const { width, height } = puzzle.grid;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    const topClearance = 64; // back button
    const bottomControls = 110; // controls row + gaps
    const attemptHeight = 44;
    const innerGaps = 32; // gaps between grid/attempt/wheel
    const safetyMargin = 30;
    const availableHeight = Math.max(
      260,
      vh - topClearance - bottomControls - attemptHeight - innerGaps - safetyMargin
    );

    const wheelSize = Math.max(
      200,
      Math.min(340, vw * 0.78, availableHeight * 0.55)
    );

    const gridAvailableHeight = availableHeight - wheelSize;
    const cellByWidth = Math.floor(Math.min(vw * 0.9, 380) / width);
    const cellByHeight = Math.floor(gridAvailableHeight / height);
    const cellSize = Math.max(16, Math.min(38, cellByWidth, cellByHeight));

    const tileSize = Math.max(44, Math.min(68, wheelSize / 3.4));

    return { cellSize, wheelSize, tileSize };
  }

  function renderGrid() {
    const { width, height } = state.puzzle.grid;
    el.grid.style.gridTemplateColumns = `repeat(${width}, var(--cell-size, 38px))`;
    el.grid.style.setProperty("--cell-size", `${state.layout.cellSize}px`);

    el.grid.innerHTML = "";
    for (let r = 0; r < height; r++) {
      for (let c = 0; c < width; c++) {
        const cell = state.cells[r][c];
        const div = document.createElement("div");
        if (!cell) {
          div.className = "cell empty";
        } else if (cell.revealed) {
          div.className = "cell filled";
          div.textContent = cell.letter;
        } else {
          div.className = "cell blank";
        }
        el.grid.appendChild(div);
      }
    }
  }

  function renderWheel() {
    const { wheelSize, tileSize } = state.layout;
    el.wheel.style.setProperty("--wheel-size", `${wheelSize}px`);
    el.wheel.style.setProperty("--tile-size", `${tileSize}px`);

    el.wheel.innerHTML = "";
    const letters = state.letters;
    const n = letters.length;
    const radius = wheelSize / 2 - tileSize / 2 - 6;
    letters.forEach((letter, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      const x = radius * Math.cos(angle);
      const y = radius * Math.sin(angle);
      const btn = document.createElement("button");
      btn.className = "tile";
      btn.textContent = letter;
      btn.style.transform = `translate(${x}px, ${y}px)`;
      btn.dataset.index = i;
      if (state.usedTiles.has(i)) btn.classList.add("used");
      btn.addEventListener("click", () => onTileTap(i));
      el.wheel.appendChild(btn);
    });
  }

  function renderAttempt() {
    el.attemptDisplay.textContent = state.attempt.map((t) => t.letter).join("");
  }

  function onTileTap(index) {
    if (state.usedTiles.has(index)) return;
    state.usedTiles.add(index);
    state.attempt.push({ index, letter: state.letters[index] });
    renderWheel();
    renderAttempt();
    checkAttempt();
  }

  function checkAttempt() {
    const word = state.attempt.map((t) => t.letter).join("");
    if (state.foundWords.has(word)) return;

    const match = state.puzzle.words.find((w) => w.word === word);
    if (match) {
      state.foundWords.add(word);
      for (let i = 0; i < match.word.length; i++) {
        const r = match.dir === "down" ? match.row + i : match.row;
        const c = match.dir === "down" ? match.col : match.col + i;
        state.cells[r][c].revealed = true;
      }
      clearAttempt();
      renderGrid();

      if (state.foundWords.size === state.puzzle.words.length) {
        setTimeout(showComplete, 300);
      }
      return;
    }

    // Not a grid word - check whether it's a valid "bonus" word instead.
    // Bonus words are real words formable from the wheel that just
    // aren't part of the visible grid; finding one only bumps a small
    // counter, it never affects puzzle completion.
    const bonusWords = state.puzzle.bonus_words || [];
    if (!state.foundBonusWords.has(word) && bonusWords.includes(word)) {
      state.foundBonusWords.add(word);
      clearAttempt();
      renderBonusCounter();
    }
  }

  function renderBonusCounter() {
    const total = (state.puzzle.bonus_words || []).length;
    if (total === 0) {
      el.bonusCounter.hidden = true;
      return;
    }
    el.bonusCounter.hidden = false;
    el.bonusCount.textContent = state.foundBonusWords.size;
  }

  function clearAttempt() {
    state.attempt = [];
    state.usedTiles = new Set();
    renderWheel();
    renderAttempt();
  }

  function shuffleWheel() {
    if (state.attempt.length > 0) return;
    state.letters = shuffledLetters(state.letters);
    renderWheel();
  }

  function showComplete() {
    el.complete.hidden = false;
    advanceIndex(state.difficulty);
  }

  async function nextPuzzle() {
    const difficulty = state.difficulty;
    const puzzle = await loadPuzzle(difficulty, getIndex(difficulty));
    beginState(difficulty, puzzle);
    el.complete.hidden = true;
  }

  // ---------- wiring ----------

  el.btnEasy.addEventListener("click", () => startPuzzle("easy"));
  el.btnMedium.addEventListener("click", () => startPuzzle("medium"));
  el.btnBack.addEventListener("click", showHome);
  el.btnClear.addEventListener("click", clearAttempt);
  el.btnShuffle.addEventListener("click", shuffleWheel);
  el.btnNext.addEventListener("click", nextPuzzle);
  el.btnMenu.addEventListener("click", showHome);

  window.addEventListener("resize", () => {
    if (!state || el.game.hidden) return;
    state.layout = computeLayout(state.puzzle);
    renderGrid();
    renderWheel();
  });

  loadManifests().then(showHome);
})();
