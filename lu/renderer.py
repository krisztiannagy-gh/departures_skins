"""London Underground skin for /departures (T-Skylt X, 128 x 32).

Classic amber platform indicator, built from the real TfL dot-matrix font
(see font_src.py and OFL.txt):

    1 Edgware                3 mins
    2 Morden                 7 mins
               13:24:36

* Row 1: the next train. Row 2: the second train, then trains 3..6 in turn
  (train 2 for 6 s, the others 4 s each) - only trains due within 30 min
  join the rotation, trains 1 and 2 are always shown.
* Order numbers are the real arrival order; no line names on the rows.
* Minutes: "N mins", "1 min", blank under 1 minute (no "Due").
* When train 1 has gone (15 s after its expected time) both rows float out
  and the list moves up.
* Every row is its own block: old text floats out to the top, then the new
  text floats in from the bottom, clipped at the block's edges.
* Long names: cut, or scrolled (hold 0.8 s, scroll, hold, float out).
* Clock: box local time, HH:MM:SS, Bold digits, fixed position.
* No trains / no data / loading: line and direction from the settings,
  centred (TfL Customer Information Standard 5.3.3.7); clock only if both
  are empty.
* "Hide trains to": destinations of the other direction (T-Skylt has no
  platform or direction for London).

Spec: london-skin-spec.md in the MatrixBOX project.

Contract: on_enter(), render(), animate_tick(), message_active(),
refresh_settings(), on_exit()
"""
import time, json

try:
    import varinit, displayio
    from functions import cls, get_departure
    _HOST = True
except ImportError:          # desktop tests inject their own modules
    _HOST = False
try:
    import bitmaptools
except ImportError:
    bitmaptools = None

# --- constants ----------------------------------------------------------------
BLOCKS = ((0, 10), (11, 22))    # animation blocks (first, last pixel row) of rows 1 and 2
TEXT_Y = (1, 12)                # top of the 10-row text box in each block
CLOCK_Y = 24
MIN_GAP = 3                     # px between destination area and minutes
ANIM_MS = 400                   # float out / float in, each
DWELL_2_MS = 6000               # row 2: train 2
DWELL_MS = 4000                 # row 2: trains 3+
HOLD_START_MS = 800             # long name: still before it scrolls
HOLD_END_ROT_MS = 1000          # long name: still at the end (rotating row 2)
HOLD_END_STATIC_MS = 2000       # long name: still at the end (rows that don't rotate)
SPEED_PX_S = (30, 20)           # host "Scroll speed": Normal, Low
WINDOW_S = 30 * 60              # trains 3+ join the rotation when due within this
MAX_TRAINS = 6
GRACE_S = 15                    # a train stays this long after its expected time
REQUEST_S = 30
STALE_MAX_S = 120               # requests failing: keep counting down this long
BACKOFF_S = (20, 30, 60)
PREFER_IDLE_S = 60              # data younger than this waits for a still moment
STALL_MS = 150                  # frame gap counted as a stall (timers shifted)
COLOR = (51, 32, 0)             # x brightness factor 1..5 -> #FFA000 at full
SUFFIX = " underground station"
FAIL_MARKERS = ("-", "*", "**", "***")
ACCENT_FALLBACK = {"á": "a", "à": "a", "â": "a", "ä": "a", "é": "e", "è": "e", "ê": "e",
                   "ë": "e", "í": "i", "ì": "i", "î": "i", "ï": "i", "ó": "o", "ò": "o",
                   "ô": "o", "ö": "o", "ő": "o", "ú": "u", "ù": "u", "û": "u", "ü": "u",
                   "ű": "u", "ç": "c", "ñ": "n", "ß": "s", "’": "'", "‘": "'"}


def ms():
    try: return time.monotonic_ns() // 1000000
    except Exception: return int(time.monotonic() * 1000)


# --- fonts --------------------------------------------------------------------
_F = {}                         # "r": regular (10 rows), "c": clock (8 rows)

def load_fonts(base="skins/lu/"):
    if _F: return
    for key, name in (("r", "lu_font.json"), ("c", "lu_clock.json")):
        with open(base + name) as f:
            raw = json.load(f)
        font = {"_h": raw["_h"]}
        for c, g in raw.items():
            if len(c) > 1: continue           # "_h", "_c" (licence notice)
            font[c] = (g[0], tuple(g[1:]))
        _F[key] = font

def _glyph(font, c):
    g = font.get(c)
    if g is None:
        f = ACCENT_FALLBACK.get(c) or ACCENT_FALLBACK.get(c.lower())
        if f: g = font.get(f) if c.islower() else (font.get(f.upper()) or font.get(f))
    return g                                   # None: not drawn at all

def advance(font, text):
    w = 0
    for c in text:
        g = _glyph(font, c)
        if g: w += g[0]
    return w

def ink_width(font, text):
    """Width up to the last lit column (advance minus the trailing gap)."""
    return max(0, advance(font, text) - 1)

def hard_cut(font, text, max_w):
    while text and ink_width(font, text) > max_w:
        text = text[:-1]
    return text.rstrip(" /,-&")

def text_bitmap(font, text):
    """1-bit bitmap of a text (lit pixels = 1)."""
    h = font["_h"]
    bmp = displayio.Bitmap(max(1, advance(font, text)), h, 10)   # same depth as the board bitmap (blit)
    x = 0
    for c in text:
        g = _glyph(font, c)
        if not g: continue
        w, rows = g
        for r in range(h):
            bits = rows[r]
            if not bits: continue
            for col in range(w):
                if bits & (1 << (w - 1 - col)): bmp[x + col, r] = 1
        x += w
    return bmp


# --- bitmap helpers (bitmaptools on the box, plain loops in tests) ------------------
def fill(bmp, x1, y1, x2, y2, v=0):
    if bitmaptools is not None:
        bitmaptools.fill_region(bmp, x1, y1, x2, y2, v)
        return
    for y in range(y1, y2):
        for x in range(x1, x2): bmp[x, y] = v

def blit(dst, src, x, y, x1, y1, x2, y2):
    if bitmaptools is not None:
        bitmaptools.blit(dst, src, x, y, x1=x1, y1=y1, x2=x2, y2=y2)
        return
    for sy in range(y1, y2):
        for sx in range(x1, x2): dst[x + sx - x1, y + sy - y1] = src[sx, sy]

def blit_clipped(dst, src, x, y, sx1, sx2, b0, b1):
    """Copy columns sx1..sx2 of src to (x, y), only the rows inside b0..b1."""
    sy1 = max(0, b0 - y)
    sy2 = min(src.height, b1 + 1 - y)
    sx2 = min(sx2, src.width)
    if sy2 <= sy1 or sx2 <= sx1: return
    blit(dst, src, x, y + sy1, sx1, sy1, sx2, sy2)


# --- text clean-up and the platform filter -------------------------------------------
def clean_dest(dest):
    d = str(dest).strip()
    i = d.lower().find(SUFFIX)
    if i >= 0: d = (d[:i] + d[i + len(SUFFIX):]).strip()
    return d

def hidden(dest, hide):
    low = dest.lower()
    for h in hide:
        if h and low.startswith(h): return True
    return False

def hide_list(settings):
    raw = settings.get("lu_hide_dest", [])
    if isinstance(raw, str): raw = raw.split(",")
    out = []
    for h in raw:
        h = clean_dest(h).lower()
        if h: out.append(h)
    return out


# --- trains -----------------------------------------------------------------
_key = [0]

def parse(data, fetch_ms, hide):
    """Host rows -> [{"dest", "due"}] sorted by due time (ms on the box clock)."""
    out = []
    for d in data:
        if not isinstance(d, list) or len(d) < 4: continue
        dest = clean_dest(d[2])
        if not dest or hidden(dest, hide): continue
        secs = None
        if len(d) > 9:
            try: secs = int(d[9])
            except Exception: secs = None
        if secs is None:
            mins = str(d[3]).strip()
            if not mins.isdigit(): continue
            arriving = (len(d) > 7 and bool(d[7])) or mins == "0"
            secs = 30 if arriving else int(mins) * 60
        due = fetch_ms + secs * 1000
        dup = False
        for t in out:
            if t["dest"] == dest and abs(t["due"] - due) < 20000:
                dup = True
                break
        if not dup: out.append({"dest": dest, "due": due, "key": 0})
    out.sort(key=lambda t: t["due"])
    return out

def merge(old, new, departed):
    """Keep each train's identity across requests (same destination, expected
    time within 90 s); drop trains that already left the board."""
    used = set()
    keep = []
    for t in new:
        gone = False
        for g in departed:
            if g["dest"] == t["dest"] and abs(g["due"] - t["due"]) < 60000:
                gone = True
                break
        if gone: continue
        best, best_d = None, 90001
        for o in old:
            if o["key"] in used or o["dest"] != t["dest"]: continue
            dd = abs(o["due"] - t["due"])
            if dd < best_d: best, best_d = o, dd
        if best is not None:
            t["key"] = best["key"]
            used.add(best["key"])
        else:
            _key[0] += 1
            t["key"] = _key[0]
        keep.append(t)
    return keep

def mins_value(train, now):
    """-1 = blank (under 1 minute / at the platform), else whole minutes."""
    secs = (train["due"] - now) // 1000
    if secs < 60: return -1
    return max(1, (secs + 30) // 60)

def mins_text(v):
    if v < 0: return ""
    return "1 min" if v == 1 else str(v) + " mins"

def rotation(trains, now):
    """Indexes row 2 rotates through: train 2 always, 3..6 if due within 30 min."""
    out = [1] if len(trains) > 1 else []
    for i in range(2, min(len(trains), MAX_TRAINS)):
        if trains[i]["due"] - now <= WINDOW_S * 1000: out.append(i)
    return out


# --- row content ------------------------------------------------------------
class Item:
    """What one row shows: a departure ("dep") or a text ("text", centred)."""
    def __init__(self, kind, text, width, cut, num=0, train=None, now=0):
        self.kind, self.text, self.num, self.train = kind, text, num, train
        self.key = train["key"] if train else None
        self.width, self.cut = width, cut
        R = _F["r"]
        self.num_bmp = None
        self.mins_val, self.mins_bmp, self.mins_ink, self.reserved = -1, None, 0, 0
        if kind == "dep":
            label = str(num) + " "
            self.num_bmp = text_bitmap(R, label)
            self.dest_x = advance(R, label)
            self.set_mins(mins_value(train, now), layout=False)
        self.layout()

    def layout(self):
        R = _F["r"]
        text = self.text
        if self.kind == "dep":
            right = self.width - (self.reserved + MIN_GAP if self.reserved else 0)
            self.dest_w = max(0, right - self.dest_x)
        else:
            w = ink_width(R, text)
            self.dest_x = (self.width - w) // 2 if w <= self.width else 0
            self.dest_w = self.width - self.dest_x
        self.overflow = 0
        if ink_width(R, text) > self.dest_w:
            if self.cut: text = hard_cut(R, text, self.dest_w)
            else: self.overflow = ink_width(R, text) - self.dest_w
        self.dest_bmp = text_bitmap(R, text) if text else None

    def set_mins(self, v, layout=True):
        """New minutes value. True if the row needs redrawing."""
        if v == self.mins_val and (self.mins_bmp is not None or v < 0): return False
        self.mins_val = v
        t = mins_text(v)
        R = _F["r"]
        if t:
            self.mins_bmp = text_bitmap(R, t)
            self.mins_ink = ink_width(R, t)
        else:
            self.mins_bmp, self.mins_ink = None, 0
        if self.mins_ink > self.reserved:      # the column only ever grows
            self.reserved = self.mins_ink
            if layout: self.layout()
        return True


class Row:
    def __init__(self, i):
        self.i = i
        self.item = None
        self.phase = "idle"          # idle | out | outdone | in
        self.t0 = 0                  # start of the current animation
        self.shown = 0               # when the current item came to rest
        self.dy = 0
        self.offset = 0
        self.dirty = True
        self.planned = None          # `shown` the timers below were planned for
        b0, b1 = BLOCKS[i]
        self.out_dist = TEXT_Y[i] - b0 + 10
        self.in_dist = b1 + 1 - TEXT_Y[i]

    # timeline of a long name, all relative to self.shown
    def hold_end(self): return self.shown + HOLD_START_MS
    def scroll_end(self, speed): return self.hold_end() + self.item.overflow * 1000 // speed
    def scrolls(self): return self.item is not None and self.item.overflow > 0

    def start_out(self, now):
        self.t0 = now
        self.phase = "out" if self.item is not None else "outdone"

    def start_in(self, item, now):
        self.item, self.t0, self.offset = item, now, 0
        if item is None:
            self.phase, self.dy, self.dirty = "idle", 0, True
        else:
            self.phase, self.dy = "in", self.in_dist
            self.dirty = True

    def update(self, now, speed):
        if self.phase == "out":
            p = (now - self.t0) / ANIM_MS
            if p >= 1:
                self.phase, dy = "outdone", -self.out_dist
            else:
                dy = -int(self.out_dist * p * p + 0.5)          # speeds up as it leaves
            if dy != self.dy: self.dy, self.dirty = dy, True
        elif self.phase == "in":
            p = (now - self.t0) / ANIM_MS
            if p >= 1:
                self.phase, self.shown, dy = "idle", self.t0 + ANIM_MS, 0
            else:
                q = 1 - p
                dy = int(self.in_dist * q * q + 0.5)             # eases into place
            if dy != self.dy: self.dy, self.dirty = dy, True
        elif self.phase == "idle" and self.scrolls():
            off = 0
            if now > self.hold_end():
                off = min(self.item.overflow, (now - self.hold_end()) * speed // 1000)
            if off != self.offset: self.offset, self.dirty = off, True

    def draw(self, bmp, width):
        b0, b1 = BLOCKS[self.i]
        fill(bmp, 0, b0, width, b1 + 1, 0)
        it = self.item
        self.dirty = False
        if it is None or self.phase == "outdone": return
        y = TEXT_Y[self.i] + self.dy
        if it.num_bmp is not None:
            blit_clipped(bmp, it.num_bmp, 0, y, 0, it.num_bmp.width, b0, b1)
        if it.dest_bmp is not None:
            blit_clipped(bmp, it.dest_bmp, it.dest_x, y, self.offset, self.offset + it.dest_w, b0, b1)
        if it.mins_bmp is not None:
            blit_clipped(bmp, it.mins_bmp, width - it.mins_ink, y, 0, it.mins_ink, b0, b1)

    def shift(self, d):
        self.t0 += d
        self.shown += d


# --- board -------------------------------------------------------------------
class Board:
    """Everything below the host glue: departures in, frames out (testable)."""
    def __init__(self, width):
        self.width = width
        self.rows = [Row(0), Row(1)]
        self.trains = []
        self.departed = []
        self.mode = None             # "deps" | "text"
        self.texts = ("", "")
        self.trans = None            # [row indexes, items] waiting for those rows to leave
        self.rot_end = 0             # row 2: when the next train comes in
        self.loop_end = [0, 0]       # long names on rows that don't rotate: next re-show
        self.clock = {"sec": None, "str": ""}
        self.cut = False
        self.speed = SPEED_PX_S[0]

    # -- data in
    def set_trains(self, trains):
        self.trains = trains
        for r in self.rows:                     # shown trains follow their new prediction
            it = r.item
            if it is None or it.kind != "dep": continue
            for t in trains:
                if t["key"] == it.key:
                    it.train = t
                    break

    def set_texts(self, line, direction):
        self.texts = (line or "", direction or "")

    def shift(self, d):
        for r in self.rows: r.shift(d)
        self.rot_end += d
        self.loop_end = [t + d for t in self.loop_end]

    # -- transitions
    def _transition(self, idx, items, now):
        for i in idx: self.rows[i].start_out(now)
        self.trans = (idx, items)

    def _dep(self, i, now):
        t = self.trains[i]
        return Item("dep", t["dest"], self.width, self.cut, num=i + 1, train=t, now=now)

    def _text(self, text):
        return Item("text", text, self.width, self.cut) if text else None

    def full_refresh(self, now):
        if self.trains:
            self.mode = "deps"
            items = [self._dep(0, now), self._dep(1, now) if len(self.trains) > 1 else None]
        else:
            self.mode = "text"
            items = [self._text(self.texts[0]), self._text(self.texts[1])]
        self._transition((0, 1), items, now)

    def _rest_times(self, now):
        """Set when rows that just came to rest move next."""
        for r in self.rows:
            if r.phase != "idle": continue
            if r.item is None:
                self.loop_end[r.i] = 0
                continue
            if r.shown != r.planned:
                r.planned = r.shown
                if r.i == 1 and self.mode == "deps":
                    dwell = DWELL_2_MS if r.item.num == 2 else DWELL_MS
                    end = r.shown + dwell
                    if r.scrolls():
                        end = max(end, r.scroll_end(self.speed) + HOLD_END_ROT_MS)
                    self.rot_end = end
                if r.scrolls():
                    self.loop_end[r.i] = r.scroll_end(self.speed) + HOLD_END_STATIC_MS
                else:
                    self.loop_end[r.i] = 0

    def tick(self, now):
        """Advance everything to `now`. Returns True if the bitmap must be redrawn."""
        # trains that have left the board
        while self.trains and now > self.trains[0]["due"] + GRACE_S * 1000:
            self.departed.append(self.trains.pop(0))
        if len(self.departed) > 8: self.departed = self.departed[-8:]
        for r in self.rows: r.update(now, self.speed)
        # rows that have left -> the waiting items come in together
        if self.trans is not None:
            idx, items = self.trans
            if all(self.rows[i].phase == "outdone" for i in idx):
                for i in idx: self.rows[i].start_in(items[i], now)
                self.trans = None
                for r in self.rows: r.update(now, self.speed)
        self._rest_times(now)
        if self.trans is None and all(r.phase == "idle" for r in self.rows):
            self._decide(now)
            for r in self.rows: r.update(now, self.speed)
        # minutes count down in place
        for r in self.rows:
            it = r.item
            if it is not None and it.kind == "dep" and r.phase != "outdone":
                if it.set_mins(mins_value(it.train, now)): r.dirty = True
        return any(r.dirty for r in self.rows)

    def _decide(self, now):
        r1, r2 = self.rows
        if self.trains:
            if self.mode != "deps" or r1.item is None or r1.item.key != self.trains[0]["key"]:
                self.full_refresh(now)
                return
            n = len(self.trains)
            if r2.item is None:
                if n > 1: self._transition((1,), [None, self._dep(1, now)], now)
            elif n < 2:
                self._transition((1,), [None, None], now)
            else:
                idx = r2.item.num - 1
                rot = rotation(self.trains, now)
                if idx >= n or self.trains[idx]["key"] != r2.item.key:
                    self._transition((1,), [None, self._dep(1, now)], now)
                elif len(rot) > 1 and now >= self.rot_end:
                    nxt = rot[0]
                    for j in rot:
                        if j > idx:
                            nxt = j
                            break
                    self._transition((1,), [None, self._dep(nxt, now)], now)
                elif len(rot) <= 1 and self.loop_end[1] and now >= self.loop_end[1]:
                    self._transition((1,), [None, self._dep(idx, now)], now)
            if self.trans is None and self.loop_end[0] and now >= self.loop_end[0]:
                self._transition((0,), [self._dep(0, now), None], now)
            return
        want = [self.texts[0] or None, self.texts[1] or None]
        have = [r.item.text if r.item else None for r in self.rows]
        if self.mode != "text" or want != have:
            self.full_refresh(now)
            return
        for i in (0, 1):
            if self.loop_end[i] and now >= self.loop_end[i]:
                items = [None, None]
                items[i] = self._text(self.texts[i])
                self._transition((i,), items, now)
                return

    def next_motion(self, now):
        """ms until something on the rows moves (0 = moving now)."""
        best = 10 ** 9
        for r in self.rows:
            if r.phase != "idle": return 0
            if r.scrolls():
                if now < r.hold_end(): best = min(best, r.hold_end() - now)
                elif now < r.scroll_end(self.speed): return 0
            if self.loop_end[r.i]: best = min(best, self.loop_end[r.i] - now)
        if self.mode == "deps" and self.rows[1].item is not None and len(self.trains) > 2 \
                and self.trains[2]["due"] - now <= WINDOW_S * 1000:
            best = min(best, self.rot_end - now)
        return max(0, best)

    def draw(self, bmp, force=False):
        for r in self.rows:
            if r.dirty or force: r.draw(bmp, self.width)

    # -- clock
    def draw_clock(self, bmp, sec, force=False):
        """sec = box local time in seconds, or None (unknown: no clock)."""
        C = _F["c"]
        if sec is None:
            if self.clock["sec"] is not None or force:
                fill(bmp, 0, CLOCK_Y, self.width, CLOCK_Y + C["_h"], 0)
                self.clock["sec"], self.clock["str"] = None, ""
                return True
            return False
        if sec == self.clock["sec"] and not force: return False
        t = time.localtime(sec)
        s = "%02d:%02d:%02d" % (t[3], t[4], t[5])
        old = self.clock["str"] if not force else ""
        x = (self.width - ink_width(C, "00:00:00")) // 2
        for i in range(len(s)):
            g = C.get(s[i])
            w = g[0] if g else 0
            if i >= len(old) or old[i] != s[i]:
                fill(bmp, x, CLOCK_Y, x + w, CLOCK_Y + C["_h"], 0)
                if g:
                    gb = _clock_glyph(s[i])
                    blit(bmp, gb, x, CLOCK_Y, 0, 0, gb.width, gb.height)
            x += w
        self.clock["sec"], self.clock["str"] = sec, s
        return True

_clock_bmps = {}
def _clock_glyph(c):
    b = _clock_bmps.get(c)
    if b is None:
        b = text_bitmap(_F["c"], c)
        _clock_bmps[c] = b
    return b


# --- host glue ----------------------------------------------------------------
_board = None
_net = {"good_t": None, "fails": 0, "raw": None, "raw_t": 0, "info": None, "loaded": False,
        "force": False, "station": None}
_tick = {"last": 0}

def _settings():
    return varinit.settings

def _apply_color():
    f = int(_settings().get("brightness", 4)) + 1
    c = (min(255, COLOR[0] * f) << 16) | (min(255, COLOR[1] * f) << 8) | min(255, COLOR[2] * f)
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

def _show():
    try: varinit.display.refresh(minimum_frames_per_second=0)
    except Exception:
        from functions import refresh
        refresh()

def _layers_moved():
    """The app slides its own layers in and redraws the board bitmap when the
    station or settings change (start-up screen with the station name)."""
    try:
        return (varinit.tg3.x != 0 or varinit.tg3.y != 0 or varinit.tg1.y != varinit.if_tall
                or varinit.tg2.y != varinit.if_tall)
    except Exception:
        return False

def _repaint():
    """Take the screen back: our layer only, everything drawn again."""
    _hide_list_layers()
    bmp = varinit.topbottom
    cls(bmp)
    _board.draw(bmp, force=True)
    _board.draw_clock(bmp, _wall(), force=True)
    _show()

def _station():
    try:
        st = _settings()["stations"]["1"]
        return (str(st.get("country", "")), str(st.get("operator", "")), str(st.get("siteid", "")))
    except Exception:
        return None

def _show_loading():
    """Line/direction straight away (no animation) until the first data arrives."""
    _board.trains, _board.departed, _board.trans = [], [], None
    _board.mode = "text"
    for i, r in enumerate(_board.rows):
        r.start_in(_board._text(_board.texts[i]), 0)
        r.phase, r.dy, r.shown = "idle", 0, ms()

def _wall():
    """Box local time in whole seconds, or None while it isn't known yet."""
    ct = getattr(varinit, "currenttime", 0)
    try: ct = int(ct)
    except Exception: return None
    if ct <= 0: return None
    at = getattr(varinit, "currenttime_ms", None)
    if at is None: return ct
    return ct + (ms() - at) // 1000

def _host_texts():
    try:
        import dicts
        L = dicts.language[_settings()["language"]]
        return ((L["settings"]["no_data"],),
                (L["settings"]["select_operator"], L["settings"]["search"], L["display"]["select_station"]))
    except Exception:
        return (), ()

def classify(data, fail_texts=(), prompt_texts=()):
    if not data: return "ok", []
    first = data[0]
    if isinstance(first, list) and first and first[0] == "1":
        msg = str(first[1]).strip() if len(first) > 1 else ""
        if msg in FAIL_MARKERS or msg.startswith("^") or msg in fail_texts: return "fail", None
        if msg in prompt_texts: return "info", msg
        return "ok", []
    return "ok", data

def _configure():
    """Settings -> board (cut/scroll, speed, line/direction texts)."""
    s = _settings()
    _board.cut = s.get("lu_long", "scroll") == "cut"
    try: _board.speed = SPEED_PX_S[1 if int(s.get("scroll", 0)) else 0]
    except Exception: _board.speed = SPEED_PX_S[0]
    if _net["info"]: _board.set_texts(_net["info"], "")
    else: _board.set_texts(str(s.get("lu_line", "")).strip(), str(s.get("lu_direction", "")).strip())

def _rebuild_trains():
    """Re-read the last good data (settings changed: hide list)."""
    if _net["raw"] is None: return
    new = parse(_net["raw"], _net["raw_t"], hide_list(_settings()))
    _board.set_trains(merge(_board.trains, new, _board.departed))

def _fetch():
    md = _settings().get("maxdest", 5)
    _settings()["maxdest"] = max(int(md), 20)
    try: return get_departure(num="1")
    finally: _settings()["maxdest"] = md

def render():
    """Host: time for a request."""
    _net["force"] = False
    t = ms()
    data = _fetch()
    now = ms()
    if _board is not None: _board.shift(now - t)      # the board stood still meanwhile
    _tick["last"] = now
    kind, payload = classify(data, *_host_texts())
    if kind == "ok":
        _net["good_t"], _net["fails"], _net["info"], _net["loaded"] = now, 0, None, True
        # minutes/seconds are counted from when the server answered
        _net["raw"], _net["raw_t"] = payload, now
        _configure()
        _rebuild_trains()
        return time.monotonic() + REQUEST_S - varinit.updatedelay
    if kind == "info":
        _net["fails"], _net["info"], _net["loaded"] = 0, payload, True
        _board.set_trains([])
        _configure()
        return time.monotonic() + REQUEST_S - varinit.updatedelay
    _net["fails"] += 1
    wait = BACKOFF_S[min(_net["fails"], len(BACKOFF_S)) - 1]
    return time.monotonic() + wait - varinit.updatedelay

def _hold(now):
    """True keeps the host from requesting right now (something is about to move)."""
    if _net["force"] or _net["good_t"] is None or _net["fails"]: return False
    if now - _net["good_t"] >= PREFER_IDLE_S * 1000 + REQUEST_S * 1000: return False
    return _board.next_motion(now) < 1500

def animate_tick():
    if _board is None: return False
    now = ms()
    gap = now - _tick["last"] if _tick["last"] else 0
    _tick["last"] = now
    if gap > STALL_MS: _board.shift(gap - 30)          # stalled: carry on where it stopped
    _apply_color()
    if _layers_moved(): _repaint()
    # requests failing for too long: stop counting down old predictions
    if _net["fails"] and _net["good_t"] is not None and now - _net["good_t"] > STALE_MAX_S * 1000:
        if _board.trains: _board.set_trains([])
    changed = _board.tick(now)
    bmp = varinit.topbottom
    if changed: _board.draw(bmp)
    changed = _board.draw_clock(bmp, _wall()) or changed
    if changed: _show()
    return _hold(now)

def message_active():
    return False

def refresh_settings():
    """Host: settings changed. The app has drawn over the board by now."""
    if _board is None: return
    st = _station()
    if st != _net["station"]:                           # another station: start again
        _net.update({"good_t": None, "fails": 0, "raw": None, "raw_t": 0, "info": None,
                     "loaded": False, "station": st})
        _configure()
        _show_loading()
    else:
        _configure()
        _rebuild_trains()
        _board.mode = None                              # rows float out and back with the new settings
    _apply_color()
    _repaint()
    _net["force"] = True                                # fresh data on the next pass
    try: varinit.shared["scroll_timer"] = 0
    except Exception: pass

def on_enter():
    global _board
    varinit.want_arrivals = True       # host keeps trains under 1 minute for us
    varinit.want_rows = 20             # the other direction is filtered out here
    varinit.want_seconds = True        # host adds seconds to expected time (row index 9)
    load_fonts()
    _board = Board(varinit.if_long)
    _net.update({"good_t": None, "fails": 0, "raw": None, "raw_t": 0, "info": None, "loaded": False,
                 "force": False, "station": _station()})
    _configure()
    _apply_color()
    _show_loading()
    _repaint()
    _tick["last"] = ms()
    return time.monotonic() - varinit.updatedelay + 0.3

def on_exit():
    global _board
    varinit.want_arrivals = False
    varinit.want_rows = 0
    varinit.want_seconds = False
    _board = None
    _F.clear()
    _clock_bmps.clear()
    cls(varinit.topbottom)
    try:
        from functions import colors
        colors()                        # give the app its own colour back
    except Exception: pass
