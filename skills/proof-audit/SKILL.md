---
name: proof-audit
description: Audit a theorem or proof route for missing lemmas, hidden assumptions, conditioning errors, invalid norm transfers, and silent oracle information.
---

# Proof Audit

## Trigger

Use before a theorem-shaped claim enters a decision packet or manuscript.

## Workflow

1. Restate the claim, quantifiers, loss, and probability mode.
2. Draw the dependency chain and find the first unsupported edge.
3. Classify assumptions as cited, structural, repairable, or scope-changing.
4. Check adaptivity, selection dependence, normalization, and oracle access.
5. Test the route against a minimal counterexample or executable diagnostic.
6. Return the smallest repair or reject the route.

## Validation

- Every gap points to a specific proof edge.
- Diagnostics are not described as proofs.
- The repaired claim retains all necessary qualifiers.
