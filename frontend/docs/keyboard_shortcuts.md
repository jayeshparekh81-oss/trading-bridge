# Chart — keyboard shortcuts

Bound at the document level and active on the `/chart` route. The
handler skips while focus is in an input / textarea / select /
contenteditable, so typing in the symbol selector or strategy
selector dropdown won't trigger chart actions. Modifier-key
combinations (Cmd / Ctrl / Alt + key) belong to the OS or browser
and are passed through.

| Key            | Action                              | Notes                          |
| -------------- | ----------------------------------- | ------------------------------ |
| `R` / `r`      | Reset zoom (fit to content)         | Same as double-tap on canvas   |
| `+` / `=`      | Zoom in 20%                         | Anchored to right edge         |
| `-` / `_`      | Zoom out 20%                        | Anchored to right edge         |
| `←` ArrowLeft  | Pan left by 10% of visible span     |                                |
| `→` ArrowRight | Pan right by 10% of visible span    |                                |

Out-of-scope (Day-N polish):
* `Home` / `End` — jump to start / end of loaded data.
* `Shift + ←` / `Shift + →` — pan by 50% (fast scrub).
* `[` / `]` — switch to previous / next timeframe.
* Symbol-search modal (Cmd+K convention).
