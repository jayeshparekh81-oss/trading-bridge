# Chart — mobile interactions

The Tailwind `md` breakpoint (768px) is the mobile / desktop
boundary. Below 768px, the chart UI shifts into "mobile mode":
header collapses, status pill shrinks, volume hides, paper-trade
panel becomes a slide-up drawer, etc.

## Gestures

| Gesture                        | Action                                 |
| ------------------------------ | -------------------------------------- |
| Single-finger drag             | Pan timeline horizontally              |
| Pinch (two fingers)            | Zoom in / out (Lightweight Charts)     |
| Touch-drag the time axis       | Stretch / compress the axis            |
| Touch-drag the price axis      | Stretch / compress the price scale     |
| Double-tap on canvas           | Reset to fit-content                   |
| Long-press (≥ 500ms)           | OHLCV tooltip + 50ms haptic vibrate    |
| Tap a marker                   | Open Paper Trades drawer + scroll row  |
| Tap "Paper Trades" toggle      | Open / close the bottom drawer         |

The double-tap window is 300ms with a 24px tolerance for finger
jitter. Multi-finger touchstart aborts the tap-pairing so a pinch
release doesn't accidentally pair with a subsequent tap.

The long-press timer cancels on touchmove > 24px (the operator
was scrolling, not pressing) and on touchend / touchcancel before
500ms (the operator lifted before the threshold).

`navigator.vibrate(50)` is wrapped in try/catch — Safari + some
Android UAs gate vibrate behind quotas + desktop browsers don't
implement it; silent skip is correct UX.

## Layout shifts

| Surface                  | < md (mobile)                                   | ≥ md (desktop)                                  |
| ------------------------ | ----------------------------------------------- | ----------------------------------------------- |
| Header info row          | 2 lines: price+change above, H/L below          | 1 line: SYMBOL + price + change + O/H/L/V       |
| Symbol selector          | Text input only (quick-pick chips hidden)       | Text input + NIFTY / BANKNIFTY chips            |
| Timeframe selector       | Horizontally scrollable strip, auto-centres     | Inline button group                             |
| Status pill              | Coloured dot only, no text label                | Full pill with "Live" / countdown text          |
| Reconnect button         | "↻" glyph                                       | "Reconnect now" text                            |
| Volume pane              | Hidden by default                               | Visible by default                              |
| Indicators dropdown      | Same dropdown menu                              | Same dropdown menu                              |
| Paper Trades panel       | Slide-up bottom drawer (60vh)                   | Inline 280px panel below chart                  |

## Persistence

* Strategy selection persists per `(symbol, timeframe)` to
  localStorage.
* Indicator toggles persist as one localStorage entry; mobile
  default for Volume is OFF (matchMedia at first-load) but the
  operator's override is honoured on subsequent visits.

## Accessibility hooks

* StatusPill renders a hidden text label even when the visible
  label is dot-only on mobile, so screen readers announce the
  state.
* Touch listeners use `passive: true` so the browser doesn't
  warn about janky scrolling.
* Long-press haptic is additive; nothing critical depends on
  vibration succeeding.

## Known gaps (Day-2 mobile sprint scope)

* Symbol picker as a full-screen bottom sheet (current impl
  is just the inline input — works on phone but not as polished
  as a sheet).
* Sidebar hamburger collapse on /chart specifically — owned by
  the dashboard layout, not the chart route.
* Crosshair tap-and-hold tooltip dismissal on touch-out (LWC
  handles the tooltip via crosshairMove which fires on touch
  too; explicit tap-outside dismiss is a polish item).
