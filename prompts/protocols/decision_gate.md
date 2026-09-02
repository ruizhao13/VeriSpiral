# Protocol: Decision Gate

Before a candidate can advance, produce a compact packet containing:

1. claim and scope;
2. assumptions with classification;
3. proof or implementation route;
4. closest literature comparison;
5. positive evidence and counterevidence;
6. main failure mode;
7. structural, evidence-integrity, semantic-verification, human-acceptance,
   and lifecycle statuses, kept separate;
8. exact question for human judgment.

Allowed decisions are `pursue`, `revise`, `reject`, and `ask_human`. Missing
evidence defaults to `revise` or `ask_human`, never silent promotion.
