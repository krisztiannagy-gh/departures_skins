### Status screens instead of a dark board

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
