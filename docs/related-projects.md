# Related projects and positioning

VeriSpiral sits between end-to-end research agents, self-evolving agent
frameworks, and formal theorem provers. The comparison below uses the projects'
official repositories and papers. It describes differences in scope, not a
benchmark ranking: these systems solve different problems and have not been
evaluated under a shared protocol.

## Automated scientific workflows

| Project | Official scope | Overlap with VeriSpiral | VeriSpiral's focus | What VeriSpiral cannot claim |
| --- | --- | --- | --- | --- |
| [The AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) ([paper](https://arxiv.org/abs/2504.08066)) | Generates hypotheses, runs experiments, analyzes results, and writes manuscripts using an agentic tree search. | Both expose an iterative research process and retain intermediate state. | VeriSpiral is a smaller control-layer reference: it records evidence and verifier decisions, and prevents an assumption change from silently redefining the target problem. | It does not implement comparable autonomous discovery, paper generation, or experimental search, and it has no basis for claiming better research quality. |
| [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory) ([paper](https://aclanthology.org/2025.findings-emnlp.320/)) | Takes a human-provided idea through literature review, experimentation, and report writing, with human feedback available at each stage. | Both reserve an explicit role for human input in a research workflow. | VeriSpiral's feedback-path design treats feedback as scoped input to a reviewable evolution patch. Preference feedback does not become scientific evidence, and a material patch remains subject to provenance checks, human review, regression tests, and rollback. | It is not currently an end-to-end research assistant and should not imply that its feedback workflow has been compared with Agent Laboratory. |
| [PaperQA2](https://github.com/Future-House/paper-qa) ([paper](https://arxiv.org/abs/2409.13740)) | Provides agentic retrieval-augmented generation over scientific documents, including iterative search, cited answers, summarization, and contradiction detection. | Both make source provenance visible and try to keep scientific outputs tied to evidence. | VeriSpiral operates after a source extract has been registered. Its public theory demo checks whether upper- and lower-bound certificates describe the same problem before comparing their rate exponents. | It does not retrieve papers, establish literature coverage, validate a source extraction, or perform novelty checking. |
| [Mr Dre](https://aclanthology.org/2026.acl-long.609/) | Studies multi-turn revision of deep-research reports and measures regressions in content and citation quality after feedback. | Both treat a local improvement request as capable of damaging previously accepted work. | VeriSpiral turns this concern into specification and policy boundaries: a verifier change is versioned, affected results must be replayed, and model changes cannot be hidden inside solution edits. | It has not reproduced Mr Dre's multi-agent evaluation and reports no measured reduction in revision regression. |

## Self-evolving agent systems

| Project | Official scope | Overlap with VeriSpiral | VeriSpiral's focus | What VeriSpiral cannot claim |
| --- | --- | --- | --- | --- |
| [EvoAgentX](https://github.com/ANative-Lab/EvoAgentX) ([paper](https://aclanthology.org/2025.emnlp-demos.47/)) | Builds, evaluates, and evolves LLM-agent workflows; its evolution layer integrates methods such as TextGrad, AFlow, and MIPRO to optimize prompts, tools, and workflow topology. | Both treat prompts and workflows as external state that can change without updating model weights. | VeriSpiral emphasizes what evidence authorizes a change: feedback is scoped, high-stakes patches require human approval, and scientific assumptions are versioned problem state rather than optimization knobs. | It does not provide EvoAgentX's general workflow-construction or optimization engine, and it reports no comparable benchmark improvement. |
| [FlowEvo](https://github.com/DEFENSE-SEU/FlowEvo) ([paper](https://openreview.net/forum?id=hU2N7IIkcE)) | Compiles successful traces into directly executable skills, routes later tasks among skill replay and dynamic planning, and uses governance checks to suppress negative transfer. | Both are concerned with the evidence boundary before a reusable capability is admitted. | VeriSpiral's tracked candidate fixture stops earlier: it replays a registered executable verifier but leaves human acceptance pending, so no success trace or Skill is emitted. It also adds a user-governed research-specification control problem. | The public demo does not demonstrate Trace-to-Skill compilation, an activatable Skill, or FlowEvo's adaptive runtime routing. |
| [Ratchet](https://github.com/amazon-science/Self-Evolving-Agents-Ratchet) ([paper](https://arxiv.org/abs/2605.22148)) | Turns clustered failures into a governed library of natural-language skills for a frozen model, measures their contribution, and retires skills that stop helping while retaining evidence for rollback. | Both treat reusable procedures as governed artifacts whose evidence and rollback boundary matter. | VeriSpiral separates user feedback, executable-verifier evidence, and human acceptance; its default fixture stops before any Skill is emitted. | It does not currently implement Ratchet's repeated skill-synthesis loop, contribution scoring, activatable Skill output, or benchmarked improvement over rounds. |
| [RethinkSkill](https://github.com/HKUST-KnowComp/rethinkskill) ([paper](https://arxiv.org/abs/2608.02636)) | Evolves skills through repeated feedback and validation, then distinguishes validation, released-test, robustness, and transfer outcomes. | Both require evidence before an external capability is retained and both separate proposal generation from admission. | VeriSpiral focuses on user authority over the scientific model and verifier, including same-target verifier succession and separate model lineages. | It does not implement RethinkSkill's model-driven candidate generation, repeated feedback runs, selection loop, or held-out empirical evaluation. |
| [SEA-Eval](https://arxiv.org/abs/2604.08988) | Evaluates self-evolving agents on sequential task streams using evolutionary gain and stability rather than isolated task success. | Both reject a single successful episode as sufficient evidence of durable evolution. | VeriSpiral provides control-plane provenance and branch semantics that could be evaluated under a longitudinal protocol. | The current repository is a deterministic five-round replay, not a longitudinal agent evaluation, and reports no evolutionary gain. |

## Formal proof and verification boundary

| Project | Official scope | Overlap with VeriSpiral | VeriSpiral's focus | What VeriSpiral cannot claim |
| --- | --- | --- | --- | --- |
| [LeanDojo-v2](https://github.com/lean-dojo/LeanDojo-v2) ([original LeanDojo paper](https://arxiv.org/abs/2306.15626)) | Trains, evaluates, and deploys AI-assisted Lean 4 theorem provers, using Lean proof states and a proof-assistant runtime to check candidate proofs. | Both place a checking layer downstream of generated or registered mathematical content. | VeriSpiral's public minimax path is a certificate-field compatibility checker: it compares declared scope, assumptions, and exact rate exponents before issuing a bounded machine status. This is research bookkeeping rather than proof checking. | It is not a formal verifier or theorem prover. It does not check proof steps, re-prove cited theorems, infer class containment, or validate unregistered constants and lower-order terms. |

## The defensible distinction

VeriSpiral does not introduce evidence gates, reusable-Skill designs, human
feedback, workflow evolution, or mathematical verification individually. All
have clear precedents above. Its narrower focus is a research-specification
control problem:

1. How can verifier results guide the next research iteration without allowing
   a stronger assumption to masquerade as progress on the original problem?
2. How can AI help diagnose and propose changes to a scientific model or
   verifier while leaving acceptance, modification, rejection, and branching
   authority with the user?
3. How can an accepted verifier revision continue the same target without
   inheriting earlier false passes, while a model change is isolated on a
   separate target lineage?

The design addresses these questions with typed artifacts, immutable assumption
branches, provenance-linked decisions, executable receipt replay, bounded
evolution patches, human review boundaries, regression checks, and rollback
records. The default candidate fixture stops before trace or Skill emission. In the included bandit
replay, the candidate sequence is pre-registered and the verifier does not
generate the next algorithm. The feedback-to-patch workflow must likewise be
described according to the transitions that are executable in the current
release.

This supports a narrow positioning: **a user-governed control layer for
research-specification co-evolution and solution search**. It does not
support claims that VeriSpiral is the first or only self-evolving research
agent, that it autonomously discovers algorithms, or that it is more reliable
than the systems above.
