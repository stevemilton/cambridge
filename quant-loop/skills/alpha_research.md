# alpha_research

## Goal
Generate signals using linear regression on the last 30 days of price and volume
data. Fit on the training window only; hand the held-out window to the verifier.

## Rules
- Position size limited to 2 percent of capital per signal
- Sharpe ratio must be above 1.5 in 3 of the last 5 backtests
- Skip signals on FOMC announcement days
- Skip signals 48 hours before earnings releases
- Cap sector exposure at 30 percent

## Lessons learned
- 2026-02-14: Lost 4.2 percent during earnings week.
  New rule: skip any signal 48 hours before earnings.
- 2026-03-08: Sector exposure breach caused 6 percent drawdown.
  New rule: cap sector exposure at 30 percent.
- 2026-04-22: Momentum signal blew up on FOMC day.
  New rule: kill all momentum signals on FOMC days.
