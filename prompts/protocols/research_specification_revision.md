# Protocol: Research-specification revision discussion

Use this protocol only when solution search reveals a possible defect or
scientifically meaningful alternative in the accepted model, target,
assumptions, verifier suite, or human-judgment boundary.

Freeze the current specification. Do not apply a proposed change. Return:

1. the current specification ID, version, branch, and content hash;
2. the exact diagnosis, counterexample, or user insight that triggered review;
3. one declared revision class: `model_revision`, `verifier_revision`, or an
   explicitly coupled revision whose two deltas are shown separately;
4. a field-level proposed delta;
5. expected benefit, scientific cost, new assumptions, and invalidated results;
6. whether the scientific problem is preserved or changed;
7. checks that must be rerun under the proposed specification;
8. a minimal user question with `accept`, `reject`, `modify`, and `branch`
   available where applicable; and
9. the continuation code that the next research round must consume.

An accepted verifier revision creates an immutable successor and invalidates
automatic carry-over of affected passes. A model or target change creates a
separate problem branch and never receives progress credit for its parent.
AI output remains a proposal until the user records a decision.
