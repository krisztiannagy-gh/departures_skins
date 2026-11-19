"""Wiener Linien (Vienna) skin for /departures.

Two board styles, picked in the settings (wl_style):

street  amber LED stop displays used for trams and buses
        13A  Alser Straße          4
             Skodagasse
        * big line number left, a letter suffix smaller and bottom-aligned
        * destination left-aligned on one line, or split over two lines
          (Bhf. Heiligen- / stadt), S-Bahn / U-Bahn icons at the end of it
        * minutes right-aligned, number only
        * under 1 minute: a square whose bottom-left and top-right quarters
          light up in turn every 0.5 s
        * wheelchair icon after the line number (trams only) once the data
          says the vehicle is step-free (not in the T-Skylt data yet)

ubahn   pale green U-Bahn platform displays
        U4 HÜTTELDORF            2
        * bold 7 px capitals, destination always in capitals, one character
          of space after the line
        * "_" before the minutes when step-free (not in the T-Skylt data yet)
        * under 1 minute: "*" switching between the two minute positions every 2 s

Both: 2 departures in fixed 16 px blocks, all animations inside their block,
no header or clock row. Start-up and loading: the Wiener Linien logo (street) or
the words WIENER LINIEN (U-Bahn). Other system texts left-aligned and vertically
centred: street from the destination column in bold, U-Bahn from the left edge.
Outage: "Derzeit keine Echtzeitinfo!" / "Fahrplanaushang bitte beachten!"
alternating every 4 s; nothing due: "Derzeit keine Abfahrten".

Long names (street): one line if it fits, else split over two lines; if that
still doesn't fit and wl_shorten is on, Bahnhof -> Bhf. and ...straße ->
...str. are tried; what still doesn't fit on line 2 is cut, or scrolled
(only line 2) when the app's "Scroll long destination names" is on.
U-Bahn names are cut or scrolled as a whole.

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
BLOCK = 16              # px per departure
LINE_COL = 24           # street: line number (+ wheelchair icon) column width
DEST_X = LINE_COL + 1   # street: where destinations start
MIN_GAP = 3             # px kept clear between destination and minutes
SCROLL_STEP_S = 0.06
SCROLL_PAUSE_S = 2.0
SQUARE = 14             # street: under-1-minute square (7x7 quarters, line-number height)
SQUARE_S = 0.5
STAR_S = 2.0            # U-Bahn: "*" position change
UB_TOP = 3              # U-Bahn: glyph top in the block (capitals on rows 5-11)
SPLASH_S = 3
TITLE = "Wiener Linien"

ICON_S, ICON_U = "\x01", "\x02"     # S-Bahn / U-Bahn icons inside street text

# Word endings a single over-long word may be split at (with a hyphen).
SPLIT_ENDINGS = ("bahnhof", "brücke", "straße", "strasse", "gasse", "platz", "stadt",
                 "dorf", "berg", "feld", "markt", "allee", "kirchen", "brunn", "graben",
                 "garten", "siedlung", "zentrum", "ring", "weg", "hof", "bad", "see",
                 "au", "ort", "zell")

ACCENT_FALLBACK = {"á": "a", "à": "a", "â": "a", "é": "e", "è": "e", "ê": "e", "ë": "e",
                   "í": "i", "ì": "i", "î": "i", "ó": "o", "ò": "o", "ô": "o", "ő": "ö",
                   "ú": "u", "ù": "u", "û": "u", "ű": "ü", "č": "c", "ć": "c", "š": "s",
                   "ž": "z", "ř": "r", "ň": "n", "ý": "y", "ł": "l", "ś": "s", "ń": "n"}
UPPER = {"ä": "Ä", "ö": "Ö", "ü": "Ü", "é": "É"}

# --- fonts --------------------------------------------------------------------
_FONTS = {}             # "s" "b" "x" "i" (street) or "u" (U-Bahn)
_loaded = None          # which file is loaded: "street" / "ubahn"

def load_fonts(style, base="skins/wl/"):
    """Load only the active style's font file (rows become int bitmasks)."""
    global _loaded
    want = "ubahn" if style == "ubahn" else "street"
    if _loaded == want: return
    _FONTS.clear()
    try:
        import gc; gc.collect()
    except ImportError: pass
    with open(base + ("wl_ubahn.json" if want == "ubahn" else "wl_street.json")) as f:
        raw = json.load(f)
    for name, glyphs in raw.items():
        h = glyphs["_h"]
        font = {"_h": h}
        for c, g in glyphs.items():
            if c == "_h": continue
            font[c] = (g[0], tuple(r if isinstance(r, int) else int(r, 2) for r in g[1:]))   # older files: "0101" strings
        _FONTS[name] = font
    if want == "street":                       # S/U icons usable as text characters
        _FONTS["s"][ICON_S] = _FONTS["i"]["S"]
        _FONTS["s"][ICON_U] = _FONTS["i"]["U"]
    _loaded = want

def _glyph(font, c):
    g = font.get(c)
    if g is None:
        f = ACCENT_FALLBACK.get(c) or ACCENT_FALLBACK.get(c.lower())
        if f: g = font.get(f) or font.get(_upper(f))
    if g is None and "a" <= c <= "z": g = font.get(c.upper())
    if g is None: g = font.get("_") or font.get(" ")
    return g

def text_width(font, text):
    if not text: return 0
    total = 0
    for c in text:
        total += _glyph(font, c)[0] + 1
    return total - 1

def draw_text(bmp, font, text, x, y, color=1, clip_l=0, clip_r=10000):
    h = font["_h"]
    for c in text:
        w, rows = _glyph(font, c)
        if x + w > clip_l and x < clip_r:
            for r in range(h):
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

def fill_rect(bmp, x0, y0, w, h, color=1):
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            try: bmp[x, y] = color
            except Exception: pass

def _upper(text):
    """str.upper() that also handles umlauts and ß on CircuitPython."""
    out = ""
    for c in text:
        if c == "ß": out += "SS"
        elif c in UPPER: out += UPPER[c]
        elif c in ACCENT_FALLBACK: out += _upper(ACCENT_FALLBACK[c])
        else: out += c.upper()
    return out

# --- destination text helpers ----------------------------------------------------
def strip_su(dest):
    """'Westbahnhof S U' -> ('Westbahnhof', 'SU'). Only separate trailing words."""
    words = dest.split(" ")
    icons = ""
    while len(words) > 1 and words[-1] in ("S", "U", "S+U", "U+S"):
        icons = words.pop().replace("+", "") + icons
    return " ".join(words).strip(), icons

def shortened(text, user_pairs=()):
    """Successively shorter versions of text (each step one more rule)."""
    out = []
    for pair in user_pairs:
        if isinstance(pair, (list, tuple)) and len(pair) == 2 and pair[0] and pair[0] in text:
            text = text.replace(pair[0], pair[1])
            out.append(text)
    words = text.split(" ")
    for i in range(len(words) - 1, -1, -1):
        w = words[i]
        end = len(w)
        while end > 0 and w[end - 1] in ",;:)": end -= 1
        core, tail = w[:end], w[end:]
        low = core.lower()
        new = None
        if low == "bahnhof": new = "Bhf."
        elif low in ("straße", "strasse"): new = "Str."
        elif len(low) > 6 and (low.endswith("straße") or low.endswith("strasse")):
            new = core[:-6 if low.endswith("straße") else -7] + "str."
        if new:
            words[i] = new + tail
            text = " ".join(words)
            out.append(text)
    return out

def _split_long_word(font, word, max_w):
    """Split one word that doesn't fit: at a known ending if possible -> (head-, rest)."""
    best = None
    low = word.lower()
    for end in SPLIT_ENDINGS:
        if low.endswith(end) and len(word) - len(end) >= 3:
            head = word[:len(word) - len(end)]
            if head.endswith("-"): head = head[:-1]
            if text_width(font, head + "-") <= max_w and (best is None or len(head) > len(best)):
                best = head
    if best is None:
        k = len(word) - 1
        while k > 1 and text_width(font, word[:k] + "-") > max_w: k -= 1
        best = word[:k]
    rest = word[len(best):]
    if rest.startswith("-"): rest = rest[1:]
    return best + "-", rest

def split_two(font, text, max_w):
    """Break text into (line1, rest) with line1 as long as possible."""
    if text_width(font, text) <= max_w: return text, ""
    best = None
    for i, c in enumerate(text):
        if c == " ": cand, rest = text[:i], text[i + 1:]
        elif c in "-/" and 0 < i < len(text) - 1: cand, rest = text[:i + 1], text[i + 1:]
        else: continue
        if text_width(font, cand) <= max_w: best = (cand.rstrip(" ,;"), rest.lstrip())
        else: break
    if best and best[0]: return best
    first, _, rest = text.partition(" ")
    head, tail = _split_long_word(font, first, max_w)
    return head, (tail + (" " + rest if rest else "")).strip()

def hard_cut(font, text, max_w):
    while text and text_width(font, text) > max_w:
        text = text[:-1]
    return text.rstrip(" /,-")

def _icon_suffix(icons):
    return "".join(" " + (ICON_S if c == "S" else ICON_U) for c in icons)

def fit_street(font, dest, max_w, shorten, scroll, user_pairs=()):
    """Returns (line1, line2, line2_scrolls). line2 == "" -> single line."""
    name, icons = strip_su(dest)
    suffix = _icon_suffix(icons)
    tries = [name] + (shortened(name, user_pairs) if shorten else [])
    for n in tries:
        if text_width(font, n + suffix) <= max_w: return n + suffix, "", False
        l1, rest = split_two(font, n, max_w)
        if not rest: return l1, suffix.lstrip(), False          # icons wrap to line 2
        if text_width(font, rest + suffix) <= max_w: return l1, rest + suffix, False
    l1, rest = split_two(font, tries[-1], max_w)
    if scroll: return l1, rest + suffix, True
    return l1, hard_cut(font, rest, max_w - text_width(font, suffix)) + suffix, False

def split_line_id(line):
    """'13A' -> ('13', 'A'); 'D' -> ('D', ''); 'N38' -> ('N38', '')."""
    i = len(line)
    while i > 0 and line[i - 1].isalpha(): i -= 1
    if 0 < i < len(line) and line[i - 1].isdigit(): return line[:i], line[i:]
    return line, ""

# --- departures -> rows ----------------------------------------------------------
def _parse(departures, max_rows, max_min):
    seen, rows = set(), []
    for d in departures:
        if not isinstance(d, list) or len(d) < 4: continue
        line, dest, mins = str(d[1]).strip(), str(d[2]).split("(")[0].strip(), str(d[3]).strip()
        arriving = (len(d) > 7 and bool(d[7])) or mins == "0"
        step_free = len(d) > 8 and bool(d[8])       # filled once a WL data source exists
        if not arriving and mins.isdigit() and int(mins) > max_min: continue
        key = (line, dest, "now" if arriving else mins)
        if key in seen: continue
        seen.add(key)
        rows.append({"line": line, "dest": dest, "mins": mins, "arriving": arriving,
                     "step_free": step_free, "offset": 0, "next_step": 0, "phase": -1})
        if len(rows) >= max_rows: break
    return rows

def _is_tram(line):
    """Wheelchair icon is only shown for trams: plain numbers below 100 and D, O, WLB."""
    return line in ("D", "O", "WLB") or (line.isdigit() and int(line) < 100)

def build_street(departures, width, height, settings):
    S, B, X = _FONTS["s"], _FONTS["b"], _FONTS["x"]
    rows = _parse(departures, max(1, height // BLOCK), int(settings.get("wl_max_minutes", 60)))
    shorten = int(settings.get("wl_shorten", 1))
    scroll = int(settings.get("dest_scroll", 0))
    pairs = settings.get("dest_abbrev", []) or []
    if not isinstance(pairs, list): pairs = []
    mins_w = text_width(B, "88")
    for i, r in enumerate(rows):
        y0 = i * BLOCK
        big, suf = split_line_id(r["line"])
        lw = text_width(B, big) + (1 + text_width(X, suf) if suf else 0)
        r["y0"], r["big"], r["suf"], r["line_w"] = y0, big, suf, lw
        r["wheel"] = r["step_free"] and _is_tram(r["line"])
        used = lw + (2 + 7 if r["wheel"] else 0)
        r["dest_x"] = DEST_X if used < DEST_X else used + 2
        r["dest_w"] = max(0, width - mins_w - MIN_GAP - r["dest_x"])
        l1, l2, sc = fit_street(S, r["dest"], r["dest_w"], shorten, scroll, pairs)
        r["l1"], r["l2"], r["scroll"] = l1, l2, sc
        r["l2_w"] = text_width(S, l2)
        r["text_y"] = (y0, y0 + 8) if l2 else (y0 + 4, None)
    return rows

def draw_street_row(bmp, r, width, color=1):
    S, B, X = _FONTS["s"], _FONTS["b"], _FONTS["x"]
    y0 = r["y0"]
    x = draw_text(bmp, B, r["big"], 0, y0, color)
    if r["suf"]: draw_text(bmp, X, r["suf"], x, y0 + 5, color)
    if r["wheel"]:
        draw_text(bmp, _FONTS["i"], "W", r["line_w"] + 2, y0 + 7, color)
    ya, yb = r["text_y"]
    draw_text(bmp, S, r["l1"], r["dest_x"], ya, color, clip_l=r["dest_x"], clip_r=r["dest_x"] + r["dest_w"])
    if yb is not None: draw_line2(bmp, r, color)
    if not r["arriving"]:
        m = r["mins"]
        if m.isdigit(): draw_text(bmp, B, m, width - text_width(B, m), y0, color)
        else: draw_text(bmp, S, m, width - text_width(S, m), y0 + 4, color)

def draw_line2(bmp, r, color=1):
    y = r["text_y"][1]
    clear_rect(bmp, r["dest_x"], y, r["dest_w"], 7)
    draw_text(bmp, _FONTS["s"], r["l2"], r["dest_x"] - r["offset"], y, color,
              clip_l=r["dest_x"], clip_r=r["dest_x"] + r["dest_w"])

def draw_square(bmp, r, width, phase, color=1):
    """Under 1 minute: bottom-left quarter (phase 0) / top-right quarter (phase 1)."""
    x0, y0 = width - SQUARE, r["y0"]
    half = SQUARE // 2
    clear_rect(bmp, x0, y0, SQUARE, SQUARE)
    if phase == 0: fill_rect(bmp, x0, y0 + half, half, half, color)
    else: fill_rect(bmp, x0 + half, y0, half, half, color)

def build_ubahn(departures, width, height, settings):
    U = _FONTS["u"]
    rows = _parse(departures, max(1, height // BLOCK), int(settings.get("wl_max_minutes", 60)))
    scroll = int(settings.get("dest_scroll", 0))
    line_w = max([text_width(U, "U4")] + [text_width(U, _upper(r["line"])) for r in rows])
    dest_x = line_w + 1 + text_width(U, "U") + 1
    for i, r in enumerate(rows):
        r["y0"] = i * BLOCK
        r["line"] = _upper(r["line"])
        name = _upper(strip_su(r["dest"])[0])
        # each row keeps clear only what its own minutes need ("2", "_11", "*")
        m = "88" if r["arriving"] else r["mins"]
        mins_w = text_width(U, ("_" if r["step_free"] else "") + m)
        dest_w = max(0, width - mins_w - 2 - dest_x)
        r["dest_x"], r["dest_w"] = dest_x, dest_w
        if text_width(U, name) <= dest_w: r["scroll"] = False
        elif scroll: r["scroll"] = True
        else: name, r["scroll"] = hard_cut(U, name, dest_w), False
        r["name"], r["l2_w"] = name, text_width(U, name)
    return rows

def draw_ubahn_row(bmp, r, width, color=1):
    U = _FONTS["u"]
    y = r["y0"] + UB_TOP
    draw_text(bmp, U, r["line"], 0, y, color)
    draw_ubahn_dest(bmp, r, color)
    if not r["arriving"]:
        m = r["mins"]
        x = width - text_width(U, m)
        draw_text(bmp, U, m, x, y, color)
        if r["step_free"]: draw_text(bmp, U, "_", x - text_width(U, "_") - 1, y, color)

def draw_ubahn_dest(bmp, r, color=1):
    y = r["y0"] + UB_TOP
    clear_rect(bmp, r["dest_x"], y, r["dest_w"], _FONTS["u"]["_h"])
    draw_text(bmp, _FONTS["u"], r["name"], r["dest_x"] - r["offset"], y, color,
              clip_l=r["dest_x"], clip_r=r["dest_x"] + r["dest_w"])

def draw_star(bmp, r, width, phase, color=1):
    """Under 1 minute: '*' in the ones (phase 0) or tens (phase 1) minute position."""
    U = _FONTS["u"]
    y = r["y0"] + UB_TOP
    slot = text_width(U, "8") + 1
    clear_rect(bmp, width - 2 * slot, y, 2 * slot, U["_h"])
    x = width - text_width(U, "*") - (slot if phase else 0)
    draw_text(bmp, U, "*", x, y, color)

def tick_rows(bmp, rows, style, width, now, color=1):
    changed = False
    for r in rows:
        if r["arriving"]:
            phase = int(now / (STAR_S if style == "ubahn" else SQUARE_S)) % 2
            if phase != r["phase"]:
                r["phase"] = phase
                if style == "ubahn": draw_star(bmp, r, width, phase, color)
                else: draw_square(bmp, r, width, phase, color)
                changed = True
        if r["scroll"] and now >= r["next_step"]:
            overflow = r["l2_w"] - r["dest_w"]
            dirty = False
            if r["next_step"] == 0:
                r["next_step"] = now + SCROLL_PAUSE_S
            elif r["offset"] >= overflow:
                r["offset"] = 0
                r["next_step"] = now + SCROLL_PAUSE_S
                dirty = True
            else:
                r["offset"] += 1
                r["next_step"] = now + (1.0 if r["offset"] >= overflow else SCROLL_STEP_S)
                dirty = True
            if dirty:
                if style == "ubahn": draw_ubahn_dest(bmp, r, color)
                else: draw_line2(bmp, r, color)
                changed = True
    return changed

# --- system texts ------------------------------------------------------------
# Real boards show them left-aligned: street style from the destination column
# (bold), U-Bahn style from the left edge. Each entry is a list of pages; pages
# alternate every PAGE_S seconds.
PAGE_S = 4
PAGES = {
    "offline": (("Derzeit keine", "Echtzeitinfo!"), ("Fahrplanaushang", "bitte beachten!")),
    "empty": (("Derzeit keine", "Abfahrten"),),
}

def wrap_text(font, text, width):
    lines, cur = [], ""
    for w in text.split(" "):
        t = w if not cur else cur + " " + w
        if text_width(font, t) <= width or not cur: cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return [hard_cut(font, l, width) for l in lines]

def text_lines(style, lines, width, height):
    """[(text, x, y)] left-aligned, vertically centred. U-Bahn: capitals, one per block."""
    if style == "ubahn":   # glyph rows 0-1 hold umlaut dots, capitals are rows 2-8
        font, pitch, top, body, x = _FONTS["u"], BLOCK, 2, 7, 0
        lines = [_upper(l) for l in lines]
    else:
        font, pitch, top, body, x = _FONTS["t"], 8, 0, 7, DEST_X
    avail = width - x
    out_lines = []
    for l in lines: out_lines += wrap_text(font, l, avail)
    out_lines = out_lines[:max(1, height // pitch)]
    span = (len(out_lines) - 1) * pitch + body
    y = (height - span) // 2 - top
    return font, [(l, x, y + i * pitch) for i, l in enumerate(out_lines)]

def draw_lines(bmp, style, lines, width, height, color=1):
    font, out = text_lines(style, lines, width, height)
    for l, x, y in out: draw_text(bmp, font, l, x, y, color)

def draw_title(bmp, style, width, height, color=1):
    """Start-up / loading: the logo on street boards, the words on U-Bahn boards."""
    logo = _FONTS.get("logo", {}).get("L") if style != "ubahn" else None
    if logo and height >= _FONTS["logo"]["_h"]:
        draw_text(bmp, _FONTS["logo"], "L", (width - logo[0]) // 2, (height - _FONTS["logo"]["_h"]) // 2, color)
        return
    U = _FONTS.get("u") or _FONTS["s"]
    t = _upper(TITLE) if style == "ubahn" else TITLE
    top, body = (2, 7) if style == "ubahn" else (0, 7)
    draw_text(bmp, U, t, (width - text_width(U, t)) // 2, (height - body) // 2 - top, color)

# --- network handling (same as the BKK skin) -------------------------------------
STALE_MAX_S = 120
BACKOFF_S = (20, 30, 60)
FAIL_MARKERS = ("-", "*", "**", "***")

def classify(data, fail_texts=(), prompt_texts=()):
    if not data: return "ok", []
    first = data[0]
    if isinstance(first, list) and first and first[0] == "1":
        msg = str(first[1]).strip() if len(first) > 1 else ""
        if msg in FAIL_MARKERS or msg.startswith("^") or msg in fail_texts:
            return "fail", None
        if msg in prompt_texts:
            return "info", msg
        print("WL skin: server message treated as 'no departures':", msg)
        return "ok", []
    return "ok", data

def age_rows(rows, age_s):
    out, gone = [], int(age_s // 60)
    for d in rows:
        d = list(d)
        while len(d) < 8: d.append("")
        mins = str(d[3]).strip()
        if d[7]:
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

def style_of(settings):
    return "ubahn" if settings.get("wl_style", "street") == "ubahn" else "street"

def board_color(style, brightness):
    """Palette colour for the style, scaled like the app's own colours()."""
    f = int(brightness) + 1
    # full brightness: street #FF9E00, U-Bahn #C8E000
    r, g, b = (f * 40, f * 224 // 5, 0) if style == "ubahn" else (f * 51, f * 158 // 5, 0)
    return (min(255, r) << 16) | (min(255, g) << 8) | min(255, b)

# --- host glue ----------------------------------------------------------------
_rows = []
_status = None          # kind of status screen on show, or None
_style = "street"
_net = {"good": None, "good_t": 0.0, "fails": 0, "bridging": False, "bridge_min": -1, "check_t": 0.0}

def _settings():
    return varinit.settings

def _apply_color():
    c = board_color(_style, _settings().get("brightness", 0))
    try:
        if varinit.palette[1] == c: return
    except Exception: pass
    varinit.palette[1] = c
    for p in ("dest_palette", "overlay_palette"):
        try: getattr(varinit, p)[1] = c
        except Exception: pass

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

def _prepare():
    """Pick up the board style: load its font, set its colour."""
    global _style
    _style = style_of(_settings())
    load_fonts(_style)
    _apply_color()

_page = {"i": 0, "t": 0.0, "info": None}

def _draw_status(bmp):
    w, h = varinit.if_long, varinit.if_tall
    clear_rect(bmp, 0, 0, w, h)
    if _status in ("loading", "splash"): draw_title(bmp, _style, w, h)
    elif _status == "info": draw_lines(bmp, _style, [_page["info"]], w, h)
    else:
        pages = PAGES[_status]
        draw_lines(bmp, _style, pages[_page["i"] % len(pages)], w, h)

def _show_status(bmp, kind, text=None):
    global _status, _rows
    if kind != _status: _page["i"] = 0
    _rows, _status = [], kind
    _page["info"], _page["t"] = text, time.monotonic() + PAGE_S
    _draw_status(bmp)

def _tick_pages(now):
    if _status in PAGES and len(PAGES[_status]) > 1 and now >= _page["t"]:
        _page["i"] += 1
        _page["t"] = now + PAGE_S
        _draw_status(varinit.topbottom)
        return True
    return False

def _show_rows(bmp, departures):
    global _status, _rows
    _status = None
    w, h = varinit.if_long, varinit.if_tall
    if _style == "ubahn":
        _rows = build_ubahn(departures, w, h, _settings())
        for r in _rows: draw_ubahn_row(bmp, r, w)
    else:
        _rows = build_street(departures, w, h, _settings())
        for r in _rows: draw_street_row(bmp, r, w)
    if not _rows:
        _show_status(bmp, "empty")
        return
    tick_rows(bmp, _rows, _style, w, time.monotonic())

def render():
    _prepare()
    _hide_list_layers()
    bmp = varinit.topbottom
    if _net["good"] is None and _status != "offline":
        cls(bmp)
        _show_status(bmp, "loading")
        refresh()
    _md = varinit.settings.get("maxdest", 5)
    varinit.settings["maxdest"] = max(int(_md), varinit.if_tall // BLOCK + 3)
    try: data = get_departure(num="1")
    finally: varinit.settings["maxdest"] = _md
    now = time.monotonic()
    fail_texts, prompt_texts = _host_texts()
    kind, payload = classify(data, fail_texts, prompt_texts)
    cls(bmp)
    _net["bridging"] = False
    if kind == "ok":
        _net["good"], _net["good_t"], _net["fails"] = payload, now, 0
        _show_rows(bmp, payload)
        refresh()
        return now
    if kind == "info":
        _net["fails"] = 0
        _show_status(bmp, "info", payload)
        refresh()
        return now
    _net["fails"] += 1
    age = now - _net["good_t"]
    if _net["good"] is not None and age <= STALE_MAX_S:
        _show_rows(bmp, age_rows(_net["good"], age))
        _net["bridging"], _net["bridge_min"] = True, int(age // 60)
    else:
        _show_status(bmp, "offline")
    refresh()
    wait = BACKOFF_S[min(_net["fails"], len(BACKOFF_S) - 1)]
    return now + wait - varinit.updatedelay

def _check_bridge(now):
    if not _net["bridging"] or now - _net["check_t"] < 5: return False
    _net["check_t"] = now
    age = now - _net["good_t"]
    bmp = varinit.topbottom
    if age > STALE_MAX_S:
        _net["bridging"] = False
        cls(bmp); _show_status(bmp, "offline"); return True
    if int(age // 60) != _net["bridge_min"]:
        _net["bridge_min"] = int(age // 60)
        cls(bmp); _show_rows(bmp, age_rows(_net["good"], age)); return True
    return False

def animate_tick():
    now = time.monotonic()
    _apply_color()                      # brightness changes reset the app's colour
    changed = _check_bridge(now)
    changed = _tick_pages(now) or changed
    if _rows:
        changed = tick_rows(varinit.topbottom, _rows, _style, varinit.if_long, now) or changed
    if changed: refresh()
    return False

def message_active():
    return False

def refresh_settings():
    render()

def on_enter():
    global _status
    varinit.want_arrivals = True        # host keeps departures under 1 min for us
    _prepare()
    _hide_list_layers()
    cls(varinit.topbottom)
    _status = "splash"
    _draw_status(varinit.topbottom)
    refresh()
    return time.monotonic() - varinit.updatedelay + SPLASH_S

def on_exit():
    global _rows, _status, _loaded
    varinit.want_arrivals = False
    _rows, _status = [], None
    _FONTS.clear(); _loaded = None
    cls(varinit.topbottom)
    try:
        from functions import colors
        colors()                        # give the app its own colour back
    except Exception: pass
