import type { TutorialScript } from "./_types";

export const READING_CHART_INDICATORS: TutorialScript = {
  topic: "reading-chart-indicators",
  duration_target_seconds: 360,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Aaj top 5 indicators samjhata hu — jo aapke kaam aayenge 80% setups mein. Ye banking-school tutorial nahi hai; ye sirf jo aap actually use karte ho wo cover karta. Chaliye start.",
    sections: [
      {
        time_start: 12,
        time_end: 80,
        narration:
          "Pehla — EMA, Exponential Moving Average. Ye recent prices ko zyada weight deta hai purane prices ke compared. Common pairs: EMA 9 aur EMA 21 for swing trades, EMA 20 aur EMA 50 for position trades. Trade rule simple: chhoti EMA badi ke upar = uptrend, neeche = downtrend. Yahi crossover ek classic entry signal hai.",
        screen_action:
          "TradeTri chart of NIFTY daily with EMA 9 (green) and EMA 21 (blue) overlaid. Cross-up highlighted with green arrow. Cross-down with red arrow.",
        b_roll_suggested:
          "Quick formula card: EMA emphasizes recent — visual showing weight decay over bars",
      },
      {
        time_start: 80,
        time_end: 150,
        narration:
          "Doosra — RSI, Relative Strength Index. Scale 0 se 100. 70 ke upar = recently bahut buying (overbought zone). 30 ke neeche = recently bahut selling (oversold zone). Common mistake: log soch te 'overbought matlab short maaro'. Galat. Strong trends mein RSI 70 ke upar din-bhar rehta. RSI ek input hai, tip nahi.",
        screen_action:
          "Chart with RSI panel below. Period 14. Zones shaded: red above 70, green below 30. Cursor points at specific bars where RSI was 75 but price continued up — narrator's 'common mistake' example.",
        b_roll_suggested:
          "Animated counter showing 'days RSI stayed above 70 in NIFTY 2024-25 rally' — to drive home the point",
      },
      {
        time_start: 150,
        time_end: 220,
        narration:
          "Teesra — MACD, Moving Average Convergence Divergence. Do EMAs ka difference plot karta — typically EMA 12 minus EMA 26. Signal line = MACD ka 9-period EMA. Buy signal: MACD line signal line ke upar cross kare. Histogram (bars) momentum ki speed dikhata. Trending markets mein bahut accha; chop mein false signals deta. Hamesha ADX filter ke saath use karein.",
        screen_action:
          "MACD panel below price. Three components labelled: MACD line (blue), signal line (orange), histogram (bars). Cross-up signal marked. Then a chop example where MACD whipsaws.",
        b_roll_suggested: "Side-by-side: trending market vs choppy market MACD behaviour",
      },
      {
        time_start: 220,
        time_end: 290,
        narration:
          "Chautha — Bollinger Bands. Ek middle band (20-bar SMA) ke saath upper aur lower bands jo 2 standard deviations door rehte. Use kaise: range markets mein lower band se buy, upper band se sell. Trending markets mein 'band walking' hota — price upper band ke saath chalti rehti. Range vs trend pehchanna pehli skill hai.",
        screen_action:
          "Bollinger Bands overlaid on NIFTY. First example: range-bound market with clean band-bounces. Second example: trend day with price 'walking' the upper band.",
        b_roll_suggested:
          "Animation showing standard deviation expanding/contracting with volatility",
      },
      {
        time_start: 290,
        time_end: 340,
        narration:
          "Paanchwa — Volume. Sirf number nahi, indicator hai. Volume spike (20-bar average ka 2x se zyada) + price direction = high-conviction move. Volume na ho aur breakout dikhe to wo fake breakout hai 60% baar. Indian retail aksar volume ignore karta — yahi 'why didn't my breakout work' ka jawab hai.",
        screen_action:
          "Chart with volume bars below price. One example: clean breakout with 3x volume — succeeds. Second example: breakout with average volume — fails next day.",
        b_roll_suggested: "Volume bars zooming in to show the 2x threshold visually",
      },
    ],
    outro:
      "Yahi paanch indicators 80% setups cover karte. Yad rakhein: koi bhi indicator akele nahi — hamesha 2-3 ka confluence chahiye. TradeTri pe 70+ indicators hain, har ek ka full audit log hai. Glass Box. Subscribe karein, agla tutorial backtest results samjhne pe hai.",
    total_word_count: 410,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. Today I'm walking you through the top 5 indicators — the ones that cover 80% of setups. This isn't a banking-school tutorial; this is what you'll actually use. Let's start.",
    sections: [
      {
        time_start: 11,
        time_end: 75,
        narration:
          "First — EMA, Exponential Moving Average. It weights recent prices more than older ones. Common pairs: EMA 9 and 21 for swing trades, EMA 20 and 50 for position trades. The trade rule is simple: smaller EMA above the larger one = uptrend, below = downtrend. That crossover is a classic entry signal.",
        screen_action:
          "NIFTY daily chart with EMA 9 (green) and EMA 21 (blue). Cross-up marked green, cross-down red.",
        b_roll_suggested:
          "Quick formula card: EMA weight decay over bars",
      },
      {
        time_start: 75,
        time_end: 145,
        narration:
          "Second — RSI, Relative Strength Index. Scale 0 to 100. Above 70 = lots of recent buying (overbought). Below 30 = lots of recent selling (oversold). Common mistake: 'overbought means short'. Wrong. In strong trends RSI stays above 70 for many days. RSI is one input, not a tip.",
        screen_action:
          "Chart with RSI panel below. Period 14. Zones shaded. Specific bars highlighted where RSI was 75 but price went higher.",
        b_roll_suggested:
          "Counter: 'days RSI stayed above 70 in NIFTY 2024-25 rally'",
      },
      {
        time_start: 145,
        time_end: 218,
        narration:
          "Third — MACD, Moving Average Convergence Divergence. Plots the difference between two EMAs — typically 12 minus 26. The signal line is a 9-period EMA of MACD. Buy signal: MACD line crosses above the signal line. The histogram shows momentum speed. Great in trending markets, false signals in chop. Always pair with an ADX filter.",
        screen_action:
          "MACD panel below price. Components labelled. Cross-up signal marked. Then a chop example where MACD whipsaws.",
        b_roll_suggested: "Side-by-side: trending vs choppy MACD behaviour",
      },
      {
        time_start: 218,
        time_end: 288,
        narration:
          "Fourth — Bollinger Bands. A middle band (20-bar SMA) with upper and lower bands 2 standard deviations away. How to use: in range markets, buy from the lower band, sell from the upper. In trending markets, price 'walks the band' — it stays glued to the upper band for many sessions. Telling range apart from trend is the first skill.",
        screen_action:
          "Bollinger Bands on NIFTY. First: range-bound with clean bounces. Second: trend day with band-walking.",
        b_roll_suggested: "Standard deviation expanding/contracting animation",
      },
      {
        time_start: 288,
        time_end: 338,
        narration:
          "Fifth — Volume. Not just a number, it's an indicator. A volume spike (more than 2x the 20-bar average) plus a directional close = high-conviction move. A breakout WITHOUT volume is a fake breakout 60% of the time. Indian retail often ignores volume — and that's the answer to 'why didn't my breakout work?'",
        screen_action:
          "Volume bars below price. Example 1: 3x volume breakout, succeeds. Example 2: average-volume breakout, fails.",
        b_roll_suggested: "Volume bars zooming to the 2x threshold line",
      },
    ],
    outro:
      "Those five cover 80% of setups. Remember: no indicator works alone — always look for confluence of 2-3. TradeTri has 70-plus indicators, each with a full audit log. Glass Box. Subscribe — next tutorial is interpreting backtest results.",
    total_word_count: 390,
  },

  thumbnail_text_options: [
    "Top 5 Indicators in 6 mins",
    "EMA, RSI, MACD, BB, Volume",
    "What you'll actually use",
  ],
  hashtags: [
    "#TechnicalAnalysis",
    "#Indicators",
    "#RSI",
    "#MACD",
    "#BollingerBands",
    "#TradeTri",
    "#IndianStockMarket",
  ],
  target_audience:
    "New traders who've heard the terms but haven't built intuition for indicators",
  prerequisites: ["TradeTri chart access (any free account)"],
};
