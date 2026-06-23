# pm_verification

## Goal
Grade the maker's probability estimates against *resolved* markets — the ground
truth. Trust today's signals only if the maker has been well-calibrated and is
beating the market price on settled events. Never trust the maker's own claim.

## Rules
- Brier score must be below 0.24 (better than the 0.25 always-50/50 baseline)
- The maker's Brier must beat the market price's Brier on the same resolved set
- Require a minimum sample of resolved markets before passing (sparse history = no trades)

## Notes
- This skill is graded by a *different* agent from the maker — ideally a stronger
  model. It sees only the (estimate, outcome, market_price) triples, never how
  the maker reasoned.
- Resolution is unambiguous, so a failing maker is killed for the cycle, not
  given "one more try".
