# Chart — user feature reference

What the operator sees when they hit `/chart`. Marketing /
onboarding / support copy can lift directly from this file.

---

## Live price chart

* **Symbol selector** — type a symbol (NIFTY, BANKNIFTY, RELIANCE,
  etc.) or tap a quick-pick chip. Auto-uppercases.
* **Timeframe selector** — 1m / 5m / 15m / 1h / 1D buttons. Mobile
  shows a horizontally scrollable strip; the active timeframe
  auto-scrolls into view.
* **Live ticks** — the last candle updates in real time as the WS
  streams from the broker. The chart's right edge stays anchored
  to "now".
* **Status pill** — top-right of the chart area. Three colours:
  green "Live" / amber "Reconnecting in Xs..." / red "Disconnected".
  When disconnected, a "Reconnect now" button appears so the
  operator can skip the exponential-backoff wait.
* **Day OHLCV header** — symbol, current price (large), absolute
  + percentage change vs today's open, today's open / high / low
  / volume. Mobile collapses to 2 lines (price + change above,
  H/L below). Desktop shows the full row inline.

## Markers overlay (paper-trading visualisation)

Pick a strategy from the **Strategy dropdown** and the chart
overlays paper-trading entries and exits as on-canvas markers:

| Marker shape | Colour | Meaning                                      |
| ------------ | ------ | -------------------------------------------- |
| Up-arrow ▲   | Green  | ENTRY — paper trade opened at this price     |
| Circle ●     | Blue   | TARGET HIT — exited at profit target         |
| Down-arrow ▼ | Red    | STOP HIT — exited at stop-loss / trailing    |
| Square ■     | Grey   | EXIT — squared off / time / indicator-driven |

* **Click a marker** → the bottom **Paper Trades** panel scrolls
  to the matching row and highlights it.
* **Click a row in the panel** → the chart centres on that
  marker's timestamp and the marker pulses at 2× size.
* **Empty states**:
  * No strategy selected → "Strategy select karo to paper trades
    dikhenge."
  * Strategy selected, no trades in window → "Is window mein koi
    paper trade nahi mila."
* **Persistence** — your last-picked strategy is remembered per
  (symbol, timeframe) pair. Comes back the next time you open
  the chart for the same combination.

## Indicators

Click the **Indicators** dropdown in the top bar to toggle:

* **SMA(20)** — yellow line, simple 20-period moving average.
  Default ON.
* **EMA(50)** — purple line, exponential 50-period moving average.
  Default ON.
* **RSI(14)** — cyan line in a separate bottom pane. 70 (red
  dashed) and 30 (green dashed) reference lines for overbought /
  oversold zones. Default ON.
* **MACD** — orange + grey lines + green/red histogram in a
  separate bottom pane. Default OFF (toggle on demand).
* **Volume** — green/red histogram below the price pane. Default
  ON on desktop, OFF on mobile (saves vertical space). Toggle
  to override.
* **Add custom indicator** — placeholder for now. The full custom
  indicator pipeline lands after the launch smoke test.

Toggle preferences persist in localStorage so your defaults stay.

## Scroll-back (historical lazy-load)

* Pan the chart left (drag with mouse / horizontal swipe on
  touch). When the visible range hits the leftmost 20% of loaded
  data, the next ~200 older bars fetch automatically. Multiple
  pans stitch together up to 5 years back for intraday timeframes.
* A small "Loading…" pill appears at the chart's left edge
  during the fetch.
* Daily timeframe is uncapped (backend's own 20-year ceiling
  applies).

## Crosshair tooltip

Hover (or tap-and-hold on mobile) over any candle to see a small
popover with the OHLCV + IST timestamp. The popover follows the
cursor and never spills past the chart edges.

## Touch + mouse gestures

| Gesture                        | Action                                |
| ------------------------------ | ------------------------------------- |
| Mouse drag (left-pressed)      | Pan timeline                          |
| Mouse wheel                    | Pan timeline                          |
| Pinch zoom (touch)             | Zoom in / out                         |
| Touch-drag axis                | Scale axis (vertical)                 |
| Double-click on time-axis      | Reset zoom (LWC built-in)             |
| Double-tap on canvas           | Reset to fit-content                  |
| Long-press on candle (mobile)  | OHLCV tooltip + 50ms haptic tick      |
| Two-finger tap-and-drag        | Pinch zoom                            |

## Disconnect handling

* If the broker connection drops mid-session, the status pill
  flips amber + a sonner toast surfaces "Broker connection toot
  gaya". The chart canvas keeps rendering historical candles —
  no blank screen.
* Live updates resume automatically once the broker reconnects
  (5-min reconnect window). If the operator wants to skip the
  wait, the "Reconnect now" button on the pill forces a fresh
  WS attempt.
* Session-expired (15-min JWT lapse) shows a banner with a "Wapas
  login" CTA. Chart history stays visible.

## Mobile-specific behaviour

* Header collapses from 1 row to 2 rows under 768px (price +
  change up top, H/L below).
* Symbol quick-picks hide; type the symbol manually.
* Volume pane defaults to OFF (toggle in Indicators dropdown).
* Status pill shows colour dot only (no text label).
* Paper Trades drawer slides up from the bottom (tap "Paper
  Trades" toggle button) instead of being inline.
