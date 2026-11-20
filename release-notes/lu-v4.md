### Clock and rows no longer go missing after a network hiccup

- When a data request fails (for example while the Wi-Fi is busy), the app wiped the whole board and the skin only redrew what changed next. The clock then came back digit by digit: seconds first, the hours and colons only much later. The skin now repaints the whole board after every request.
- As a safety net, the whole board is also repainted every 20 seconds.

The box updates the skin by itself.
