### Smoother PA scrolling

- **No more requests mid-text on the "no departures" screen.** It now waits for the separator, like the departures do: about one request a minute instead of every 20 s at random points.
- **Memory clean-up while the separator passes.** The box's garbage collection stops everything for 50–150 ms. It now runs on purpose while the separator passes, so the automatic one rarely hits the middle of the text. Less garbage is made per frame, so it's needed less often.
- **Stalls become pauses.** After a long stall the text carries on where it stopped instead of jumping. After a short one it catches up at most 2 px per frame.
- **Statistics** for the new `/pa/perf` page (needs Departures 0.994).

The box updates the skin by itself.
