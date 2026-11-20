# London Underground skin — changelog

Skin for the Departures app (needs the krisztiannagy-gh build of Departures, 0.995 or later). The box updates the skin by itself when its `manifest.json` version changes.

The font is Sean Petykowski's London Underground Dot Matrix Typeface (SIL Open Font License 1.1, see `OFL.txt`), redrawn as pixel pictures in `font_src.py`.

## v1 — First version (2026-11-20)
- **Layout (128×32):** two departure rows and a clock, in the real TfL dot-matrix font at its real size. Capitals sit one row below the lowercase baseline, as on the real boards.
- **Rows:** row 1 shows the next train. Row 2 shows train 2 for 6 s, then trains 3 to 6 for 4 s each. Trains 3 to 6 only join if they are due within 30 minutes. Each row has its real order number and no line name.
- **Minutes:** `N mins` or `1 min`. Under 1 minute the minutes disappear and only the number and destination stay.
- **Train leaves:** 15 s after its expected time both rows float out and the list moves up.
- **Animation:** each row is its own block. Old text floats out to the top, then new text floats in from the bottom, cut off at the block's edges.
- **Long names:** setting *Long station names*, scroll (default) or cut. Scrolling holds 0.8 s, moves at the app's scroll speed (Normal 30 px/s, Low 20 px/s), then holds again. In row 2 the train stays until its name has finished scrolling. Rows that don't rotate repeat the scroll.
- **Clock:** box local time, `HH:MM:SS`, in the bold TfL digits, always in the same place.
- **No trains, no data or loading:** the line and direction from the settings, centred (TfL's rule for an empty indicator). Both empty: only the clock. When requests keep failing, the last trains keep counting down for 2 minutes first.
- **Hide trains to:** T-Skylt has no platform or direction for London, so destinations of the other direction are listed here. " Underground Station" is removed from every destination.
- Colour #FFA000 at full brightness, scaled with the brightness setting.
