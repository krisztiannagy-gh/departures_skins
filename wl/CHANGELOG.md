# Wiener Linien skin — changelog

Skin for the Departures app (needs the krisztiannagy-gh build of Departures, 0.990 or later). The box updates the skin by itself when its `manifest.json` version changes.

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
