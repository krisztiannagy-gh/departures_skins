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

Long destination names (settings bkk_shorten + the app's dest_scroll):
  abbr_cut     shorten words BKK-style (vasútállomás -> vasútáll. ...), then cut
  abbr_scroll  shorten, then scroll what still doesn't fit
  cut          cut at the last whole character that fits
  scroll       scroll the full name
Scrolling only ever happens inside the destination column, never over the
line number or the minutes.

Static mode (setting bkk_static): instead of departures show the BKK logo
or the text "BKK FUTÁR" top left (setting bkk_static_style "logo" / "text";
no data is fetched).

Start-up: the BKK logo, centred, for SPLASH_S seconds. Loading/connecting:
the logo with a 1 px bar on the bottom row that fills from left to right and
then empties from left to right. It stays up while the first requests fail,
for up to STALE_MAX_S after start-up, then "Nincs kapcsolat" takes over. (The bar
stands still while a request is running: the box can't animate during one.)
Panels too small for the logo (94 x 19) show
the text "BKK FUTÁR" top left instead, and the usual "Adatok betöltése" screen.

Passenger announcements (needs Departures 0.992, its pa.py engine): a
full-screen PA replaces the board (fixed rows drawn here, scrolling rows as
moving TileGrids); a Scrolling PA or Reminder takes the bottom row, the
departures and status screens use the rows above. While a bottom-row PA
scrolls, departure requests wait for a separator (data at most ~1-2 min old,
spare rows counted down meanwhile); a full-screen PA makes none, except for
the clock when a PA has a start or end time.

Contract: on_enter(), render(), animate_tick(), message_active(),
refresh_settings(), on_exit()
"""
import time, json, gc

try:
    import varinit, displayio
    from functions import cls, refresh, get_departure
    _HOST = True
except ImportError:          # desktop preview / tests
    _HOST = False
try:
    import pa as PA          # passenger announcements engine (Departures 0.992+)
except ImportError:
    PA = None

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
    """Glyph rows are int bitmasks (bit (w-1-col) = column col); older font
    files stored them as "0101" strings, which are still accepted."""
    global _FONT
    with open(path) as f:
        raw = json.load(f)
    font = {}
    for c, g in raw.items():
        if not isinstance(g, list): continue
        w = g[0]
        font[c] = (w, tuple(r if isinstance(r, int) else int(r, 2) for r in g[1:]))
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
    # bkk_shorten (this skin) + dest_scroll (the app's "Scroll long destination
    # names") together pick one of LONG_NAME_MODES
    mode = ("abbr_" if int(settings.get("bkk_shorten", 1)) else "") + \
           ("scroll" if int(settings.get("dest_scroll", 0)) else "cut")
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

# --- static content -------------------------------------------------------------
TITLE = "BKK FUTÁR"
SPLASH_S = 3            # start-up logo stays this long before the first departures
BAR_S = 1.2             # loading bar: seconds to fill, then the same to empty
_LOGO = None            # (w, h, row bitmasks) from bkk_logo.json

def load_logo(path="skins/bkk/bkk_logo.json"):
    global _LOGO
    try:
        with open(path) as f: d = json.load(f)
        _LOGO = (d["w"], d["h"], tuple(r if isinstance(r, int) else int(r, 2) for r in d["rows"]))
    except Exception as e:
        print("BKK skin: no logo", e); _LOGO = None

def logo_fits(width, height):
    return _LOGO is not None and width >= _LOGO[0] and height >= _LOGO[1] + 2

def draw_logo(bmp, width, height, color=1, max_y=None):
    """Logo centred on the board. Returns False if it doesn't fit.
    max_y: the logo must end above this row (bottom-row PA); it stays at its
    usual place if it already does, otherwise it's centred above it."""
    if not logo_fits(width, height): return False
    w, h, rows = _LOGO
    x0, y0 = (width - w) // 2, (height - h) // 2
    if max_y is not None and y0 + h > max_y:
        y0 = max(0, (max_y - h) // 2)
    for r in range(h):
        bits = rows[r]
        if not bits: continue
        for c in range(w):
            if bits & (1 << (w - 1 - c)):
                try: bmp[x0 + c, y0 + r] = color
                except Exception: pass
    return True

def bar_span(now, width):
    """Lit part [a, b) of the loading bar: fills left to right, then empties
    left to right, eased at both ends."""
    t = (now % (2 * BAR_S)) / BAR_S
    e = lambda v: v * v * (3 - 2 * v)
    if t < 1: return 0, int(e(t) * width + 0.5)
    return int(e(t - 1) * width + 0.5), width

def draw_static(bmp, width, height, settings, color=1, max_y=None):
    if settings.get("bkk_static_style", "text") == "logo" and draw_logo(bmp, width, height, color, max_y):
        return
    draw_text(bmp, TITLE, 0, TOP, color)

# --- status screens -------------------------------------------------------------
# Shown instead of an empty board, so it's always clear the box is alive:
#   loading  - after start-up until the first data arrives
#   offline  - no fresh data for STALE_MAX_S (or none at all since start-up)
#   empty    - the server answered, but nothing leaves within bkk_max_minutes
#   info     - setup prompts from the app (pick operator / station ...)
# Short outages are bridged: the last departures stay up to STALE_MAX_S with
# their minutes counted down on the box.
STALE_MAX_S = 120
BACKOFF_S = (20, 30, 60)        # next request after 0 / 1 / 2+ failures in a row
FAIL_MARKERS = ("-", "*", "**", "***")
TXT_LOADING = "Adatok betöltése"
TXT_OFFLINE = "Nincs kapcsolat"
TXT_EMPTY = "Ebből a megállóból {} percen belül nem indul járat."
TXT_EMPTY_SHORT = "Nincs induló járat"
ICON = 7                        # icons are 7 x 7, same height as the letters
ICON_GAP = 2

# 16 points of a 7x7 circle, clockwise from the top
RING = ((2, 0), (3, 0), (4, 0), (5, 1), (6, 2), (6, 3), (6, 4), (5, 5),
        (4, 6), (3, 6), (2, 6), (1, 5), (0, 4), (0, 3), (0, 2), (1, 1))
DIRS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
ICON_PERIOD = {"loading": 0.12, "offline": 0.8, "empty": 1.0}

def icon_pixels(kind, frame):
    if kind == "loading":           # circle with a gap travelling round it
        gap = [(frame * 2 + i) % 16 for i in range(3)]
        return [p for i, p in enumerate(RING) if i not in gap]
    if kind == "offline":           # circled x, pulsing
        if frame % 2: return [(2, 2), (4, 2), (3, 3), (2, 4), (4, 4)]
        return list(RING) + [(2, 2), (4, 2), (3, 3), (2, 4), (4, 4)]
    if kind == "empty":             # clock whose hand ticks round
        dx, dy = DIRS[frame % 8]
        return list(RING) + [(3, 3), (3 + dx, 3 + dy), (3 + 2 * dx, 3 + 2 * dy)]
    return []

def wrap_text(text, width):
    lines, cur = [], ""
    for w in text.split(" "):
        t = w if not cur else cur + " " + w
        if text_width(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return [hard_cut(l, width) if text_width(l) > width else l for l in lines]

def build_status(kind, width, height, settings, text=None):
    """Layout of a status screen: header, wrapped text, icon position."""
    rows_n = max(1, height // PITCH)
    if text is None:
        text = {"loading": TXT_LOADING, "offline": TXT_OFFLINE,
                "empty": TXT_EMPTY.format(int(settings.get("bkk_max_minutes", 60)))}[kind]
    has_icon = kind in ICON_PERIOD
    avail = rows_n - 1 if rows_n > 1 else 1          # rows under the header

    def layout(t):
        lines = wrap_text(t, width)
        inline = has_icon and text_width(lines[-1]) + ICON_GAP + ICON <= width
        return lines, inline, len(lines) + (1 if has_icon and not inline else 0)

    lines, inline, need = layout(text)
    if need > avail and kind == "empty":
        lines, inline, need = layout(TXT_EMPTY_SHORT)
    first = 2 if need == 1 and rows_n >= 3 else 1
    if rows_n == 1: first = 0
    placed = [(l, 0, TOP + (first + i) * PITCH) for i, l in enumerate(lines[:max(1, avail)])]
    icon = None
    if has_icon:
        if inline:
            last, x, y = placed[-1]
            icon = (x + text_width(last) + ICON_GAP, y)
        else:
            icon = (0, TOP + (first + len(placed)) * PITCH)
    return {"kind": kind, "header": rows_n > 1, "lines": placed, "icon": icon, "frame": -1}

def draw_status(bmp, st, color=1):
    if st["kind"] == "logo":
        draw_logo(bmp, st["w"], st["h"], color, st.get("max_y"))
        st["frame"] = -1
        return
    if st["header"]: draw_text(bmp, TITLE, 0, TOP, color)
    for text, x, y in st["lines"]: draw_text(bmp, text, x, y, color)
    st["frame"] = -1

def tick_status(bmp, st, now, color=1):
    """Redraw the icon when its frame changes. Returns True if it changed."""
    if st and st["kind"] == "logo":                  # loading bar on the bottom row
        if st.get("max_y") is not None: return False  # ...unless a PA scrolls there
        span = bar_span(now, st["w"])
        if span == st["frame"]: return False
        st["frame"] = span
        a, b = span
        y = st["h"] - 1
        for x in range(st["w"]):
            try: bmp[x, y] = color if a <= x < b else 0
            except Exception: pass
        return True
    if not st or not st["icon"] or st["kind"] not in ICON_PERIOD: return False
    frame = int(now / ICON_PERIOD[st["kind"]])
    if frame == st["frame"]: return False
    st["frame"] = frame
    x0, y0 = st["icon"]
    clear_rect(bmp, x0, y0, ICON, ICON)
    for px, py in icon_pixels(st["kind"], frame):
        try: bmp[x0 + px, y0 + py] = color
        except Exception: pass
    return True

def classify(data, fail_texts=(), prompt_texts=()):
    """Host get_departure() result -> ("ok", rows) | ("fail", None) | ("info", text)."""
    if not data: return "ok", []
    first = data[0]
    if isinstance(first, list) and first and first[0] == "1":
        msg = str(first[1]).strip() if len(first) > 1 else ""
        if msg in FAIL_MARKERS or msg.startswith("^") or msg in fail_texts:
            return "fail", None
        if msg in prompt_texts:
            return "info", msg
        print("BKK skin: server message treated as 'no departures':", msg)
        return "ok", []
    return "ok", data

def age_rows(rows, age_s):
    """Last good departures, minutes counted down by age_s; gone ones dropped."""
    out, gone = [], int(age_s // 60)
    for d in rows:
        d = list(d)
        while len(d) < 8: d.append("")
        mins = str(d[3]).strip()
        if d[7]:                                  # was already departing
            if age_s <= 60: out.append(d)
            continue
        if not mins.isdigit():
            out.append(d); continue
        left = int(mins) - gone
        if left < 0: continue
        if left == 0: d[3], d[7] = "0", 1
        else: d[3] = str(left)
        out.append(d)
    return out

# --- host glue ----------------------------------------------------------------
_rows = []
_status = None
_view = {"kind": None, "status": None, "text": None}    # what the departures area shows
_net = {"good": None, "good_t": 0.0, "fails": 0, "bridging": False, "bridge_min": -1,
        "check_t": 0.0, "start_t": 0.0, "force": False}
_splash = {"done": False}

def _settings():
    return varinit.settings

def _hide_list_layers():
    varinit.tg1.y, varinit.tg2.y = varinit.if_tall, varinit.if_tall
    varinit.tg3.x, varinit.tg3.y = 0, 0
    try:
        for _t in varinit.dest_tgs: _t.hidden = True
        varinit.overlay_tg.hidden = True
    except Exception: pass

def _host_texts():
    try:
        import dicts
        L = dicts.language[_settings()["language"]]
        return ((L["settings"]["no_data"],),
                (L["settings"]["select_operator"], L["settings"]["search"], L["display"]["select_station"]))
    except Exception:
        return (), ()

# --- passenger announcements ----------------------------------------------------
# The engine (the app's pa.py) decides what is shown when; this skin draws it.
# Fixed full-screen rows go into the board bitmap. Every scrolling text (full-
# screen scrolling rows, the bottom-row Scrolling PA / Reminder) is rendered once
# into its own 1-bit bitmap in a TileGrid with a transparent background that only
# moves, which is cheap enough for smooth scrolling on the box.
PA_FETCH_AGE_S = 60     # bottom-row PA: request at the next separator once data is this old
PA_FETCH_MAX_S = 120    # ...and in any case once it's this old
_pa = None              # pa.Engine while the skin runs on a big enough panel
_pa_layer = {"group": None, "pal": None, "tgs": {}, "ver": -1}
# Smoothness. The box does one thing at a time: a request, a settings-page
# answer or a garbage collection (memory clean-up, 50-150 ms on 2 MB) stops
# the animation. So: collect garbage on purpose while a separator passes;
# after a long stall the text carries on where it stopped (a pause, no jump);
# after a short one it catches up at most MAX_STEP px per frame.
PAUSE_MS = 120          # a frame gap longer than this counts as a stall
FRAME_MS = 30           # normal frame time, kept when a stall is turned into a pause
MAX_STEP = 2            # px a scrolling text may move in one frame when behind
GC_EVERY_MS = 4000      # at most one planned garbage collection this often
_tick = {"last": 0, "sep": False, "gc_t": 0}
PERF = {}               # stall statistics for the app's /pa/perf page

def perf_reset():
    PERF.clear()
    PERF.update({"frames": 0, "gap_60": 0, "gap_150": 0, "gap_500": 0, "max_gap_ms": 0,
                 "gc": 0, "gc_ms": 0, "gc_max_ms": 0, "req": 0, "req_ms": 0, "req_max_ms": 0,
                 "since_ms": PA.ms() if PA is not None else 0})
perf_reset()
_layout = {"now": "plain"}      # plain | bottom | fs

def _rows_n():
    return max(1, varinit.if_tall // PITCH)

def _bottom_y():
    return TOP + (_rows_n() - 1) * PITCH

def _avail_h():
    """Height the departures / status screens may use."""
    return _bottom_y() if _layout["now"] == "bottom" else varinit.if_tall

def _pa_start():
    global _pa
    _pa = None
    if PA is None or not _HOST: return
    if varinit.if_long < PA.MIN_PANEL_W or _rows_n() < 2: return
    _pa = PA.start(text_width, varinit.if_long, _rows_n())
    pal = displayio.Palette(2)
    pal[0] = 0
    pal.make_transparent(0)
    pal[1] = varinit.palette[1]
    grp = displayio.Group()
    varinit.group.append(grp)
    _pa_layer.update({"group": grp, "pal": pal, "tgs": {}, "ver": -1})
    _tick["last"] = 0
    perf_reset()

def _pa_stop():
    global _pa
    grp = _pa_layer["group"]
    if grp is not None:
        try: varinit.group.remove(grp)
        except Exception: pass
    _pa_layer.update({"group": None, "pal": None, "tgs": {}, "ver": -1})
    if PA is not None: PA.stop()
    _pa = None
    _layout["now"] = "plain"

def _pa_layout():
    if _pa is None: return "plain"
    if _pa.fullscreen(): return "fs"
    return "bottom" if _pa.bottom() is not None else "plain"

def _pa_want():
    """key -> (Strip, y) for everything that scrolls right now."""
    want = {}
    if _pa is None: return want
    if _pa.fullscreen():
        for i, r in enumerate(_pa.fs["rows"]):
            if isinstance(r, PA.Strip): want["fs%d" % i] = (r, TOP + i * PITCH)
    else:
        b = _pa.bottom()
        if b is not None: want["bot"] = (b, _bottom_y())
    return want

def _pa_sync(now_ms):
    """Create, remove and move the scrolling TileGrids. True if anything changed."""
    lay = _pa_layer
    grp, tgs = lay["group"], lay["tgs"]
    if grp is None: return False
    try:
        if lay["pal"][1] != varinit.palette[1]: lay["pal"][1] = varinit.palette[1]   # brightness / tone
    except Exception: pass
    changed = False
    if lay["ver"] != _pa.version:            # only rebuild when the engine's layout changed
        lay["ver"] = _pa.version
        want = _pa_want()
        for k in list(tgs.keys()):
            if k not in want or tgs[k]["strip"] is not want[k][0]:
                try: grp.remove(tgs[k]["tg"])
                except Exception: pass
                del tgs[k]
                changed = True
        for k, (st, y) in want.items():
            if k in tgs: continue
            bmp = displayio.Bitmap(st.w, 7, 2)
            for x, t in st.items:
                draw_text(bmp, t, x, 0, 1, clip_r=st.w + 8)
            tg = displayio.TileGrid(bmp, pixel_shader=lay["pal"], x=st.panel_w, y=y)
            grp.append(tg)
            tgs[k] = {"tg": tg, "bmp": bmp, "strip": st, "cut": st.w, "clr": st.w}
            changed = True
    for d in tgs.values():
        st, tg, bmp = d["strip"], d["tg"], d["bmp"]
        x = st.x(now_ms)
        if st.limit < st.w:
            # cut short (reminder switched off / Scrolling PA waiting): blank
            # what comes after the cut just before it would enter the panel
            if d["cut"] != st.limit: d["cut"], d["clr"] = st.limit, st.limit
            stop = min(st.w, st.panel_w - x + 2)
            for col in range(d["clr"], stop):
                for yy in range(7): bmp[col, yy] = 0
            if stop > d["clr"]: d["clr"] = stop
        if x < tg.x - MAX_STEP and tg.x <= st.panel_w:
            x = tg.x - MAX_STEP              # behind after a short stall: catch up gently
        if tg.x != x:
            tg.x = x
            changed = True
    return changed

def _redraw():
    """Redraw the board bitmap after the PA layout changed (full screen on/off,
    bottom row taken/given back)."""
    global _rows, _status
    bmp = varinit.topbottom
    w, h = varinit.if_long, varinit.if_tall
    cls(bmp)
    if _layout["now"] == "fs":
        _rows, _status = [], None
        for i, r in enumerate(_pa.fs["rows"]):
            if isinstance(r, str): draw_text(bmp, r, 0, TOP + i * PITCH)
        return
    by = _bottom_y() if _layout["now"] == "bottom" else None
    if int(_settings().get("bkk_static", 0)):
        _rows, _status = [], None
        draw_static(bmp, w, h, _settings(), max_y=by)
        return
    kind = _view["kind"]
    if kind == "rows" and _net["good"] is not None:
        age = time.monotonic() - _net["good_t"]
        if age <= STALE_MAX_S:
            _show_rows(bmp, age_rows(_net["good"], age))
            _net["bridge_min"] = int(age // 60)
            return
        _show_status(bmp, "loading")
        return
    if kind == "status":
        _show_status(bmp, _view["status"], _view["text"])
        return
    _show_status(bmp, "loading")

def _fetch():
    """One departures request. The board can't animate during it, so the
    scrolling PAs are told to resume where they stopped."""
    t = PA.ms() if PA is not None else 0
    data = get_departure(num="1")
    if PA is not None:
        d = PA.ms() - t
        if _pa is not None: _pa.shift(d)
        _tick["last"] = PA.ms()              # the freeze is handled, not a stall
        PERF["req"] += 1; PERF["req_ms"] += d
        if d > PERF["req_max_ms"]: PERF["req_max_ms"] = d
    return data

def _store_good(data):
    kind, payload = classify(data, *_host_texts())
    if kind == "ok":
        _net["good"], _net["good_t"], _net["fails"] = payload, time.monotonic(), 0
        _net["bridge_min"] = 0
    return kind, payload

def _hold():
    """True keeps the host from calling render() (= no request) right now."""
    if _pa is None: return False
    if _net["force"]: return False
    if _pa.fullscreen():
        return not PA.clock_due()            # no departures visible: no requests
    if _pa.bottom() is None or int(_settings().get("bkk_static", 0)): return False
    if _net["good"] is None or _net["bridging"]:
        return False                         # connecting / retrying works as usual
    if _status is not None and _status["kind"] not in ("empty", "info"):
        return False                         # loading / offline screens retry as usual
    age = time.monotonic() - _net["good_t"]
    if age >= PA_FETCH_MAX_S: return False
    if age >= PA_FETCH_AGE_S and _pa.bottom().sep_visible(PA.ms()): return False
    return True

def _show_status(bmp, kind, text=None):
    global _status, _rows
    _rows = []
    _view.update({"kind": "status", "status": kind, "text": text})
    w, h = varinit.if_long, _avail_h()
    by = _bottom_y() if _layout["now"] == "bottom" else None
    if kind == "loading" and logo_fits(w, varinit.if_tall):
        _status = {"kind": "logo", "w": w, "h": varinit.if_tall, "frame": -1, "max_y": by}
    else:
        _status = build_status(kind, w, h, _settings(), text)
    draw_status(bmp, _status)
    tick_status(bmp, _status, time.monotonic())

def _show_rows(bmp, departures):
    global _status, _rows
    _status = None
    _view.update({"kind": "rows", "status": None, "text": None})
    _rows = build_rows(departures, varinit.if_long, _avail_h(), _settings())
    if not _rows:
        _show_status(bmp, "empty")
        return
    for r in _rows: draw_row(bmp, r)

def render():
    global _rows, _status
    if _FONT is None: load_font()
    if _LOGO is None: load_logo()
    _hide_list_layers()
    _splash["done"] = True
    _net["force"] = False
    bmp = varinit.topbottom
    now = time.monotonic()
    static = int(_settings().get("bkk_static", 0))
    if static or _layout["now"] == "fs":
        # nothing from the data is visible: request only to keep the box
        # clock right while a PA waits for its start or end time
        if _pa is not None and PA.clock_due():
            _store_good(_fetch())
            now = time.monotonic()
        if _layout["now"] == "fs":
            return now
        _rows, _status = [], None
        _view.update({"kind": "static"})
        cls(bmp)
        draw_static(bmp, varinit.if_long, varinit.if_tall, _settings(),
                    max_y=_bottom_y() if _layout["now"] == "bottom" else None)
        refresh()
        return now
    if _net["good"] is None and (_status is None or _status["kind"] != "offline"):
        cls(bmp)                                   # first data: say we're loading
        _show_status(bmp, "loading")
        refresh()
    data = _fetch()
    now = time.monotonic()
    kind, payload = _store_good(data)
    if _layout["now"] == "fs":                     # a full-screen PA came up meanwhile
        return now
    cls(bmp)
    _net["bridging"] = False
    if kind == "ok":
        _show_rows(bmp, payload)
        refresh()
        return now
    if kind == "info":
        _net["fails"] = 0
        _show_status(bmp, "info", payload)
        refresh()
        return now
    # failed request: bridge with the last good data, then say so; back off
    _net["fails"] += 1
    age = now - _net["good_t"]
    if _net["good"] is not None and age <= STALE_MAX_S:
        _show_rows(bmp, age_rows(_net["good"], age))
        _net["bridging"], _net["bridge_min"] = True, int(age // 60)
    elif _net["good"] is None and now - _net["start_t"] <= STALE_MAX_S:
        _show_status(bmp, "loading")               # still connecting after start-up
        _net["bridging"] = False
    else:
        _show_status(bmp, "offline")
        _net["bridging"] = False
    refresh()
    wait = BACKOFF_S[min(_net["fails"], len(BACKOFF_S) - 1)]
    return now + wait - varinit.updatedelay

def _check_bridge(now):
    """Between requests while showing departures: count the minutes down (a
    bottom-row PA spaces requests out to about a minute) and, after failed
    requests, switch to 'Nincs kapcsolat' as soon as the data is too old."""
    if _layout["now"] == "fs" or _view["kind"] != "rows" or _net["good"] is None: return False
    if now - _net["check_t"] < 5: return False
    _net["check_t"] = now
    age = now - _net["good_t"]
    bmp = varinit.topbottom
    if _net["bridging"] and age > STALE_MAX_S:
        _net["bridging"] = False
        cls(bmp); _show_status(bmp, "offline"); return True
    if int(age // 60) != _net["bridge_min"]:
        _net["bridge_min"] = int(age // 60)
        cls(bmp); _show_rows(bmp, age_rows(_net["good"], age)); return True
    return False

def _pa_gc(now_ms):
    """Collect garbage while a separator is passing, where a short stop shows
    least, so the automatic collection rarely hits the middle of the text."""
    sep = False
    for d in _pa_layer["tgs"].values():
        if d["strip"].sep_visible(now_ms):
            sep = True
            break
    if sep and not _tick["sep"] and now_ms - _tick["gc_t"] >= GC_EVERY_MS:
        t0 = PA.ms()
        gc.collect()
        t = PA.ms()
        d = t - t0
        _pa.shift(d)
        _tick["gc_t"] = _tick["last"] = t
        PERF["gc"] += 1; PERF["gc_ms"] += d
        if d > PERF["gc_max_ms"]: PERF["gc_max_ms"] = d
    _tick["sep"] = sep

def animate_tick():
    now = time.monotonic()
    changed = False
    if _pa is not None and _splash["done"]:
        now_ms = PA.ms()
        gap = now_ms - _tick["last"] if _tick["last"] else 0
        _tick["last"] = now_ms
        if _pa_layer["tgs"] and gap:
            PERF["frames"] += 1
            if gap > 60: PERF["gap_60"] += 1
            if gap > 150: PERF["gap_150"] += 1
            if gap > 500: PERF["gap_500"] += 1
            if gap > PERF["max_gap_ms"]: PERF["max_gap_ms"] = gap
            if gap > PAUSE_MS: _pa.shift(gap - FRAME_MS)   # stalled: carry on where it stopped
        _pa.update(now_ms)
        _pa_gc(now_ms)
        lay = _pa_layout()
        if lay != _layout["now"]:
            was_fs = _layout["now"] == "fs"
            _layout["now"] = lay
            _redraw()
            if was_fs: _net["force"] = True       # fresh departures right after a full-screen PA
            changed = True
        changed = _pa_sync(now_ms) or changed
    changed = _check_bridge(now) or changed
    if _rows:
        blink = max(100, int(_settings().get("arrival_blink_ms", 600))) / 1000
        changed = tick_rows(varinit.topbottom, _rows, now, blink) or changed
    elif _status:
        changed = tick_status(varinit.topbottom, _status, now) or changed
    if changed: refresh()
    if _net["force"]:
        varinit.shared["scroll_timer"] = 0        # host: render (request) on its next pass
    return _hold()

def message_active():
    return False

def refresh_settings():
    if _layout["now"] == "fs":
        return                                     # nothing of the departures is visible
    render()

def on_enter():
    varinit.want_arrivals = True       # host keeps departures under 1 min for us
    varinit.want_rows = 8              # spare departures between spaced-out requests
    load_font()
    load_logo()
    _net["start_t"] = time.monotonic()
    _splash["done"] = False
    _pa_start()
    # start-up logo, like a board coming on; the first departures follow after
    # SPLASH_S seconds (the host renders once the returned time + updatedelay passes)
    _hide_list_layers()
    cls(varinit.topbottom)
    if not draw_logo(varinit.topbottom, varinit.if_long, varinit.if_tall):
        draw_text(varinit.topbottom, TITLE, 0, TOP)
    refresh()
    return time.monotonic() - varinit.updatedelay + SPLASH_S

def on_exit():
    global _rows, _status
    varinit.want_arrivals = False
    varinit.want_rows = 0
    _pa_stop()
    _rows, _status = [], None
    cls(varinit.topbottom)
