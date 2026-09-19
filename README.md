# Word Puzzles

A simple, distraction-free crossword-style word game. No ads, no accounts,
no timers or scores — find words from a letter wheel to fill in a grid.
Works entirely in the browser from static files.

## How it works

- `generator/build_puzzles.py` generates puzzles offline: it picks a root
  word, finds every shorter word made from a subset of its letters, and
  lays as many as look reasonable into a crossword grid. Any other valid
  word it found but didn't draw into the grid is kept as a "bonus" word —
  typing one still registers (bumps a small counter) without ever
  appearing on screen, so almost anything a player reasonably tries just
  works. Output goes to `puzzles/easy/` and `puzzles/medium/` as JSON
  files, plus a `manifest.json` per difficulty listing puzzle order.
- `index.html` / `style.css` / `app.js` are the game itself — plain
  JS, no build step, no dependencies.
- Progress (which puzzle you're on) is saved in the browser's
  `localStorage`, per difficulty. No login, no server.

## Word sources

Two word lists feed the generator, both auto-downloaded on first run:

- A small curated ~4000-word common-words list — used for root words and
  anything actually drawn into the grid, since that's always visible and
  needs to be unambiguously ordinary.
- A much larger real-world word-frequency list — used only to recognize
  bonus words, since those are never shown on screen.

Both are filtered against the system dictionary (`/usr/share/dict/web2`,
present by default on macOS) and `/usr/share/dict/propernames` to drop
non-words and proper nouns, plus a small hand-maintained `BLOCKLIST` in
`build_puzzles.py` for anything that slips through both (abbreviations,
archaic/dialectal terms, or anything too heavy/clinical-themed for a
casual game). If you spot a bad word in a generated puzzle, add it to
`BLOCKLIST` and regenerate.

## Regenerating puzzles

```
cd generator
python3 build_puzzles.py
```

Commit the regenerated files under `puzzles/` afterward. The raw
downloaded wordlists (`generator/wordlist_raw.txt`,
`generator/wordlist_bonus_raw.txt`) are gitignored — they're re-fetched
automatically if missing.

## Running locally

```
python3 -m http.server 8765
```

Then open `http://localhost:8765/`.

## Deploying to GitHub Pages

1. Push this repo to GitHub.
2. In the repo settings, under **Pages**, set the source to the `main`
   branch, root folder.
3. The site will be live at `https://<username>.github.io/<repo>/`.
