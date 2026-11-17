### First release: BKK FUTÁR (Budapest) skin

A clone of the amber LUMINO DFI stop displays used by BKK.

**Layout**
- **Own 7-pixel font:**
  - 1-pixel strokes, never bold.
  - All Hungarian accents fit inside the 7 pixels, and letters like *g* and *y* don't hang below the line.
  - Long vowels (á é í ó ú) get a 2-pixel slanted accent touching the letter; ö and ü get single-pixel dots with a gap.
- **Board spacing:** 1-pixel top margin, 1 pixel between rows, last row touching the bottom edge. The number of rows follows the panel height (4 on X/XS, 8 on 2X).
- **Row format:** `line  destination  N'`, with the minutes always followed by `'`.

**Behaviour**
- **Departing / at the stop:** the line number stays steady, the minutes disappear, and the destination blinks until 15 s after departure.
- Departures more than 60 minutes away are not shown.
- **Duplicate rows** from the data feed are shown once.
- **Long names:**
  - Shortened the BKK way: vasútáll., pu., u., k.né, alulj., ltp., krt., and "x / y" written as "x/y".
  - Then cut, keeping the M / H / M+H transfer marker at the end.
  - Or scrolled, but only inside the destination column, never over the line number or the minutes.
- Includes the ► arrow used in BKK headsigns.

Needs Departures 0.986 or later.
