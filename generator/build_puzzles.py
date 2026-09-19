#!/usr/bin/env python3
"""Generates crossword-jam-style puzzles from a common-words list.

For each puzzle: pick a "root" word, find every shorter word in the
wordlist whose letters are a subset of the root's letters, then lay
as many of those words as possible into a crossword grid. The root
word's letters become the letter wheel the player taps from.

Output: one JSON file per puzzle under puzzles/<difficulty>/, plus a
manifest.json per difficulty listing puzzle ids in play order.
"""

import json
import random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
WORDLIST_RAW = HERE / "wordlist_raw.txt"
SYSTEM_DICT = Path("/usr/share/dict/web2")
PUZZLES_DIR = HERE.parent / "puzzles"

MIN_SUBWORD_LEN = 3
# Only take the N most frequent words from the raw list. The full list
# trails off into obscure/technical terms ("ide", "rfc"-style noise);
# capping rank keeps everything recognizable to a casual player.
FREQUENCY_RANK_CUTOFF = 4000

DIFFICULTIES = {
    "easy": {
        "root_len": (5, 6),
        "min_placed": 5,
        "target_placed": 8,
        "count": 15,
    },
    "medium": {
        "root_len": (7, 8),
        "min_placed": 7,
        "target_placed": 11,
        "count": 15,
    },
}

RNG_SEED = 42


def load_wordlist():
    """Intersect a common-word frequency list with a real dictionary.

    The frequency list alone contains web-scraped junk (abbreviations
    like "ncaa"/"rfc", frequency-list noise like "ata") and proper
    nouns (e.g. "iran", capitalized in the dictionary). Requiring an
    exact case-sensitive lowercase match against the system dictionary
    filters both out, since proper nouns only appear capitalized there.
    """
    words = set()
    lines = WORDLIST_RAW.read_text().splitlines()[:FREQUENCY_RANK_CUTOFF]
    for line in lines:
        w = line.strip().lower()
        if w.isalpha() and len(w) >= MIN_SUBWORD_LEN:
            words.add(w)

    if SYSTEM_DICT.exists():
        dict_words = set(SYSTEM_DICT.read_text(errors="ignore").splitlines())
        words = {w for w in words if w in dict_words}
    else:
        print(f"warning: {SYSTEM_DICT} not found, skipping real-word filter")

    return words


def is_subword(word, root_counter):
    wc = Counter(word)
    for letter, n in wc.items():
        if root_counter.get(letter, 0) < n:
            return False
    return True


def find_subwords(root, all_words):
    root_counter = Counter(root)
    matches = [
        w for w in all_words
        if w != root and len(w) <= len(root) and is_subword(w, root_counter)
    ]
    matches.sort(key=len, reverse=True)
    return matches


class Grid:
    def __init__(self):
        self.cells = {}  # (row, col) -> letter

    def can_place(self, word, row, col, vertical):
        cells_to_fill = []
        for i, ch in enumerate(word):
            r = row + i if vertical else row
            c = col if vertical else col + i
            existing = self.cells.get((r, c))
            if existing is not None and existing != ch:
                return None
            if existing is None:
                # neighboring cells perpendicular to the word must be empty,
                # so we don't accidentally fuse into an unintended word
                if vertical:
                    if self.cells.get((r, c - 1)) or self.cells.get((r, c + 1)):
                        return None
                else:
                    if self.cells.get((r - 1, c)) or self.cells.get((r + 1, c)):
                        return None
            cells_to_fill.append((r, c))
        # cell immediately before/after the word must be empty
        if vertical:
            before, after = (row - 1, col), (row + len(word), col)
        else:
            before, after = (row, col - 1), (row, col + len(word))
        if self.cells.get(before) or self.cells.get(after):
            return None
        return cells_to_fill

    def place(self, word, row, col, vertical):
        for i, ch in enumerate(word):
            r = row + i if vertical else row
            c = col if vertical else col + i
            self.cells[(r, c)] = ch

    def try_place_anywhere(self, word):
        """Try to intersect `word` with any already-placed letter."""
        for (r, c), ch in list(self.cells.items()):
            for i, wch in enumerate(word):
                if wch != ch:
                    continue
                # try placing word vertically through (r, c)
                cand = self.can_place(word, r - i, c, vertical=True)
                if cand:
                    self.place(word, r - i, c, vertical=True)
                    return (r - i, c, "down")
                # try placing word horizontally through (r, c)
                cand = self.can_place(word, r, c - i, vertical=False)
                if cand:
                    self.place(word, r, c - i, vertical=False)
                    return (r, c - i, "across")
        return None

    def bounds(self):
        rows = [r for r, c in self.cells]
        cols = [c for r, c in self.cells]
        return min(rows), max(rows), min(cols), max(cols)


def build_grid(root, subwords, target_placed):
    grid = Grid()
    grid.place(root, 0, 0, vertical=False)
    placed = [{"word": root, "row": 0, "col": 0, "dir": "across"}]

    for word in subwords:
        if len(placed) >= target_placed:
            break
        result = grid.try_place_anywhere(word)
        if result:
            r, c, direction = result
            placed.append({"word": word, "row": r, "col": c, "dir": direction})

    if not grid.cells:
        return None

    min_r, max_r, min_c, max_c = grid.bounds()
    norm_placed = []
    for entry in placed:
        norm_placed.append({
            "word": entry["word"],
            "row": entry["row"] - min_r,
            "col": entry["col"] - min_c,
            "dir": entry["dir"],
        })
    width = max_c - min_c + 1
    height = max_r - min_r + 1
    return {"width": width, "height": height, "words": norm_placed}


def make_puzzle(puzzle_id, difficulty, root, all_words, rng):
    subwords = find_subwords(root, all_words)
    cfg = DIFFICULTIES[difficulty]
    grid = build_grid(root, subwords, cfg["target_placed"])
    if grid is None or len(grid["words"]) < cfg["min_placed"]:
        return None

    letters = list(root)
    rng.shuffle(letters)

    return {
        "id": puzzle_id,
        "difficulty": difficulty,
        "letters": letters,
        "grid": {"width": grid["width"], "height": grid["height"]},
        "words": grid["words"],
    }


def main():
    rng = random.Random(RNG_SEED)
    all_words = load_wordlist()

    for difficulty, cfg in DIFFICULTIES.items():
        out_dir = PUZZLES_DIR / difficulty
        out_dir.mkdir(parents=True, exist_ok=True)

        lo, hi = cfg["root_len"]
        candidates = [w for w in all_words if lo <= len(w) <= hi]
        rng.shuffle(candidates)

        made = []
        used_letter_sets = set()
        for root in candidates:
            if len(made) >= cfg["count"]:
                break
            key = frozenset(Counter(root).items())
            if key in used_letter_sets:
                continue
            puzzle_id = f"{difficulty}-{len(made) + 1:03d}"
            puzzle = make_puzzle(puzzle_id, difficulty, root, all_words, rng)
            if puzzle:
                made.append(puzzle)
                used_letter_sets.add(key)

        for puzzle in made:
            path = out_dir / f"{puzzle['id']}.json"
            path.write_text(json.dumps(puzzle, indent=2))

        manifest = [p["id"] for p in made]
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        print(f"{difficulty}: generated {len(made)}/{cfg['count']} puzzles")


if __name__ == "__main__":
    main()
