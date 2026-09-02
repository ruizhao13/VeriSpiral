# Public release checklist

Use this checklist before publishing VeriSpiral on GitHub.

## Identity and documentation

- [ ] Repository, package, CLI, badges, examples, and generated metadata use
      the final `VeriSpiral` / `verispiral` name consistently.
- [ ] No obsolete brand, organization-specific, or personal-role naming remains
      in public files or Git history.
- [ ] Human roles use the neutral terms `user`, `human reviewer`, and `project
      owner` where appropriate.
- [ ] README links work from a GitHub-rendered page.
- [ ] The self-evolution workflow distinguishes the target online loop from the
      deterministic transitions implemented today.
- [ ] Public docs state that the user owns the model, target, verifier contract,
      and scientific judgment boundary.
- [ ] Solution, model, and verifier changes are routed separately; a declared
      coupled model-and-verifier revision exposes both deltas.
- [ ] No statement implies that user feedback is scientific evidence, that the
      demo trains model weights, or that a replay discovers algorithms, proves
      theorems, personalizes a user model, or learns over time.
- [ ] Any comparison with related projects cites their current primary
      documentation and avoids unsupported superiority claims.

## Reproducibility and behavior

- [ ] `make test` passes from a clean checkout.
- [ ] `make demo` replays the registered executable verifier, reports the five
      documented stages, ends at `await_human_acceptance`, and tracks only the
      decision packet and manifest.
- [ ] The default demo reports `semantic_verification=verified` and
      `human_acceptance=pending`, and emits no success trace or Skill.
- [ ] `make evolution-demo` verifies its registered executable control source,
      manifest, component version, and hashes, then emits an unapplied patch for
      human review without modifying the target component.
- [ ] The feedback patch still reports `human_review_status=required`, all
      acceptance checks as `not_run`, and
      `no_scientific_conclusion_generated`.
- [ ] `make minimax-demo` produces `log_gap -> not_comparable ->
      minimax_rate_match` while preserving the original target branch.
- [ ] `make research-loop-demo` validates registered decision fixtures, accepts
      a verifier successor on the same target lineage, and isolates a model
      revision on a separate lineage.
- [ ] The research-specification replay binds a registered decision to the
      exact discussion and proposed-specification hash, supersedes only the old
      verifier record for a same-target successor, and gives no original-target
      credit to a changed model lineage.
- [ ] Research-specification fixtures cover model revision, verifier revision,
      and coupled model-and-verifier revision without mixing in solution deltas.
- [ ] `make golden-check` confirms all tracked demonstrations byte for
      byte.
- [ ] `make audit` reports no blocked path, large file, local absolute path, or
      credential-like pattern.
- [ ] Pass, rejection, assumption-mismatch, and certificate-conflict behavior
      remain covered by tests.
- [ ] README commands have been rerun after the final edit.

## Scientific and contribution boundaries

- [ ] Every case-study claim is scoped as a demonstration and links to its
      public evidence or limitation.
- [ ] The project owner has checked every minimax certificate extraction
      against its cited theorem locator; `registered_public_extract` has not
      been mistaken for proof verification.
- [ ] The final minimax trace still states `human_review_required=true` and
      does not authorize a manuscript-facing theorem claim.
- [ ] No public document claims that the default fixture produces a success
      trace or Skill.
- [ ] A passed executable receipt is described only within its registered scope
      and never as human acceptance or general scientific validation.
- [ ] `minimax_rate_match` is described only as compatible registered fields
      with matching stored exponents, not as theorem verification.
- [ ] A checked-in `actor: human` decision is not presented as live input or
      proof of the decision-maker's identity.
- [ ] `MODEL_AND_HUMAN_CONTRIBUTIONS.md` matches the actual contribution
      history and has been reviewed by the project owner.
- [ ] Third-party sources and dependencies have appropriate attribution and
      compatible licenses.

## Data and repository hygiene

- [ ] The repository contains no private source corpus, interaction history,
      preference or reward ledger, unpublished manuscript, collaborator data,
      credential, or machine-specific path.
- [ ] Generated outputs and caches are either intentionally tracked reference
      artifacts or excluded by `.gitignore`.
- [ ] The staged diff—not only the working tree—has been reviewed for private
      data, embedded metadata, large files, and unintended changes.
- [ ] The final repository size and largest-file report are recorded.
- [ ] The public repository is opened in a logged-out browser and the clone,
      install, demo, test, and audit instructions are verified from a clean
      directory.
- [ ] No remote is added and nothing is pushed until the project owner gives
      explicit approval for publication.
