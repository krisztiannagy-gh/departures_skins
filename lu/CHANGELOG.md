# London Underground skin — changelog

Skin for the Departures app (needs the krisztiannagy-gh build of Departures, 0.995 or later). The box updates the skin by itself when its `manifest.json` version changes.

The font is Sean Petykowski's London Underground Dot Matrix Typeface (SIL Open Font License 1.1, see `OFL.txt`), redrawn as pixel pictures in `font_src.py`.

## v3 — Minutes column and warmer amber (2026-11-20)
- **Minutes:** the "m" stays in the same column when "2 mins" becomes "1 min". The minutes are placed as if they always ended in "s", so "1 min" leaves the "s" spot empty instead of moving right.
- **Colour:** warmer amber, #FF7300 at full brightness (was #FFA000, which looked too yellow on the box). Close to the app's own amber.

## v2 — Clean start after adding or changing a station (2026-11-20)
- When a station is added or changed, the app draws its own start-up screen (logo and station name) over the board. The skin now wipes it and redraws the whole board, so the clock is complete and row 1 is no longer covered.
- **Another station:** the old station's trains are dropped at once, the line/direction screen shows, and new data is fetched straight away (before, it could take 20 s or more).
- Other settings changes also fetch fresh data straight away.

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
- Colour #FFA000 at full brightness, scaled with the brightness setting (warmer from v3).
