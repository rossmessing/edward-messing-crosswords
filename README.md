# Word Puzzles

A simple, distraction-free crossword-style word game. No ads, no accounts,
no timers or scores — find words from a letter wheel to fill in a grid.
Works entirely in the browser from static files.

## How it works

- `generator/build_puzzles.py` generates puzzles offline: it picks a root
  word, finds every shorter word made from a subset of its letters, and
  lays them into a crossword grid. Output goes to `puzzles/easy/` and
  `puzzles/medium/` as JSON files, plus a `manifest.json` per difficulty
  listing puzzle order.
- `index.html` / `style.css` / `app.js` are the game itself — plain
  JS, no build step, no dependencies.
- Progress (which puzzle you're on) is saved in the browser's
  `localStorage`, per difficulty. No login, no server.

## Regenerating puzzles

```
cd generator
python3 build_puzzles.py
```

Requires `/usr/share/dict/web2` (present by default on macOS) to filter
out proper nouns and non-words from the common-word frequency list.
Commit the regenerated files under `puzzles/` afterward.

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
