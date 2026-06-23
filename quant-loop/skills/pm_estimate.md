# pm_estimate

## Goal
Estimate the true probability that a prediction-market event resolves YES, then
trade only the *gap* between that estimate and the market price. The edge is your
estimate being better-calibrated than the crowd — not following the price.

## Rules
- Position size limited to 2 percent of capital per market
- Only trade when your estimate beats the market price by at least the margin (5 percent)
- Buy YES when your probability is well above the market price; buy NO when well below
- Stay flat when your estimate is close to the price — no edge, no trade
- Never stake more than the position cap on a single market

## Lessons learned
- (resolution outcomes get written back here by the risk monitor)
