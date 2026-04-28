# 企业内网本地化 Agentic-Search 重点论文分析

## 1. 研究方法与产物范围

- 全量论文台账见 `papers_full.md` / `papers_full.csv` / `papers_full.json`。
- 主表按 awesome 仓库中的唯一主论文去重，共 `159` 篇，快照日期为 `2026-04-14`。
- 对每篇论文至少完成了以下层级的信息抽取：
  - 论文标题、发布时间、摘要
  - 代码仓库与 star 快照
  - README / 顶层结构可复用模块
- 本文只对与“企业内部知识库 + 内部工具 + 本地化训练 + 推理效率/推理轮次”最相关的论文做深读归纳。
- 在主表之外，本轮额外补充评估了 `Step-DeepResearch`、`OpenSeeker`、`OpenResearcher` 三个新增开源资源，并把结论写回本文与实施方案。
- 旧方案 [r1-v1.md](../../r1-v1.md) 只作为现有数据资产参考，不作为架构前提。

## 2. 先说结论

完整读完这批文献后，最重要的结论不是“哪个公开网页 deep research 分数最高”，而是下面 8 条：

1. 企业内网场景不应该直接照搬 open-web browser agent。
2. 首版最该做的是“高质量企业轨迹数据 + 可验证离线环境”，不是一上来做重型在线 RL。
3. 训练目标不能只优化最终答案正确率，必须显式优化：工具选择、证据归因、拒答边界、轮次、调用次数。
4. 检索器不能继续被当成固定黑盒，企业内网检索器需要被单独训练或至少被 agent 轨迹反标。
5. 对企业场景来说，“少搜、搜准、早停、会拒答”比“无限多轮搜索”更重要。
6. 多工具是必要的，但不能首版全量上；工具太多会和 reasoning 互相干扰。
7. 长任务的关键不是无限扩上下文，而是摘要记忆、并行检索和冗余抑制。
8. 模型起点现在不该预设死。正确做法是先做 `<=8B` 候选 student 的小规模 bakeoff，再定主线。

## 3. 重点论文分组

### 3.1 冷启动与数据引擎

#### Search-R1
- 时间：`12 Mar 2025`
- 代码：[PeterGriffinJin/Search-R1](https://github.com/PeterGriffinJin/Search-R1)
- Star：`4462`
- 亮点：把搜索调用和推理交织进 RL，给出了稳定训练的开源骨架和 retrieved token masking 思路。
- 对你的价值：
  - 给出 agentic-search 的基本 RL 骨架
  - 适合作为最小可跑 baseline
- 不足：
  - 主要面向公开搜索
  - 奖励仍偏 outcome-based
  - 对企业工具路由、证据合规、轮次预算约束不够强
- 结论：`可作为基线，不可作为最终企业方案本体`。

#### R1-Searcher
- 时间：`7 Mar 2025`
- 代码：[RUCAIBox/R1-Searcher](https://github.com/RUCAIBox/R1-Searcher)
- Star：`707`
- 亮点：两阶段 outcome-RL，强调不依赖复杂 process reward 也能完成冷启动。
- 对你的价值：
  - 说明首版不一定要先建复杂 PRM 才能跑起来
  - 对低成本起步有参考意义
- 不足：
  - 对企业场景最关心的证据链与边界意识约束不够
- 结论：`适合做低复杂度 baseline-2`。

#### SimpleDeepSearcher
- 时间：`22 May 2025`
- 代码：[RUCAIBox/SimpleDeepSearcher](https://github.com/RUCAIBox/SimpleDeepSearcher)
- Star：`118`
- 亮点：证明高质量 trajectory synthesis 本身就能带来很强提升，不必过度迷信重型 RL。
- 对你的价值：
  - 非常适合企业内网冷启动
  - 与你现有 Q/A、目标知识、答案这类数据资产天然匹配
- 不足：
  - 更多解决“先把 agent 样子训出来”，不是最终可靠性闭环
- 结论：`企业数据引擎最值得直接借鉴的论文之一`。

#### SynPlanResearch-R1
- 时间：`9 Mar 2026`
- 代码：[HansiZeng/syn-plan-research](https://github.com/HansiZeng/syn-plan-research)
- Star：`6`
- 亮点：通过 synthetic plans 修正 agent 冷启动时的浅尝辄止和工具偏置。
- 对你的价值：
  - 非常适合 `search + 少量内部工具` 的冷启动
  - 可以直接迁移到企业工具探索 SFT 数据合成
- 不足：
  - 公开场景为主，内部工具约束需要自行重写
- 结论：`应纳入 v1 数据合成策略`。

#### MedResearcher-R1
- 时间：`20 Aug 2025`
- 代码：[AQ-MedAI/MedResearcher-R1](https://github.com/AQ-MedAI/MedResearcher-R1)
- Star：`498`
- 亮点：用知识图谱驱动垂域多跳题合成，并配合领域工具构建完整训练数据流水线。
- 代码结构可直接借鉴：
  - `KnowledgeGraphConstruction`
  - `TrajectoryGenerationPipeline`
  - `EvaluationPipeline`
- 对你的价值：
  - 这是最贴近“企业专有知识库 + 专用工具”的公开案例
  - 证明垂域 agent 不一定从通用 web 数据长出来，可以从领域知识结构直接构题
- 结论：`这是企业内网方案最强的正样本之一`。

#### DeepDive
- 时间：`12 Sep 2025`
- 代码：[THUDM/DeepDive](https://github.com/THUDM/DeepDive)
- Star：`296`
- 亮点：从知识图谱自动生成高难问题，并在多轮 RL 中加入冗余 query 惩罚。
- 对你的价值：
  - 能把企业知识图谱、制度依赖图、业务对象关系图转成难题生成器
  - 冗余惩罚直接对应“推理效率/轮次”
- 结论：`v1 的 hard-case 生成与效率奖励都应参考它`。

### 3.2 低成本训练环境与 sim-to-real

#### ZeroSearch
- 时间：`7 May 2025`
- 代码：[Alibaba-NLP/ZeroSearch](https://github.com/Alibaba-NLP/ZeroSearch)
- Star：`1259`
- 亮点：用模拟搜索替代真实搜索，显著降低 RL 成本，同时保持训练有效性。
- 对你的价值：
  - 企业内网最不适合直接在 RL 阶段打真实系统
  - 这篇论文几乎直接回答了“如何便宜地训练”
- 结论：`企业内网 RL 的默认环境思路应该以 ZeroSearch 为中心`。

#### SearchGym
- 时间：`21 Jan 2026`
- 代码：[JIA-Lab-research/SearchGym](https://github.com/JIA-Lab-research/SearchGym)
- Star：`9`
- 亮点：用可验证 KG + 对齐文档搭建高保真模拟环境，并验证 sim-to-real。
- 仓库里最值得借鉴的设计：
  - 训练环境和评测环境分离
  - synthetic/local/live 三层环境
- 对你的价值：
  - 企业场景完全可以做“企业 SearchGym”
  - 比公开网页更容易做对，因为内部数据更可控
- 结论：`应作为企业离线环境建设蓝本`。

#### DeepResearcher
- 时间：`4 Apr 2025`
- 代码：[GAIR-NLP/DeepResearcher](https://github.com/GAIR-NLP/DeepResearcher)
- Star：`727`
- 亮点：真实环境端到端 RL，会涌现计划、交叉验证、自反思与诚实回答。
- 对你的价值：
  - 它证明真实环境 RL 的上限确实更高
- 不足：
  - 对企业内网 v1 来说太重，且真实系统 rollout 成本过高
- 结论：`更适合当 v2/v3 的上限参照，不适合作为 v1 默认路径`。

### 3.3 检索器、查询质量与工具路由

#### SmartSearch
- 时间：`8 Jan 2026`
- 代码：[RUC-NLPIR/SmartSearch](https://github.com/RUC-NLPIR/SmartSearch)
- Star：`38`
- 亮点：给中间 query 质量显式过程奖励，并支持低质量 query 的 refinement。
- 对你的价值：
  - 企业场景中大量错误不是“不会回答”，而是“检索词构错了”
  - 这篇论文直接解决 query 质量问题
- 结论：`v1 必须吸收其 query-level reward 思想`。

#### Agentic-R
- 时间：`17 Jan 2026`
- 代码：[8421BCD/Agentic-R](https://github.com/8421BCD/Agentic-R)
- Star：`77`
- 亮点：指出 agentic-search 的 retriever 不能继续沿用普通 similarity-based RAG retriever，要按 passage utility 重新训练。
- 对你的价值：
  - 企业内网最容易卡在检索层，不是生成层
  - 这篇论文给出 agent 与 retriever 双向迭代的路径
- 结论：`检索器单独训练是企业落地的必要环节，不是可选优化项`。

#### R1-Searcher++
- 时间：`22 May 2025`
- 代码：[RUCAIBox/R1-Searcher-plus](https://github.com/RUCAIBox/R1-Searcher-plus)
- Star：`76`
- 亮点：同时奖励内部知识利用和外部搜索利用，还引入记忆式吸收机制。
- 对你的价值：
  - 很适合企业“能直接答就别搜，必须搜时再搜”
  - 这类 internal/external routing 是企业效率核心
- 结论：`应当把它吸收到 student 的路由奖励里`。

### 3.4 过程奖励、证据一致性与拒答边界

#### Search-P1
- 时间：`26 Feb 2026`
- 代码：无公开仓库
- 亮点：path-centric reward，让失败轨迹也能产出学习信号，显著提升样本效率。
- 对你的价值：
  - 企业数据贵，失败 rollout 不能全部浪费
- 结论：`v1 的 RL 奖励设计应采用路径级局部评分，而不是只看最终答案`。

#### Evaluate-as-Action
- 时间：`10 Mar 2026`
- 代码：无公开仓库
- 亮点：把“检索质量评估”变成显式动作，每次检索后立即自评，再做 segment-level advantage 重标定。
- 对你的价值：
  - 特别适合企业工具返回长文档或不稳定结果时做 early correction
- 结论：`非常适合企业 agent 的自检回路`。

#### CaRR
- 时间：`9 Jan 2026`
- 代码：[THUDM/CaRR](https://github.com/THUDM/CaRR)
- Star：`61`
- 亮点：citation-aware rubric rewards，把证据链完整性、事实依据和 hidden entity 找全都纳入奖励。
- 仓库里直接可借鉴的模块：
  - `deepsearch_rm_with_rubrics`
  - rubric-based reward server
- 对你的价值：
  - 企业问答比公开问答更需要“有据可查”
- 结论：`这是企业证据奖励的首选参考实现`。

#### ProRAG
- 时间：`29 Jan 2026`
- 代码：[lilinwz/ProRAG](https://github.com/lilinwz/ProRAG)
- Star：`24`
- 亮点：用 learned process reward 解决长链路 credit assignment。
- 对你的价值：
  - 如果 v1 后续发现规则奖励不够，可以把它作为 v2 的 learned PRM 路线
- 结论：`v1 参考，v2 可落地`。

#### BAPO
- 时间：`16 Jan 2026`
- 代码：[Liushiyu-0709/BAPO-Reliable-Search](https://github.com/Liushiyu-0709/BAPO-Reliable-Search)
- Star：`24`
- 亮点：明确训练“我不知道”的边界意识，并避免模型把 IDK 当捷径滥用。
- 对你的价值：
  - 企业内网里答错通常比拒答更贵
- 结论：`拒答边界必须成为主奖励之一，不是补丁功能`。

### 3.5 推理效率、推理轮次与记忆管理

#### Search More, Think Less
- 时间：`26 Feb 2026`
- 代码：[OPPO-PersonalAI/SMTL](https://github.com/OPPO-PersonalAI/SMTL)
- Star：`2`
- 亮点：把顺序深想改成并行证据采集，在长任务下显著减少 reasoning steps 和成本。
- 对你的价值：
  - 这篇论文直接回应了你新增的“关注推理效率及推理轮次”约束
- 结论：`v1 方案必须加入 parallel retrieval 候选机制`。

#### ParallelSearch
- 时间：`12 Aug 2025`
- 代码：无公开仓库
- 亮点：让 agent 识别可并行的子查询结构，并并发搜索。
- 对你的价值：
  - 对企业内网特别有用，尤其是比对型问题和多实体问题
- 结论：`应在工具协议层预留并行 calls`。

#### Search Wisely
- 时间：`22 May 2025`
- 代码：无公开仓库
- 亮点：分析 over-search / under-search，并用不确定性阈值优化搜索决策。
- 对你的价值：
  - 直接对应“少搜但别漏搜”的目标
- 结论：`企业评测必须加入 over-search / under-search 指标`。

#### ReSum
- 时间：`16 Sep 2025`
- 代码：无公开仓库
- 亮点：外部摘要工具 + ReSum-GRPO，让长历史被压成可继续推理的短摘要。
- 对你的价值：
  - 非常适合长流程制度问答、跨多份文档核验
- 结论：`比堆长上下文更适合企业内网部署`。

#### MemSearcher
- 时间：`4 Nov 2025`
- 代码：[icip-cas/MemSearcher](https://github.com/icip-cas/MemSearcher)
- Star：`19`
- 亮点：通过 compact memory 稳定上下文长度，并做 memory-aware RL。
- 对你的价值：
  - 可以显著控制 token 成本和多轮推理时长
- 结论：`v1 后半段应加入 memory 节点，而不是无限增长上下文`。

### 3.6 本轮补充的三个开源资源

#### OpenResearcher
- 时间：`17 Mar 2026`
- 代码：[TIGER-AI-Lab/OpenResearcher](https://github.com/TIGER-AI-Lab/OpenResearcher)
- Star：`652`
- 亮点：
  - 把长链 deep research 的轨迹合成、模型训练、离线搜索环境和评测 recipe 一起开源
  - 用 `search/open/find` 三个显式 browser primitive 在离线 `15M` 文档语料上完成搜索-浏览闭环
  - 公开了 `97K+` 轨迹，其中包含大量 `100+` tool calls 的长轨迹
- 代码里最值得直接借鉴的部分：
  - `browser.py` 的 local search/open/find 抽象
  - `scripts/deploy_search_service.py` 的本地检索服务与高亮摘要
  - `scripts/start_search_service.sh` 的本地 dense/BM25 搜索服务部署方式
- 对你的价值：
  - 这是当前最接近“企业本地语料 + 本地检索服务 + 离线轨迹合成”的公开正样本
  - 它证明了“一次性 corpus bootstrap”和“多轮 trajectory synthesis”可以解耦，且不依赖外部 Search API
  - 对你的企业 snapshot-env、shadow-eval、离线 teacher 轨迹生成都有直接方法价值
- 不足：
  - 仍是 open-web deep research 分布
  - 使用 browser primitive，任务目标偏长报告和公开搜索
  - 30B-A3B 与 `100+` tool call 长轨迹强度明显高于企业 v1 所需
- 结论：`应优先吸收其离线环境、local search service 和长轨迹合成方法，但不直接照搬其 open-web 任务分布与长报告目标`。

#### OpenSeeker
- 时间：`16 Mar 2026`
- 代码：[rui-ye/OpenSeeker](https://github.com/rui-ye/OpenSeeker)
- Star：`561`
- 亮点：
  - 直接把 frontier search agent 的训练数据和模型开源
  - 用 `fact-grounded scalable controllable QA synthesis` 构造可控多跳问题
  - 用 `retrospective summarization` 做 trajectory denoising，只用 `11.7K` 样本做 SFT 也能打到很强成绩
- 对你的价值：
  - “可控构题 + 轨迹去噪”这两点都非常适合企业内网冷启动
  - 可把它的 topological expansion / entity obfuscation 思路迁移到企业实体图、制度依赖图、流程图上
  - retrospective summarization 很适合做企业 Silver 数据清洗，把冗余搜索、无贡献浏览和错误反思裁掉
- 不足：
  - 代码实现更偏 `search + visit` 两工具和公开网页环境
  - 依赖 `Serper/Tavily/Jina` 与外部摘要 API，代码复用性弱于 `OpenResearcher`
  - 训练分布仍然是 open-web benchmark，不是企业制度/报表/实体混合分布
- 结论：`方法和数据价值高于代码价值；最适合吸收到企业 Hard Synthetic 构题与 Silver 轨迹去噪流水线`。

#### Step-DeepResearch
- 时间：`23 Dec 2025`
- 代码：[stepfun-ai/StepDeepResearch](https://github.com/stepfun-ai/StepDeepResearch)
- Star：`544`
- 亮点：
  - 把 deep research 拆成 atomic capabilities：planning、information seeking、reflection/cross-validation、report generation
  - 用 progressive pipeline 把 agentic mid-training、SFT、RL 串起来
  - 引入 checklist-style judger 强化稳健性，并强调单智能体条件下的成本效率
- 对你的价值：
  - atomic capability decomposition 很适合改写成企业版训练 curriculum
  - checklist-style judger 很适合借来做企业 evidence / boundary / efficiency 的 rubric evaluator
  - 它提供了“单智能体、较高效率”的工程方向参照，而不是多智能体堆复杂度
- 不足：
  - 依赖其内部专有工具体系，公开代码中的工具空间仍包含 `batch_web_surfer/file/todo/shell`
  - 目标偏开放式研究报告生成，不等于企业内网问答/只读工具检索
  - 当前公开内容更适合作为技术报告与推理效率标杆，复现实用性不如 `OpenResearcher`
- 结论：`适合作为能力拆分、judge 设计和效率上限的参考，不适合作为企业 v1 的直接骨架`。

## 4. 哪些公开路线不适合直接照搬

### 4.1 纯 open-web deep research 路线
- 不适合原因：
  - 工具空间过大
  - 文档质量不可控
  - 评测目标偏 open-ended report，而不是企业有证据问答
- 代表：`DeepResearcher`、`WebSailor-V2`、`WebResearcher`
- 处理方式：只吸收训练思想，不照搬环境。

### 4.2 多智能体/浏览器优先路线
- 不适合原因：
  - 你当前的核心是内网知识与工具，不是网页 GUI 操作
  - 多智能体会显著放大工程复杂度和推理成本
- 代表：`M-ASK`、`AgentFlow`、`MAO-ARAG`、`AI-SearchPlanner`
- 处理方式：v1 不引入。

### 4.3 只看最终答案的 outcome-only RL
- 不适合原因：
  - 企业里“答对了但证据错了”不可接受
  - 也不利于压缩轮次和控制工具成本
- 处理方式：必须加入过程奖励、证据奖励、边界奖励、预算奖励。

## 5. 对本项目的直接设计结论

### 必做
- 企业知识图谱或实体依赖图驱动的数据合成
- 内部工具统一成少量只读接口
- 离线/模拟环境优先
- query-level 与 path-level 奖励
- 证据一致性与拒答边界奖励
- 并行检索、冗余惩罚、轮次预算评测
- 检索器单独训练或迭代微调

### 首版不做
- 浏览器型 agent
- 多智能体 planner-executor 编排
- 在线真实系统 RL
- 全量多工具训练
- 多模态

### 你最应该直接复用的仓库
1. [Search-R1](https://github.com/PeterGriffinJin/Search-R1)
2. [ZeroSearch](https://github.com/Alibaba-NLP/ZeroSearch)
3. [SearchGym](https://github.com/JIA-Lab-research/SearchGym)
4. [SimpleDeepSearcher](https://github.com/RUCAIBox/SimpleDeepSearcher)
5. [MedResearcher-R1](https://github.com/AQ-MedAI/MedResearcher-R1)
6. [DeepDive](https://github.com/THUDM/DeepDive)
7. [SmartSearch](https://github.com/RUC-NLPIR/SmartSearch)
8. [Agentic-R](https://github.com/8421BCD/Agentic-R)
9. [CaRR](https://github.com/THUDM/CaRR)
10. [BAPO](https://github.com/Liushiyu-0709/BAPO-Reliable-Search)
11. [OpenResearcher](https://github.com/TIGER-AI-Lab/OpenResearcher)
12. [OpenSeeker](https://github.com/rui-ye/OpenSeeker)

## 6. 最终判断

对“基于企业内部知识库及内部工具的高效本地化 Agentic-Search 模型训练”来说，最佳路线不是单押某一篇论文，而是下面这个组合：

- 冷启动数据：`SimpleDeepSearcher + MedResearcher-R1 + SynPlanResearch-R1 + DeepDive`
- 训练环境：`ZeroSearch + SearchGym`
- 基线 RL 骨架：`Search-R1 / R1-Searcher`
- 查询与检索器：`SmartSearch + Agentic-R`
- 可靠性：`CaRR + BAPO + Evaluate-as-Action`
- 效率与轮次：`Search More, Think Less + ParallelSearch + Search Wisely`
- 长任务管理：`ReSum + MemSearcher`
- 开放长轨迹与离线搜索补充：`OpenResearcher + OpenSeeker`
- 能力拆分与 judge / 效率标杆：`Step-DeepResearch`

这就是后续实施方案的理论来源。
