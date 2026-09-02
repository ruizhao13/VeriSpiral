---
name: skill-induction
description: Turn a validated recurring research workflow into a concise reusable skill with explicit triggers, failure modes, and checks.
---

# Skill Induction

## Trigger

Use only after a workflow succeeds under an external verifier or explicit human
acceptance and is likely to recur.

## Workflow

1. Name the recurring task rather than the source project.
2. Identify the trace, success signal, and failure modes.
3. Write a concise trigger, inputs, workflow, outputs, and validation section.
4. Add deterministic scripts only when they reduce repeated error.
5. Replay the skill against the originating trace.

## Validation

- The skill would have improved the original run.
- At least one known failure mode is prevented.
- The skill does not encode private or project-specific state.
