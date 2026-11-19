# Wiener Linien skin — changelog

Skin for the Departures app (needs the krisztiannagy-gh build of Departures, 0.990 or later). The box updates the skin by itself when its `manifest.json` version changes.

## v4 — Smaller font files (2026-11-20)
- Font files store each pixel row as a number instead of a "0101" string: **15 KB less** on the box (street 19.7 → 7.6 KB, U-Bahn 4.5 → 1.7 KB). Same pixels; older files still load.

## v3 — Real-board texts, logo, bigger departing square (2026-11-18)
- **Departing now (street):** the square is now 14×14 px, the height of the line number. Each lit quarter is 7×7 px, level with one destination line.
- **"0 minutes" counts as departing now:** a departure sent as 0 minutes shows the square (street) or `*` (U-Bahn) instead of a plain 0.
- **Start-up and loading:** street style shows the Wiener Linien logo, centred. U-Bahn style shows WIENER LINIEN (U-Bahn boards never show logos).
- **Status texts as on the real boards**, left-aligned and vertically centred. Street style uses a bold font starting at the destination column; U-Bahn style uses capitals starting at the left edge:
  - No data: *Derzeit keine Echtzeitinfo!* and *Fahrplanaushang bitte beachten!*, alternating every 4 s.
  - Nothing due: *Derzeit keine Abfahrten*.
  - Messages from the app (e.g. select a station) use the same layout.
- **Colours:** street #FF9E00, U-Bahn #C8E000 at full brightness, scaled down with the brightness setting.
- **Line numbers:** digits redrawn by hand with even 2 px strokes; the 0 no longer has a slash.

## v2 — Bold U-Bahn font, Vienna-style icons (2026-11-18)
- **U-Bahn style:** new bold font, 7 px capitals with 2 px strokes (was 9 px and thin), closer to the real platform displays. The `*` and the `_` follow the same font.
- **U-Bahn style:** each row keeps clear only what its own minutes need, so long names like HEILIGENSTADT are no longer cut.
- **Street style:** the U-Bahn icon is now a filled circle with the U cut out, matching the S-Bahn icon (both drawn after the Vienna logos).

## v1 — First Vienna boards (2026-11-17)
- **Two board styles**, picked under *Board style* in the skin's settings:
  - **Street (tram & bus):** amber LED stop display. Big line number (letter suffix smaller, e.g. 13A), destination on one or two lines, S-Bahn and U-Bahn icons at the end of the name, minutes as a plain number on the right.
  - **U-Bahn:** pale green platform display. `U4 HÜTTELDORF`, destination always in capitals, minutes on the right.
- **Departing now (under 1 minute):**
  - Street: a square on the right whose bottom-left and top-right quarters light up in turn every 0.5 s.
  - U-Bahn: a `*` that switches between the two minute positions every 2 s.
- **Long names (street):** split over two lines first (at a space, a hyphen or a common word ending such as -stadt or -gasse). If that still doesn't fit, *Bahnhof* → *Bhf.* and *…straße* → *…str.* (setting *Shorten long names*). What still doesn't fit on line 2 is cut, or only line 2 scrolls if *Scroll long destination names* is on under Advanced. U-Bahn names are cut or scrolled as a whole.
- **Status texts**, centred like Wiener Linien's own: *Wiener Linien* for 3 s at start-up, *Abfahrtszeiten werden geladen*, *Echtzeitinformation derzeit nicht verfügbar*, *In den nächsten XX Minuten keine Abfahrt*. Short outages are bridged for 2 minutes, the same as the BKK skin.
- **Prepared, not yet visible:** the tram wheelchair icon and the U-Bahn `_` (step-free) are built in. They appear once the skin gets Wiener Linien's own data; the T-Skylt data has no step-free information.
- Colours are fixed per style and follow the brightness setting; the LED tone setting is hidden while this skin is active.
