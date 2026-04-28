# r1-v2 Review Memo

这份 memo 只讨论大方向，不展开工程细节实现。

评审依据：

- [r1-v1.md](./r1-v1.md)
- [r1-v2-preview.md](./r1-v2-preview.md)
- [graphify-batch/raw/global-navigation/navigation_summary.json](./graphify-batch/raw/global-navigation/navigation_summary.json)
- [graphify-batch/raw/global-navigation/engineering_efficiency_matches.md](./graphify-batch/raw/global-navigation/engineering_efficiency_matches.md)
- [graphify-batch/raw/global-navigation/grpo_sorted_by_stars_live.json](./graphify-batch/raw/global-navigation/grpo_sorted_by_stars_live.json)

## 一、总体判断

`v2` 的大方向是合理的，而且明显比 `v1` 更接近真实可落地的企业方案。

核心原因有三点：

- 从“保险垂类 Search-R1 复刻”转向了“企业内网 Agentic Search 基线”，目标更稳、更宽，也更适合本地部署
- 从“先追 RL 技术炫技”转向了“先把数据、工具协议、离线环境和评测闭环做稳”，这更符合企业项目的成功路径
- 从“只追求答对”转向了“证据闭环、拒答边界、预算内最优”，这更符合真实业务要求

但 `v2-preview` 当前还有一个明显问题：

- 它更像 `v2 + v2.5 + v3` 的合体，而不是一个边界清晰的版本

换句话说，不需要推翻方向，但需要收缩版本范围。

## 二、我建议如何定义 v2

一句话定义：

`v2 = 企业内网单代理、只读、证据驱动、预算受控的 Agentic Search 基线版本。`

这里有 6 个关键词，缺一不可：

- `企业内网`
  目标分布是内部知识库、实体目录、制度文档、FAQ、报表说明，不是开放网页 deep research
- `单代理`
  首版先把单 agent 做稳，不把多智能体协同引入主线
- `只读`
  首版只处理 search / open / lookup / readonly report，不涉及写操作
- `证据驱动`
  答案必须来自 snapshot 证据，不允许主要靠参数知识硬答
- `预算受控`
  首版目标不是“无限深搜”，而是控制轮次、调用数和 token 成本
- `基线版本`
  这是企业 Agentic Search 的第一性闭环，不是最终形态

## 三、v2 应该明确的需求

如果只保留大方向，我建议把 `v2` 的需求冻结成下面 6 条。

### 1. 企业主场景可用

模型需要稳定处理以下主场景：

- 单文档问答
- 多文档交叉验证
- 文档 + 实体联合求证
- 少量多轮检索
- 必要时打开文档深读

首版不要求它处理开放式长报告生成，也不要求像浏览器 agent 那样完成复杂开放任务。

### 2. 必须证据闭环

`v2` 不是“会搜”的版本，而是“会拿证据回答”的版本。

最低要求：

- 最终回答有明确的证据来源
- 关键结论能回链到文档片段、实体字段或报表片段
- 答对但证据链错，仍然算失败

### 3. 必须会拒答和降级

企业场景里最大的风险不是不会答，而是错答。

`v2` 必须能稳定区分至少四类边界情况：

- 证据不足
- 权限不足
- 工具失败
- 结果冲突

并且对这四类情况给出不同的拒答或降级行为，而不是统一说一句“我不确定”。

### 4. 必须预算内最优

`v2` 的目标不是搜索越多越好，而是：

- 少轮次
- 少调用
- 少无效搜索
- 在准确率可接受前提下尽快结束

这意味着“效率”不是锦上添花，而是主需求的一部分。

### 5. 必须基于离线 snapshot 环境训练和评测

训练、reward、评测都应该优先依赖离线快照环境。

原因：

- 可复现
- 可回放
- 可验证
- 不把线上波动写进 reward

这也是 `v2` 区别于很多开放环境 RL 项目的根本边界。

### 6. 首版交付对象应是 analyst-assist，而不是 full autonomy

`v2` 最合理的产品落点不是“完全自主 deep research agent”，而是：

- 给分析师、运营、知识管理人员提供可验证的检索与证据整理辅助
- 对高风险问题优先产出 `draft + evidence bundle + boundary note`

这会显著降低首版上线风险。

## 四、哪些不应该是 v2 的硬需求

下面这些方向可以保留，但不应进入 `v2` 的冻结范围：

- 多智能体协同
- 在线真实系统 RL
- memory-aware RL
- learned PRM
- 浏览器自动化
- 开放式 deep research 报告生成
- 复杂 planner-executor 编排
- 把 `run_report_readonly` 做成 RL 主优化目标

这些能力不是没有价值，而是它们会把首版复杂度和不确定性一起拉高。

## 五、论文资料的重新分层

当前最需要做的不是“再多看几篇论文”，而是按 `v2` 的主需求重新分层。

### P0：v2 主骨架，必须重点参考

这些论文直接决定 `v2` 能不能成立。

- `Search-R1`
  - 借骨架：reasoning + search interleave
- `R1-Searcher`
  - 借低复杂度 baseline：先把搜索反射弧训出来
- `ZeroSearch`
  - 借离线模拟环境：不把真实搜索放进 RL loop
- `SearchGym`
  - 借环境分层：synthetic / snapshot / shadow-live
- `R1-Searcher++`
  - 借 search / answer / stop 路由思想
- `SmartSearch`
  - 借 query refinement
- `Search Wisely`
  - 借 over-search / under-search 决策
- `Search-P1`
  - 借 path-centric reward
- `Evaluate-as-Action`
  - 借 step-level evidence check
- `CaRR`
  - 借 evidence-grounding / citation-aware rubric
- `BAPO`
  - 借 boundary-aware abstain
- `Agentic-R`
  - 借 retriever 不应当作黑盒的思路

这一层决定的是：

- 会不会搜
- 搜得对不对
- 该不该停
- 证据是否闭环
- retriever 是否真的服务 agent

### P1：v2 数据工程与冷启动，强烈建议参考

这些论文主要服务于数据引擎，而不是 serving 主逻辑。

- `SimpleDeepSearcher`
  - 借 teacher synthesis + quality curation
- `OpenSeeker`
  - 借 controllable QA synthesis + trajectory denoising
- `OpenResearcher`
  - 借 offline corpus bootstrap + local search service + trajectory schema
- `SynPlanResearch-R1`
  - 借 synthetic plan
- `MedResearcher-R1`
  - 借垂域图谱构题
- `DeepDive`
  - 借 hard case + redundancy penalty

这一层决定的是：

- v2 有没有高质量 Gold/Silver/Hard data
- 有没有办法在企业语料上构造真正有区分度的 multi-hop case

### P2：后续增强或专项优化，先参考但不抢主线

- `In-the-Flow`
  - 价值：planner-executor orchestration
  - 结论：很有价值，但更适合主闭环跑稳之后再引入
- `W&D`
  - 价值：parallel width vs sequential depth 的效率分析
  - 结论：适合 Phase E 级别的效率强化，不是 v2 入口
- `ParallelSearch`
  - 价值：并行子查询
  - 结论：应提早参考，但不宜把“并行”当作首版主战场
- `ReSum`
  - 价值：长链路 context compression
  - 结论：适合后续长任务增强
- `MemSearcher`
  - 价值：compact memory
  - 结论：首版先做 training-free memory baseline
- `DeepResearcher`
  - 价值：真实环境交互上限参考
  - 结论：更适合作为上限参考，而不是 v2 主训练范式

## 六、哪些方法最值得借

如果不按论文名，而按“方法”抽象，我认为最值得保留的是这 8 类。

### 1. 离线 snapshot 环境

来源：

- `ZeroSearch`
- `SearchGym`
- `OpenResearcher`

意义：

- 让训练、评测、回放三件事真正闭环

这是 `v2` 成功的必要条件，不是加分项。

### 2. 企业图谱驱动的 hard synthetic 数据

来源：

- `MedResearcher-R1`
- `DeepDive`
- `OpenSeeker`

意义：

- 企业 FAQ 大多太简单，不足以逼出 agentic behavior

所以必须通过实体图、制度依赖图、流程状态图去合成难题。

### 3. Synthetic plan 作为冷启动监督

来源：

- `SynPlanResearch-R1`

意义：

- 首版最容易出现的问题不是答不出来，而是浅搜、乱搜、搜一轮就停

所以 plan supervision 非常重要。

### 4. Query refinement 与 retriever-aware optimization

来源：

- `SmartSearch`
- `Agentic-R`

意义：

- query 差，会把后面所有阶段都拖垮

这说明 query rewrite 不是“小优化”，而是主能力的一部分。

### 5. Search / stop / answer 路由

来源：

- `R1-Searcher++`
- `Search Wisely`

意义：

- 模型必须学会“什么时候直接答、什么时候继续搜、什么时候停止”

这是 `v2` 的核心能力之一。

### 6. Step-level evidence check

来源：

- `Evaluate-as-Action`

意义：

- 每一轮检索都要知道是否真的推进了求解

否则 reward 只能盯最终结果，训练会很粗。

### 7. Path-centric reward

来源：

- `Search-P1`

意义：

- 失败路径不能完全浪费
- 好路径不能只看最终答对，还要看证据覆盖和预算纪律

### 8. Boundary-aware abstain

来源：

- `BAPO`
- `CaRR`

意义：

- 这是企业落地的底线能力

## 七、哪些数据集和公开资产值得直接参考

### 第一优先级

- `OpenResearcher-Dataset`
- `OpenResearcher-Corpus`
- `OpenResearcher-Eval-Logs`
- `OpenSeeker-v1-Data`
- `SearchGym-test-data`
- `syn-plan-research-data-sft / rl / eval`

这些资产最值得直接参考的，不是“拿来即训”，而是：

- trajectory schema
- offline environment 组织方式
- eval 切片
- search agent 数据应该长什么样

### 第二优先级

- `HotpotQA`
- `2WikiMultiHopQA`
- `MuSiQue`
- `Bamboogle`
- `PopQA`
- `NQ`
- `TriviaQA`

这些资产更适合：

- 多跳问答补充
- query rewrite 预热
- retriever warmup
- “该搜 / 不该搜”路由评测

不适合作为企业主训练集主成分。

### 不建议直接作为 v2 主训练源

- `GAIA`
- `BrowseComp`
- `XBench`
- `WebWalkerQA`

原因：

- 分布更偏开放网页、浏览器、开放任务
- 对企业内网只读 agent 的首版帮助有限

## 八、模型层面的建议

### 1. 不要先拍死 student 家族

这一点 `v2-preview` 的方向是对的。

建议坚持 `Stage 0 bakeoff`：

- 同样样本
- 同样协议
- 同样预算
- 同样评测切片

然后再决定主 student。

### 2. student 应优先选择强 instruct 或 thinking-distilled 小模型

如果按 `v2` 的需求，模型的第一任务不是“从零获得知识”，而是：

- 学会路由
- 学会工具协议
- 学会边界拒答
- 学会预算内搜索

因此更建议从强 `instruct / distilled-thinking` 小模型起步，而不是直接从纯 `base` 起步。

### 3. teacher 要明显强于 student

teacher 的职责是：

- 合成 Gold / Silver
- 做 denoising
- 做 plan supervision
- 做 checklist 或 rubric 评审

这类工作比首版 serving 更需要模型上限。

### 4. retriever 不应继续作为固定黑盒

这也是 `v2` 最值得保留的一点。

如果检索层不单独优化，很多 agent 训练问题最后都会退化成：

- query 差
- 召回差
- rerank 差
- policy 背锅

## 九、结合这次 graphify-batch 整理后的额外判断

这次本地资料整理已经给出了几个清楚的信号。

### 1. GRPO 主骨架仍然应优先看 Search-R1 这条线

[grpo_sorted_by_stars_live.json](./graphify-batch/raw/global-navigation/grpo_sorted_by_stars_live.json) 里，当前最值得优先看的公开 repo 仍然是：

- `Search-R1`
- `ZeroSearch`
- `DeepResearcher`
- `R1-Searcher`
- `Tool-Star`

这说明你当前把 `Search-R1 / ZeroSearch / R1-Searcher` 放在主线是对的。

### 2. 工程效率相关论文应该被提权

[engineering_efficiency_matches.md](./graphify-batch/raw/global-navigation/engineering_efficiency_matches.md) 里，和“工程效率”最强相关的一簇包括：

- `In-the-Flow`
- `W&D`
- `ParallelSearch`
- `SmartSearch`
- `Search-P1`
- `Search Wisely`

这说明如果 `v2` 的核心目标之一是“预算内最优”，这些论文不能只当补充阅读。

### 3. 当前资料簇并没有支持“首版做多智能体或超长 research 工作流”

[navigation_summary.json](./graphify-batch/raw/global-navigation/navigation_summary.json) 里最密集的概念簇更偏：

- `Search Efficiency`
- `Tool and Knowledge Integration`
- `Agent-level`
- `Single-agent Optimization`
- `Context & Memory Management`

这和我对 `v2` 的收束判断是一致的：

- 单 agent
- 工具与知识整合
- 搜索效率
- 证据闭环

而不是先上复杂 orchestration。

## 十、最终结论

我的结论很明确：

- `v2` 的方向是对的
- 但必须收缩版本边界

如果要把这轮 review 压成一句建议，那就是：

`v2 不应该被定义成“企业版 Deep Research agent”，而应该被定义成“企业内网证据驱动、预算受控的单代理搜索基线”。`

按这个方向，最值得优先吸收的论文组合是：

- `Search-R1 + R1-Searcher + ZeroSearch + SearchGym`
- `R1-Searcher++ + SmartSearch + Search Wisely`
- `Search-P1 + Evaluate-as-Action + CaRR + BAPO`
- `OpenResearcher + OpenSeeker + SimpleDeepSearcher + SynPlanResearch-R1 + MedResearcher-R1 + DeepDive`

而下面这些应当后置：

- `In-the-Flow`
- `W&D`
- `ParallelSearch`
- `ReSum`
- `MemSearcher`
- `DeepResearcher`

## 十一、下一步建议

如果继续往前推进，我建议下一步只做一件事：

把 `r1-v2-preview.md` 重写成一个更收束的 `v2 requirements brief`，只保留：

- `v2 一句话定义`
- `must-have`
- `non-goal`
- `P0/P1/P2 参考论文与数据资产`
- `首版产品交付形态`

先冻结这个，再谈实现细节。
