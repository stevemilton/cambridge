# risk_management

## Goal
Enforce hard risk limits without negotiation. This is the kill switch: it runs in
its own parallel sub-loop and overrides every other stage.

## Rules
- Flatten all positions if aggregate drawdown exceeds 5 percent
- The position-size cap is also enforced at the broker, not just at the agent
- On any breach, write the incident back to the alpha_research skill as a lesson

## Notes
- The risk monitor's stop conditions are measured numbers (drawdown, exposure),
  never an agent's assertion that "everything looks fine".
