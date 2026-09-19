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
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
WORDLIST_RAW = HERE / "wordlist_raw.txt"
WORDLIST_RAW_URL = (
    "https://raw.githubusercontent.com/first20hours/google-10000-english/"
    "master/google-10000-english-no-swears.txt"
)
SYSTEM_DICT = Path("/usr/share/dict/web2")
PROPER_NAMES = Path("/usr/share/dict/propernames")
PUZZLES_DIR = HERE.parent / "puzzles"

MIN_SUBWORD_LEN = 3
MAX_SUBWORD_LEN = 8  # matches the longest root word length
# Only take the N most frequent words from the raw list. This list is
# a small, pre-curated "no-swears" common-words list (not a raw web
# corpus), so a low cutoff is deliberate: going much higher starts
# admitting real but obscure/technical/archaic terms that a much
# bigger corpus would otherwise catch on frequency alone but that
# this list is too short to rank sensibly.
FREQUENCY_RANK_CUTOFF = 4000

DIFFICULTIES = {
    "easy": {
        "root_len": (5, 6),
        "min_placed": 5,
        "grid_target": 9,
        "count": 15,
    },
    "medium": {
        "root_len": (7, 8),
        "min_placed": 7,
        "grid_target": 12,
        "count": 15,
    },
}

RNG_SEED = 42

# The frequency list is scraped from real web text, so it conflates
# genuinely common words with lowercased proper nouns, and Webster's
# unabridged (web2) admits plenty of archaic/dialectal/obscure entries
# that happen to share a spelling with something common (e.g. "tate",
# a real but obscure archaic word, vs. "Tate" the surname/gallery).
# Neither filter alone can tell those apart, so anything caught by
# manual review goes here: abbreviations, foreign/dialectal terms,
# fragments that aren't used standalone, proper-noun collisions, and
# anything too clinical/heavy-themed or crude for a casual word game.
BLOCKLIST = {
    "ana", "ani", "ara", "ait", "ast", "bam", "ber", "bis", "carr",
    "cest", "che", "cho", "cit", "clit", "coco", "cor", "cos", "deg",
    "desi", "dev", "dit", "dob", "dod", "ean", "fra", "ged", "git",
    "het", "holt", "homo", "ide", "ing", "ist", "iso", "kat", "kip",
    "lim", "lis", "luxe", "lys", "mao", "mel", "mor", "mot", "nea",
    "neo", "non", "obi", "och", "oki", "ora", "poe", "poy", "psi",
    "ras", "rea", "reb", "rel", "rex", "ria", "rio", "roc", "roi",
    "sao", "sar", "seg", "ser", "seth", "shi", "sho", "sie", "sith",
    "soc", "soho", "tai", "tate", "tera", "til", "ting", "tho",
    "morocco", "incubus", "anorexia", "dyslexia", "weber", "bodied",
    "reflux", "cortical", "dont", "las", "tue",
    # Genuinely offensive/violent terms rather than merely obscure or
    # informal - excluded even from bonus words, which mild "risque"
    # words are otherwise fine for.
    "rape", "raper", "raped", "rapes", "raping", "slut", "sluts",
    "nazim",
}

# The curated 4000-word list is clean but short, so it misses some very
# ordinary short words a player would reasonably expect to work (e.g.
# "gut"). These are added back in before filtering, so they still pass
# through the same real-word/proper-name checks as everything else.
ALLOWLIST_EXTRA = {
    "gut", "hub", "hug", "hut", "jug", "mug", "rug", "tub", "tug",
    "keg", "peg", "pod", "pop", "pot", "tap", "tan", "tax", "tin",
    "tip", "tow", "nap", "nod", "oak", "owl", "pad", "pig", "pin",
    "rib", "rim", "rod", "rot", "row", "rub", "sip", "sob", "tab",
    "van", "vat", "wag", "wax", "wig", "win", "wit", "zip", "jab",
    "jam", "jog", "lag", "lid", "mop",
}


def _ensure_downloaded(path, url):
    if path.exists():
        return
    print(f"downloading {path.name} ...")
    urllib.request.urlretrieve(url, path)


def _filter_real_words(words):
    """Drop non-words and proper nouns from a raw candidate word set.

    Real-word check: exact case-sensitive lowercase match against the
    system dictionary (proper nouns only appear capitalized there).
    Proper-noun check: web2 sometimes also carries an obscure lowercase
    common-noun sense for what's overwhelmingly a place/given name
    (e.g. "tivoli", "chester"), which the case check alone can't catch.
    """
    if SYSTEM_DICT.exists():
        dict_words = set(SYSTEM_DICT.read_text(errors="ignore").splitlines())
        words = {w for w in words if w in dict_words}
    else:
        print(f"warning: {SYSTEM_DICT} not found, skipping real-word filter")

    if PROPER_NAMES.exists():
        proper = {
            line.strip().lower()
            for line in PROPER_NAMES.read_text(errors="ignore").splitlines()
        }
        words -= proper

    return words - BLOCKLIST


def _load_frequency_list(path, cutoff):
    words = set()
    lines = path.read_text().splitlines()[:cutoff]
    for line in lines:
        w = line.split("\t")[0].strip().lower()
        if w.isalpha() and len(w) >= MIN_SUBWORD_LEN:
            words.add(w)
    return words


def load_wordlist():
    """The clean, curated word set used for root words and visible grid
    words. Small and conservative on purpose - anything placed in the
    grid is always on screen, so it needs to be unambiguously common.
    """
    words = _load_frequency_list(WORDLIST_RAW, FREQUENCY_RANK_CUTOFF)
    words |= ALLOWLIST_EXTRA
    return _filter_real_words(words)


def load_bonus_wordlist(grid_words):
    """The full system dictionary, used only to recognize "bonus" words -
    valid words a player can type that aren't drawn into the grid. Since
    these never render on screen, there's no reason to cap them by
    frequency at all (a cutoff just means real words like "terse" get
    silently rejected for no visible reason) - any dictionary word
    should work. Proper-noun and blocklist filtering still applies.
    """
    if not SYSTEM_DICT.exists():
        print(f"warning: {SYSTEM_DICT} not found, bonus words limited to grid words")
        return set(grid_words)

    words = set()
    for line in SYSTEM_DICT.read_text(errors="ignore").splitlines():
        w = line.strip().lower()
        if w.isalpha() and MIN_SUBWORD_LEN <= len(w) <= MAX_SUBWORD_LEN:
            words.add(w)

    words |= grid_words
    return _filter_real_words(words)


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
    matches.sort(key=lambda w: (-len(w), w))
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


def build_grid(root, subwords, grid_target):
    grid = Grid()
    grid.place(root, 0, 0, vertical=False)
    placed = [{"word": root, "row": 0, "col": 0, "dir": "across"}]

    # Keep the visible grid to a modest, curated size. Every other
    # valid subword we found still gets recognized when typed - it's
    # just added as a "bonus" word instead of drawn into the grid (see
    # make_puzzle below), so nothing a player types is ever a dead end.
    for word in subwords:
        if len(placed) >= grid_target:
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


def make_puzzle(puzzle_id, difficulty, root, all_words, bonus_words_pool, rng):
    subwords = find_subwords(root, all_words)
    cfg = DIFFICULTIES[difficulty]
    grid = build_grid(root, subwords, cfg["grid_target"])
    if grid is None or len(grid["words"]) < cfg["min_placed"]:
        return None

    placed_words = {entry["word"] for entry in grid["words"]}
    all_bonus_candidates = find_subwords(root, bonus_words_pool)
    bonus_words = sorted(w for w in all_bonus_candidates if w not in placed_words)

    letters = list(root)
    rng.shuffle(letters)

    return {
        "id": puzzle_id,
        "difficulty": difficulty,
        "letters": letters,
        "grid": {"width": grid["width"], "height": grid["height"]},
        "words": grid["words"],
        "bonus_words": bonus_words,
    }


def main():
    _ensure_downloaded(WORDLIST_RAW, WORDLIST_RAW_URL)

    rng = random.Random(RNG_SEED)
    all_words = load_wordlist()
    bonus_words_pool = load_bonus_wordlist(all_words)
    print(f"grid word pool: {len(all_words)}, bonus word pool: {len(bonus_words_pool)}")

    for difficulty, cfg in DIFFICULTIES.items():
        out_dir = PUZZLES_DIR / difficulty
        out_dir.mkdir(parents=True, exist_ok=True)

        lo, hi = cfg["root_len"]
        candidates = sorted(w for w in all_words if lo <= len(w) <= hi)
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
            puzzle = make_puzzle(
                puzzle_id, difficulty, root, all_words, bonus_words_pool, rng
            )
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
