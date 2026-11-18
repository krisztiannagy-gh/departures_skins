### Real-board texts, logo, bigger departing square

- **Departing now (street):** the square is now 14×14 px, the height of the line number. Each lit quarter is 7×7 px, level with one destination line.
- **"0 minutes" counts as departing now:** a departure sent as 0 minutes shows the square (street) or `*` (U-Bahn) instead of a plain 0.
- **Start-up and loading:** street style shows the Wiener Linien logo, centred. U-Bahn style shows WIENER LINIEN (U-Bahn boards never show logos).
- **Status texts as on the real boards**, left-aligned and vertically centred. Street style uses a bold font starting at the destination column; U-Bahn style uses capitals starting at the left edge:
  - No data: *Derzeit keine Echtzeitinfo!* and *Fahrplanaushang bitte beachten!*, alternating every 4 s.
  - Nothing due: *Derzeit keine Abfahrten*.
  - Messages from the app (e.g. select a station) use the same layout.
- **Colours:** street #FF9E00, U-Bahn #C8E000 at full brightness, scaled down with the brightness setting.
- **Line numbers:** digits redrawn by hand with even 2 px strokes; the 0 no longer has a slash.

The box updates the skin by itself.
