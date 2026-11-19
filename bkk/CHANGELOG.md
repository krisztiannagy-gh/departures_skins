# BKK FUTÁR skin — changelog

Skin for the Departures app (needs the krisztiannagy-gh build of Departures, 0.986 or later). The box updates the skin by itself when its `manifest.json` version changes.

## v8 — Passenger announcements (2026-11-20)
- **Draws the passenger announcements** set up on the settings page (needs Departures 0.992).
  - **Full-screen PA:** replaces the departures; each row is fixed or scrolling.
  - **Scrolling PA / Reminder:** in the bottom row; departures, status screens and static mode use the rows above. The loading bar is left out while a PA scrolls there.
- **Request timing:** while a bottom-row PA scrolls, the request waits for the separator once the data is a minute old (at most 2 minutes). No requests under a full-screen PA, except one every 30 minutes for the clock while a PA has a start or end time. Fresh departures right after a full-screen PA.
- **Spare departures:** asks for 8, counts them down between requests.
- **Font:** new characters `% " „ ” “ ’ – — ; = @ # € < [ ] °`.

## v7 — BKK logo at start-up and while loading (2026-11-18)
- **Start-up:** the BKK logo (Budapesti Közlekedési Központ), centred, for 3 s, instead of the "BKK FUTÁR" text.
- **Loading and connecting:** the logo stays up with a thin amber bar on the bottom row. The bar fills from left to right, then empties from left to right, and repeats.
  - It replaces the *Adatok betöltése* screen.
  - It stays while the first requests after start-up fail, for up to 2 minutes, then *Nincs kapcsolat* takes over as before.
  - The bar stands still for the second or two a request is running, because the box can't animate during one.
- **Static mode:** shows the logo or the "BKK FUTÁR" text, your choice under *Static mode shows* (needs Departures 0.991; otherwise the text).
- Boards too small for the logo keep the "BKK FUTÁR" text and the *Adatok betöltése* screen.

## v6 — Status screens instead of a dark board (2026-11-17)
- **Status screens** under the **BKK FUTÁR** header, each with an animated 7×7 icon so you can always see the box is alive:
  - **Adatok betöltése** (turning circle): after start-up, until the first data arrives.
  - **Nincs kapcsolat** (pulsing ⊗): no fresh data for 2 minutes, or none since start-up.
  - **Ebből a megállóból XX percen belül nem indul járat.** (ticking clock): the server answered, but nothing departs within your *Show departures up to* setting.
  - Text wraps by pixel width. Small panels fall back to "Nincs induló járat".
- **Short outages are bridged:**
  - A failed request keeps the last departures on the board for up to 2 minutes, with minutes counted down on the box and departed lines dropped.
  - After 2 minutes it switches to *Nincs kapcsolat* by itself.
- **Gentle on the servers:** while T-skylt can't be reached, requests space out from every 20 s to 30 s, then 60 s. They return to 20 s as soon as an answer comes back.

Works best with Departures 0.989 (10 s request timeout).

## v5 — Static mode: text only (2026-11-17)
- Static mode shows the **BKK FUTÁR** text top left. The picture option, picture file loading and converter tool from v4 have been removed.

## v4 — Start-up text and static mode (2026-11-17)
- **Start-up text:** "BKK FUTÁR" top left (1 px top margin) for 3 seconds whenever the skin starts, like a board powering on.
- **Static mode:** show the BKK FUTÁR text instead of departures. Nothing is fetched while it's on. A picture option was added here and removed again in v5.

Needs Departures 0.987 or later for the settings.

## v3 — Clearer long-name settings (2026-11-17)
- **Long destination names** are now set with two switches instead of one 4-option list:
  - **Shorten long names BKK-style** (skin setting) turns the abbreviations on or off.
  - The app's existing **Scroll long destination names** (*Advanced*) chooses whether what still doesn't fit is cut or scrolled. Real BKK boards never scroll, so cut is the default.

## v2 — Font: ő and ű (2026-11-17)
- **ő** and **ű** now match the real boards: a 4-pixel letter, one empty row, then the 2-pixel double accent. Still 7 pixels in total.

## v1 — First release: BKK FUTÁR (Budapest) skin (2026-11-17)
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
