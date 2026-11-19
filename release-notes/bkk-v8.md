### Passenger announcements

Shows the announcements you set up on the settings page (needs Departures 0.992, which brings the settings).

- **Full-screen PA:** replaces the departures. Each row is fixed text or a scrolling text that loops on its own row.
- **Scrolling PA** and **Reminder:** scroll in the bottom row. The departures (or the status screens, or the static BKK FUTÁR text/logo) use the rows above.
- Texts enter from the right and leave completely on the left before the next pass starts. Your separator (default `***`) comes before and after the text.
- **Up-to-date departures while a PA scrolls:** a request is made when the separator is on screen once the data is a minute old, so departures are never more than about 1–2 minutes old. The scroll pauses for a second on the separator while it runs. Spare departures are kept and counted down in between.
- **Full-screen PA:** no departure requests while it's up (only one every 30 minutes for the clock, while a PA has a start or end time). Fresh departures are requested as soon as it ends.
- **New characters:** `% " „ ” “ ’ – — ; = @ # € < [ ] °`.

The box updates the skin by itself.
