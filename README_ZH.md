# VeriSpiral

**用多保真证据与失败诊断，共同设计 Goal、Setup、Verifier 和 Algorithm 的科研工作流。**

核心问题是：一个候选在更可靠的检验中失败后，下一笔预算该花在哪里？继续改算法，
构造更好的验证器，补上模型遗漏，还是重新讨论目标？VeriSpiral 将“如何巧妙构造
可负担的验证器”和“如何用区分性实验定位失败层次”作为研究主线。

```mermaid
flowchart LR
    R[实际问题与原始要求] --> GS[Goal 与 Setup 候选]
    GS --> V[Verifier 构造与成本比较]
    V --> F[用户确认并冻结规格]
    F --> A[算法搜索与廉价检查]
    A --> H[高保真晋级检验]
    H --> D[竞争解释与区分性实验]
    D -->|算法或实现问题| A
    D -->|规格问题：提交用户决定| GS
```

第一层把现实诉求变成可研究的问题；第二层把昂贵目标评估变成可重复调用的检查。
两层都可能丢失重要信息，因此要检查被选出的算法是否迁移，并计算验证器的建造、
调用与重检成本。用户决策、版本控制和证据约束为这条研究主线提供保障。

从[研究议程](docs/research-agenda.md)了解假设、对照、指标和停止判据；
从[问题编译协议](prompts/protocols/problem_compilation.md)开始处理一段问题描述或文档。
通用协议需要配合领域工具与可信参考评价，不能靠一条长提示词替代它们。

VeriSpiral 把科研过程分成两个循环。内循环在冻结的科研规格下进行：AI 可以检索
文献、生成候选解、设计证明路线、寻找反例和设计实验。外循环处理科研规格本身：
AI 可以准备 model revision 或 verifier revision 的讨论包，但只有用户可以对它
执行 `accept`、`reject`、`modify` 或 `branch`。

用户掌握最终采用的科学模型、target、verifier 契约和科学判断边界。“协同演化”
表示证据与用户决策可以形成一个显式版本化的新规格；它不表示自动个性化、长期
学习或系统静默修改自己。

当前仓库有七条小型、确定性演示。[接通后的工作流](docs/connected-workflow.md)在显式
小型图适配器上执行文档接入、规格决策、求解、并发检查、修复与检查器继任；任意自然
语言理解和上述通用科研循环仍未实现。
最新的[最短路径问题验证](docs/path-workflow-study.md)实际运行候选算法、独立路径评分
和证书检查，并根据首次观察追加了补证书修复，保留了“没有证明加速”的负结果。

## 60 秒了解项目

| 问题 | 回答 |
| --- | --- |
| 它研究什么问题？ | 如何共同设计问题、验证器和算法，并在预算内区分失败原因，选择下一项实验或修订。 |
| 用户掌握什么？ | 最终采用的模型、target、verifier，以及科学解释的边界。 |
| AI 可以负责什么？ | 目标与建模选项、验证器构造、候选解、反例、区分性实验与修订提案。这是目标分工，不是当前 demo 已实现的完整能力。 |
| 最重要的分离是什么？ | 内循环 solution search 与外循环 research-specification revision 分开。solution delta 不能和 model/verifier delta 共用 patch；联动修订也必须分别展示两部分。 |
| 当前能运行什么？ | 接通的小型图工作流、最短路径与补证书试验、并发故障检查，以及候选审查、未应用补丁、bandit 证书比较、科研规格继任与分支。 |

## 两个循环，一条权限边界

```mermaid
flowchart TD
    U[用户确认的 model + target + verifier] --> F[冻结 ResearchSpecification vN]

    subgraph Inner[内循环：solution search]
        F --> L[AI 文献工作]
        L --> C[AI 候选解]
        C --> P[证明路线与反例]
        C --> E[实验]
        P --> G[运行用户接受的检查]
        E --> G
        G --> R[通过声明的检查 / 失败 / 不确定]
        R -->|solution change| C
    end

    R -->|model 或 target 问题| M[Model-revision discussion packet]
    R -->|verifier 问题| V[Verifier-revision discussion packet]
    M --> D[用户决策]
    V --> D
    D -->|reject| F
    D -->|modify| M
    D -->|accept| N[新规格版本]
    D -->|branch| B[独立规格分支]
    N --> F
    B --> F
```

AI 可以暴露不匹配并起草边界明确的修改建议，但不能决定“修改后的问题与原问题足够
接近”、为了挽救某个解而削弱 verifier，也不能批准修改。公开 runner 可以把仓库内
预登记的决策 fixture 应用为版本化分支，但这不等于现场用户批准。完整契约见
[科研规格协同演化](docs/research-specification-coevolution.md)。

## 严格分开三类变化

| 变化 | 例子 | 规则 |
| --- | --- | --- |
| Solution | 候选算法、不改变既定定理 target 的辅助引理或证明主张、证明路线、反例、实验 | model、target 和 verifier 保持冻结 |
| Model | 观测模型、假设、参数类、损失、target、基线类、成功条件 | 建立独立 target lineage；不能算作解决了原问题 |
| Verifier | 检查逻辑、可接受证据、阈值、fixture、证书接口、解释规则 | 重新检查受影响结果；不能同时修改 model 或 target |

如果 model 与 verifier 必须联动调整，复合讨论包也必须把两部分 delta 及影响分开
展示。它仍然是规格修订，只有用户能决定 `accept`、`reject`、`modify` 或 `branch`。

## 当前可执行的部分

### 1. 五阶段候选审查

```mermaid
flowchart LR
    C[合成候选] --> S[结构验证]
    E[仓库内证据] --> I[证据完整性]
    S --> V[回放已登记可执行 verifier]
    I --> V
    V --> H[人工接受：pending]
    H --> D[await_human_acceptance 决策包]
    D --> N[不产生 success trace；不产生 Skill]
```

五个状态分别是 `structural_validation`、`evidence_integrity`、
`semantic_verification`、`human_acceptance` 和 `candidate_lifecycle`。默认 fixture
会真实回放已登记的可执行 verifier，并把 receipt 与完整 semantic subject 绑定。
五项状态为 `pass / pass / verified / pending / ready_for_verification`，所以最终决策
是 `await_human_acceptance`。

tracked manifest 只包含 decision packet。由于没有人工 acceptance record，本次运行
不会生成 `success_trace.json`，也不会生成 induced Skill。receipt 通过只说明已登记
verifier 在声明范围内通过，不能代替人工接受或一般性的科学验证。

### 2. 合成反馈到未应用的流程补丁

```mermaid
flowchart LR
    F[合成 FeedbackEvent] --> G[Schema、来源、版本与哈希检查]
    C[已登记可执行控制来源] --> G
    G --> P[一项 process-only 提案]
    P --> H[proposed_for_human_review]
    H --> N[apply_status: not_applied]
```

仓库内事件只请求增加一条流程说明。来源必须绑定到已登记、可执行的控制证据，不能
依赖自我声明的成功。运行器生成未应用补丁后停止。这不是 model revision packet、
verifier revision packet、已记录的人工决策或自动演化。

相关输入与输出：

- [反馈事件](examples/evolution/feedback_event.json)
- [来源与组件 registry](examples/evolution/registry.json)
- [受约束提案](examples/expected/evolution/evolution_proposal.json)
- [未应用补丁](examples/expected/evolution/evolution_patch.json)
- [产物清单](examples/expected/evolution/manifest.json)

### 3. Bandit 证书兼容性回放

```mermaid
flowchart LR
    T[已登记 target 接口] --> C[证书兼容性检查器]
    L[已登记下界证书字段] --> C
    U[预先登记的上界证书字段] --> C
    C -->|scope 对齐| A[精确指数比较]
    C -->|假设不匹配| Q[提交用户判断的分支建议]
```

CLI 命令名是 `minimax`，但运行器不是定理验证器。它比较仓库内登记的问题签名
字符串、假设和有理数速率指数。三个候选在运行前就已登记；代码不会生成算法，也
不会验证论文证明或证书摘录的正确性。产物中的假设分支只是 demo 状态，不表示用户
接受了新的科学模型。

固定回放输出：

```text
UCB-like：       log_gap
MOSS：           在 unknown-horizon target 上 not_comparable
MOSS-anytime：   回到原始 target 并得到 minimax_rate_match
```

这里的 `minimax_rate_match` 是很窄的机器状态：兼容的登记接口具有相同的已存指数。
它不是证明，也不是获准公开的 minimax 结论。详见
[证书兼容性说明](docs/minimax-verifier.md)。

### 4. 科研规格协同演化回放

这条路径验证已登记的规格文件及哈希、AI 起草的修订讨论，以及仓库内预登记的人工
决策事件。被接受的 verifier-only 修订会成为同一 target lineage 上的不可变继任
版本，替代旧 verifier 并供后续 round 使用；model change 则建立独立 target lineage，
不能把结果计入原 target。

fixture 支持 model revision、verifier revision，以及把两部分 delta 明确分开的
`model_and_verifier_revision`；联动修订遵循独立 model branch 规则。它演示的是决策
绑定、verifier 继任、model lineage 隔离，以及依据登记 scenario 重算事件来源。
人工决策不能偷换 AI discussion 的 revision 类型；如果想从 model revision 改成
verifier revision，必须重新形成提案与讨论。它不会采集现场用户输入，不能证明
记录中的 actor 是真实的人，也不会生成算法、证明或确立科学结论。

### 5. 有限故障诊断与验证器比较

`make diagnosis-demo` 在十个公开有限表例子上执行七项登记检查，包含无故障对照和
两个并发失败例子。控制器按费用顺序选择可负担的待检项，只读取已支付的检查结果；
全部登记检查完成后才报告覆盖完成，预算不足时同时保留已发现失败和未检查项。
故障标签只在结束后用于核对，所有修订仍只是建议。

同一演示比较只检查前两个情境的廉价筛查与检查全部四个情境的精确评价，展示代理
评分选中的候选如何在完整评价中失去优势。它还列出建造成本与调用成本的摊销。
这些是人为构造的有限表、检查和成本，不是独立测试集或真实因果诊断效果；详见
[诊断演示及边界](docs/diagnosis-demo.md)。

### 6. 从实际执行的问题返回项目修复

`make path-trial` 在 26 张公开小图上运行两个候选方法，比较三种检查方式。
完整查边消除了弱检查的误接受，却留下证书不完整的最优结果；追加修复保持候选
路径不变，补全证书并计入其生产成本。完整数值、直接求解对照和边界见
[问题验证报告](docs/path-workflow-study.md)。这不执行模型调用或自主科研。

### 7. 从问题文档接到修复和版本重检

`make workflow-demo` 读取公开问题文档和显式图数据，形成规格提案后读取匹配的决策。
演示同时发现候选不最优、证书无效和筛查不一致，修复候选后重新执行全部四项检查。
暴露过弱筛查器问题就提出修订；接受后在同一目标上建立后继版本，保留候选但重新
付费检查。演示决策为合成记录，最终候选仍待人工接受。
[入口与范围说明](docs/connected-workflow.md)给出真实决策文件的用法、预算及暂停
规则；程序没有自动理解任意自然语言问题的能力。

## 运行演示

需要 Python 3.10 或更新版本，以及 `make`。不需要 API Key 或网络连接。

```bash
make demo
make evolution-demo
make minimax-demo
make research-loop-demo
make diagnosis-demo
make path-trial
make workflow-demo
make test
make golden-check
make audit
```

生成文件写入 `demo/output/`，不会进入 Git；参考产物位于 `examples/expected/`。
Golden test 只能说明合成 fixture 可逐字节复现，不能说明科学正确性。

## 仓库地图

- [接通的工作流](docs/connected-workflow.md)：文档入口、明确决策、并发检查、修复与继任重检；
- [问题验证与两轮修复](docs/path-workflow-study.md)：最短路径、证书覆盖和成本负结果；
- [问题驱动迭代协议](prompts/protocols/problem_driven_iteration.md)：固定比较、观察、修复与重检；
- [研究议程](docs/research-agenda.md)：共同设计、可证伪假设、等预算对照与迁移指标；
- [问题编译协议](prompts/protocols/problem_compilation.md)：从段落或文档进入工作流；
- [有限诊断演示](docs/diagnosis-demo.md)：故障区分、预算、代理失真与证据边界；
- [科研规格协同演化](docs/research-specification-coevolution.md)：用户与 AI 分工、
  内外循环、变化类型和决策语义；
- [架构](docs/architecture.md)：系统边界以及概念设计与公开 demo 的对应关系；
- [变化控制工作流](docs/self-evolution-workflow.md)：已实现反馈路径及停止边界；
- [项目简述](PROJECT_BRIEF.md)：精简范围与声明；
- [设计原则](docs/design-principles.md)：系统约束；
- [审阅指南](docs/reviewer-guide.md)：快速检查路径；
- [证书兼容性说明](docs/minimax-verifier.md)：bandit 回放语义与来源；
- [声明—证据矩阵](docs/claim-evidence-matrix.md)：可执行声明及边界；
- [同类项目](docs/related-projects.md)：有来源的范围比较；
- [`src/verispiral/`](src/verispiral/)：确定性编排与验证代码；
- [`schemas/`](schemas/)、[`examples/`](examples/) 和 [`tests/`](tests/)：契约、
  fixture 与可执行检查。

## 当前边界

- 仓库不调用 LLM，也不检索文献。
- 仓库会执行和切换已写好的图算法，不会发明算法、定理、证明或通用科研实验。
- 仓库可以验证已登记的讨论与人工决策 fixture，在同一 target lineage 上继续使用
  已接受 verifier successor，并把改变后的 model 隔离到独立 lineage；它不采集现场
  决策。接通的图工作流另可读取调用者提供的决策文件，两种路径均不能证明决策者身份。
- 仓库不会自动批准 model/verifier 变化，不会应用流程反馈补丁或执行回滚，也不会
  个性化系统、维护用户模型或长期学习。
- 结构验证和哈希不能证明证据内容正确。
- 证书回放不能证明定理、验证来源摘录、确认新颖性或批准科学结论。
- 默认候选 demo 停在人工接受待定状态，不生成 success trace 或 Skill。

公开边界见 [DATA_AND_PRIVACY.md](DATA_AND_PRIVACY.md)，许可证见
[LICENSE](LICENSE)，发布前检查见
[PUBLIC_RELEASE_CHECKLIST.md](PUBLIC_RELEASE_CHECKLIST.md)。

English documentation: [README.md](README.md)
