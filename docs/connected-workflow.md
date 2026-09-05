# 从问题文档到执行、修复和重检

`make workflow-demo` 接通一条有明确范围的工作流：读取问题文档和图数据，形成规格
提案，读取与提案绑定的接受记录，再运行候选方法、检查、并发失败诊断和修复。
需要更换检查器时先停下；接受修订后，在同一目标上建立新版本并重新检查保留的候选。

实现见[工作流控制器](../src/verispiral/research_workflow.py)和
[最短路径适配器](../src/verispiral/path_adapter.py)。
[公开摘要](../examples/expected/workflow/demo_summary.json)、
[首轮完整报告](../examples/expected/workflow/initial_run/workflow_report.json)、
[后继版本报告](../examples/expected/workflow/successor_run/workflow_report.json)及
[工作流测试](../tests/test_research_workflow.py)支持下述软件行为。
演示里的接受记录标为 `synthetic_fixture`，不代表现场人工批准或科学结论。

## 当前入口与支持范围

输入包含一份非空 UTF-8 `.md` 或 `.txt` 问题文档，以及显式的图数据：

```json
{
  "node_count": 4,
  "edges": [[0, 1, 1], [1, 3, 9], [0, 2, 2], [2, 3, 1]]
}
```

目前只支持 2 至 12 个节点、按编号递增连接的有向无环图，权重为整数，可为负数；
不支持重边，并要求每个节点都能从节点 0 到达。适配器提出的目标是从 0 到最后一个
节点的最小权重路径。用户必须核对这个目标与输入文档是否一致。

程序记录原文的来源、哈希及待确认问题，**没有实现任意自然语言到科研规格的语义
提取**。缺少图数据或超出适配器范围时，提案标记为 `needs_input`，不能执行。
公开演示所用的[问题文档](../examples/workflow/problem.md)和
[图数据](../examples/workflow/setup.json)均为专门编写的小型 fixture。

## 使用自己的决策记录

从仓库根目录运行下面的命令可生成提案与 `decision_template.json`：

```bash
PYTHONPATH=src python3 -B -m verispiral workflow-prepare \
  --problem examples/workflow/problem.md \
  --setup examples/workflow/setup.json \
  --output demo/output/my-workflow/proposal
```

检查提案中的目标、图模型、方法与检查器选项，再将模板另存为 `decision.json`。
决定采用时把 `action` 从 `pending` 改为 `accept`，保留匹配的 `proposal_sha256`，
并选择预算、轮数、初始方法与筛查器。`reject` 会记录拒绝并停止，不运行候选。
文件中的 `user_record` 表示调用者提供的决策记录；程序不能认证决策者身份。

```bash
PYTHONPATH=src python3 -B -m verispiral workflow-run \
  --proposal demo/output/my-workflow/proposal/proposal.json \
  --decision demo/output/my-workflow/proposal/decision.json \
  --output demo/output/my-workflow/run
```

命令不会自动接受模板。输入文档、图数据、提案或执行实现发生变化后，旧决策不能
继续使用，必须重新准备和核对提案。不同内容也不能覆盖已有运行目录；请使用新目录。
只有 Makefile 中固定公开 fixture 的演示和参考产物更新会先在临时目录成功生成，
再替换对应生成目录，以便开发时重复验证。

私人问题的输入和输出都应放在公开仓库之外。运行器拒绝把来自
`examples/workflow/` 之外的输入写回公开仓库；原文不会复制到报告，但报告会包含
结构化图数据、候选与检查结果，因此仍应留在对应私人工作区。

## 一个失败如何推动下一步

公开图上，贪心方法先选路径 `0 → 1 → 3`，成本为 10；穷举参考找到
`0 → 2 → 3`，成本为 3。仅检查路径上边的弱检查器却接受前者。
这组结果同时支持三个有限指示：

| 失败指示 | 实际检查 | 后续工作 |
| --- | --- | --- |
| `candidate_not_optimal` | 提交路径的成本高于穷举参考 | 用已登记的精确方法重新求解 |
| `certificate_invalid` | 证书没有通过完整查边规则 | 修复候选或单独补证书 |
| `screen_disagreement` | 当前筛查判断与参考最优性判断不同 | 保留问题并提出检查器修订 |

还有一项 `candidate_infeasible` 检查路径是否有效。本例该项通过。控制器不会看到
第一个失败就结束诊断：四项登记检查全部完成后才报告覆盖完成；预算不足则明确
列出未检查项，同时保留已观察的失败。多个指示可以有共同原因或相互影响，不能把
这张表解释为三个已经独立识别的根因。

候选修复使用已写好的方法，不生成新算法。修复完成后重新执行全部四项检查，并把
每份结果绑定到当前候选内容与规格的哈希；不会把之前的通过项直接搬过来。如果路径
已经最优而只是证书缺失，则保留路径、补证书，并计入完整证书生产成本。

一旦本轮运行暴露弱检查器漏判，即使后来的候选通过全部检查，历史问题仍留在报告，
运行也会停在 `awaiting_verifier_decision`，输出 `revision_proposal.json`。
接受后继提案必须选用 `all_edges_certificate`；它只改变筛查器，目标和图模型保持
原样。再次执行 `workflow-run` 时使用这份修订提案、与其哈希匹配的新决策及新目录。
后继版本保留候选，但旧证据不再适用，四项检查重新付费、重新执行。

完整演示通过两轮候选检查和一次检查器继任，最终停在
`candidate_ready_for_human_acceptance`。这只表示当前有限检查全部通过；
`human_acceptance` 仍为 `pending`，`scientific_claim_accepted` 仍为 `false`。

## 预算与停止边界

每项操作先检查其保守费用上界是否可负担，再执行并按实际计数扣费。
预算计入声明的边操作：图扫描、邻接表构造、求解、证书生产、路径评分、穷举与
检查；不计解析、文件读写、节点操作、控制器时间，也不等于真实总运行费用。
没有足够预算时宁可停止，不能偷读未支付的参考评价后再选择检查。

报告会区分预算耗尽、轮数耗尽、等待检查器决策、未能确定下一步及等待候选人工接受。
若候选修复完成前已耗尽预算或轮数，发现的检查器问题仍保留，但本次运行不会生成
修订提案。后继版本预算不足也不会把保留候选标为已通过。

这个闭环证明的是一个小型适配器上的连接、费用记录和证据失效机制。全部例子公开，
求解器与参考实现虽分开编写仍共享模型设计；它没有隐藏测试、任意领域迁移、自动
Goal/Setup 发明或一般验证器合成，也没有证明比直接求解更省成本。成本负结果见
[最短路径试验](path-workflow-study.md)；更广的课题仍需按
[研究议程](research-agenda.md)进行独立问题和等预算对照。
