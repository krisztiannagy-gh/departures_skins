"""BKK FUTÁR (Budapest) skin for /departures.

Clones the amber LUMINO DFI stop displays used by BKK:

    7    Albertfalva vasútáll.   3'
    47   Deák Ferenc tér M       5'

Layout (same rules as the real 24/40/80 x 192 boards, scaled to any panel):
  * 7 px tall glyphs, 1 px top margin, 1 px between rows, last row touches
    the bottom edge -> 8 px row pitch, so 32 px = 4 rows, 64 px = 8 rows.
  * line number left, destination after it, minutes right-aligned with a
    trailing ' (e.g. 12').
  * under 1 minute / at the stop: minutes column empty, destination blinks
    (setting arrival_blink_ms, default 600 ms), until 15 s after departure.
  * departures more than bkk_max_minutes (default 60) away are not shown.
  * identical rows (same line, destination and minutes) are shown once.

Long destination names (setting bkk_long_names):
  abbr_cut     shorten words BKK-style (vasútállomás -> vasútáll. ...), then cut
  abbr_scroll  shorten, then scroll what still doesn't fit
  cut          cut at the last whole character that fits
  scroll       scroll the full name
Scrolling only ever happens inside the destination column, never over the
line number or the minutes.

Contract: on_enter(), render(), animate_tick(), message_active(),
refresh_settings(), on_exit()
"""
import time, json

try:
    import varinit
    from functions import cls, refresh, get_departure
    _HOST = True
except ImportError:          # desktop preview / tests
    _HOST = False

# --- constants ----------------------------------------------------------------
TOP = 1                 # empty pixel rows above the first departure
PITCH = 8               # 7 px text + 1 px gap
LINE_GAP = 4            # px between line-number column and destination
MIN_GAP = 3             # px kept clear between destination and minutes
SCROLL_STEP_S = 0.06    # one pixel every 60 ms
SCROLL_PAUSE_S = 2.0    # pause at the start (and 1 s at the end) of a scroll
LONG_NAME_MODES = ("abbr_cut", "abbr_scroll", "cut", "scroll")

# Word -> abbreviation, as seen on the BKK boards. Applied whole-word, from the
# last word backwards, only until the name fits. Extend via the app's
# "Abbreviate dest" setting (long=short pairs), which is tried first.
ABBREVIATIONS = (
    ("vasútállomás", "vasútáll."),
    ("pályaudvar", "pu."),
    ("utca", "u."),
    ("királyné", "k.né"),
    ("aluljáró", "alulj."),
    ("lakótelep", "ltp."),
    ("körút", "krt."),
)

# --- font -----------------------------------------------------------------------
_FONT = None

def load_font(path="skins/bkk/bkk_font.json"):
    """Glyph rows become int bitmasks (bit (w-1-col) = column col) for speed."""
    global _FONT
    with open(path) as f:
        raw = json.load(f)
    font = {}
    for c, g in raw.items():
        if not isinstance(g, list): continue
        w = g[0]
        font[c] = (w, tuple(int(r, 2) for r in g[1:]))
    _FONT = font
    return font

def _glyph(c):
    g = _FONT.get(c)
    return g if g is not None else _FONT["_"]

def text_width(text):
    if not text: return 0
    total = 0
    for c in text:
        total += _glyph(c)[0] + 1
    return total - 1

def draw_text(bmp, text, x, y, color=1, clip_l=0, clip_r=10000):
    """Draw text with its top-left at (x, y); pixels outside [clip_l, clip_r) are skipped."""
    for c in text:
        w, rows = _glyph(c)
        if x + w > clip_l and x < clip_r:
            for r in range(7):
                bits = rows[r]
                if not bits: continue
                for col in range(w):
                    if bits & (1 << (w - 1 - col)):
                        px = x + col
                        if clip_l <= px < clip_r:
                            try: bmp[px, y + r] = color
                            except Exception: pass
        x += w + 1
        if x >= clip_r: break
    return x

def clear_rect(bmp, x0, y0, w, h):
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            try: bmp[x, y] = 0
            except Exception: pass

# --- long names -------------------------------------------------------------
def _split_word(word):
    """'aluljáró,' -> ('aluljáró', ',')"""
    end = len(word)
    while end > 0 and word[end - 1] in ",.;:)":
        end -= 1
    return word[:end], word[end:]

def abbreviate(text, max_w, user_pairs=()):
    """Shorten the way BKK does, stopping as soon as the name fits."""
    if text_width(text) <= max_w: return text
    for pair in user_pairs:                       # user's own long=short pairs first
        if isinstance(pair, (list, tuple)) and len(pair) == 2 and pair[0] and pair[0] in text:
            text = text.replace(pair[0], pair[1])
            if text_width(text) <= max_w: return text
    if " / " in text:                             # boards write "Rákospatak u/Csömöri út"
        text = text.replace(" / ", "/")
        if text_width(text) <= max_w: return text
    words = text.split(" ")
    for i in range(len(words) - 1, -1, -1):       # last word first
        core, tail = _split_word(words[i])
        for long, short in ABBREVIATIONS:
            if core == long or core == long[0].upper() + long[1:]:
                short = short if core == long else short[0].upper() + short[1:]
                if short.endswith(".") and tail.startswith("."): tail = tail[1:]
                words[i] = short + tail
                text = " ".join(words)
                if text_width(text) <= max_w: return text
                break
    # "utca"-style words inside slash-joined parts ("Rákospatak utca/Csömöri út")
    for long, short in ABBREVIATIONS:
        if long + "/" in text:
            text = text.replace(long + "/", short.rstrip(".") + "/")
            if text_width(text) <= max_w: return text
    return text

def hard_cut(text, max_w):
    while text and text_width(text) > max_w:
        text = text[:-1]
    return text.rstrip(" /,-")

def _is_marker(word):
    """Transfer markers BKK puts at the end of names: M, H, M+H, M+H+V ..."""
    return 0 < len(word) <= 5 and all(c in "MHV+" for c in word)

def cut_destination(text, max_w):
    """Hard cut that keeps a trailing transfer marker: 'Kelenföld vasútáll. M'
    -> 'Kelenföld vasút M' rather than losing the M."""
    words = text.split(" ")
    if len(words) > 1 and _is_marker(words[-1]):
        tail = " " + words[-1]
        head = hard_cut(" ".join(words[:-1]), max_w - text_width(tail))
        if head: return head + tail
    return hard_cut(text, max_w)

def fit_destination(text, max_w, mode, user_pairs=()):
    """Returns (text, needs_scroll)."""
    if mode not in LONG_NAME_MODES: mode = "abbr_cut"
    if text_width(text) <= max_w: return text, False
    if mode.startswith("abbr"):
        text = abbreviate(text, max_w, user_pairs)
        if text_width(text) <= max_w: return text, False
    if mode.endswith("scroll"):
        return text, True
    return cut_destination(text, max_w), False

# --- layout -------------------------------------------------------------------
def build_rows(departures, width, height, settings):
    """departures: host rows [flag, line, dest, mins, dir, color, delay, arriving].
    Returns a list of drawable row dicts (pure, no drawing)."""
    max_rows = max(1, height // PITCH)
    max_min = int(settings.get("bkk_max_minutes", 60))
    mode = settings.get("bkk_long_names", "abbr_cut")
    pairs = settings.get("dest_abbrev", []) or []
    if not isinstance(pairs, list): pairs = []

    seen, rows = set(), []
    for d in departures:
        if not isinstance(d, list) or len(d) < 4: continue
        line, dest, mins = str(d[1]).strip(), str(d[2]).split("(")[0].strip(), str(d[3]).strip()
        arriving = len(d) > 7 and bool(d[7])
        if not arriving and mins.isdigit() and int(mins) > max_min: continue
        key = (line, dest, "now" if arriving else mins)
        if key in seen: continue                  # duplicate departures from the feed
        seen.add(key)
        rows.append({"line": line, "dest": dest, "mins": mins, "arriving": arriving})
        if len(rows) >= max_rows: break

    line_w = max([text_width("88")] + [text_width(r["line"]) for r in rows])
    line_w = min(line_w, text_width("888E"))
    dest_x = line_w + LINE_GAP
    mins_w = text_width("60'")
    dest_r = width - mins_w - MIN_GAP
    max_dest_w = max(0, dest_r - dest_x)

    for i, r in enumerate(rows):
        r["y"] = TOP + i * PITCH
        r["line"] = hard_cut(r["line"], line_w)
        r["dest_x"], r["dest_w"] = dest_x, max_dest_w
        r["dest"], r["scroll"] = fit_destination(r["dest"], max_dest_w, mode, pairs)
        r["text_w"] = text_width(r["dest"])
        r["tail"] = "" if r["arriving"] else (r["mins"] + "'" if r["mins"].isdigit() else r["mins"])
        r["tail_x"] = width - text_width(r["tail"])
        r["offset"], r["next_step"], r["visible"] = 0, 0, True
    return rows

def draw_row(bmp, r, color=1):
    draw_text(bmp, r["line"], 0, r["y"], color)
    draw_dest(bmp, r, color)
    draw_text(bmp, r["tail"], r["tail_x"], r["y"], color)

def draw_dest(bmp, r, color=1):
    clear_rect(bmp, r["dest_x"], r["y"], r["dest_w"], 7)
    if r["visible"]:
        draw_text(bmp, r["dest"], r["dest_x"] - r["offset"], r["y"], color,
                  clip_l=r["dest_x"], clip_r=r["dest_x"] + r["dest_w"])

def tick_rows(bmp, rows, now, blink_s, color=1):
    """Advance blink + scroll state; redraws changed rows. Returns True if anything changed."""
    changed = False
    phase_on = int(now / blink_s) % 2 == 0
    for r in rows:
        dirty = False
        if r["arriving"] and r["visible"] != phase_on:
            r["visible"] = phase_on
            dirty = True
        if r["scroll"] and now >= r["next_step"]:
            overflow = r["text_w"] - r["dest_w"]
            if r["next_step"] == 0:                       # first tick: hold at the start
                r["next_step"] = now + SCROLL_PAUSE_S
            elif r["offset"] >= overflow:                 # reached the end: jump back
                r["offset"] = 0
                r["next_step"] = now + SCROLL_PAUSE_S
                dirty = True
            else:
                r["offset"] += 1
                r["next_step"] = now + (1.0 if r["offset"] >= overflow else SCROLL_STEP_S)
                dirty = True
        if dirty:
            draw_dest(bmp, r, color)
            changed = True
    return changed

# --- host glue ----------------------------------------------------------------
_rows = []

def _settings():
    return varinit.settings

def _hide_list_layers():
    varinit.tg1.y, varinit.tg2.y = varinit.if_tall, varinit.if_tall
    varinit.tg3.x, varinit.tg3.y = 0, 0
    try:
        for _t in varinit.dest_tgs: _t.hidden = True
        varinit.overlay_tg.hidden = True
    except Exception: pass

def render():
    global _rows
    if _FONT is None: load_font()
    _hide_list_layers()
    bmp = varinit.topbottom
    cls(bmp)
    # ask the host for a few more rows than fit (duplicates get dropped), then
    # put the user's own setting back so nothing else is affected
    _md = varinit.settings.get("maxdest", 5)
    varinit.settings["maxdest"] = max(int(_md), varinit.if_tall // PITCH + 3)
    try: data = get_departure(num="1")
    finally: varinit.settings["maxdest"] = _md
    if data and isinstance(data[0], list) and data[0][0] == "1":
        # error / info message from the host pipeline: show it on the first row
        _rows = []
        draw_text(bmp, hard_cut(str(data[0][1]), varinit.if_long), 0, TOP)
    else:
        _rows = build_rows(data or [], varinit.if_long, varinit.if_tall, _settings())
        for r in _rows: draw_row(bmp, r)
    refresh()
    return time.monotonic()

def animate_tick():
    if _rows:
        blink = max(100, int(_settings().get("arrival_blink_ms", 600))) / 1000
        if tick_rows(varinit.topbottom, _rows, time.monotonic(), blink):
            refresh()
    return False      # never hold back the regular 20 s refresh

def message_active():
    return False

def refresh_settings():
    render()

def on_enter():
    varinit.want_arrivals = True       # host keeps departures under 1 min for us
    load_font()
    return render()

def on_exit():
    global _rows
    varinit.want_arrivals = False
    _rows = []
    cls(varinit.topbottom)
