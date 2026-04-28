# OpenViking Tool Protocol Draft

适用前提：

- 资料按 OpenViking 的 `viking://...` 文件系统范式组织
- 同时保留文件系统检索和语义检索
- 首版目标是企业内网单代理、只读、证据驱动、预算受控的 Agentic Search

参考来源：

- OpenViking GitHub README: https://github.com/volcengine/OpenViking
- 其中明确强调：
  - `L0 / L1 / L2` 分层上下文加载
  - “directory positioning + semantic search” 组合检索
  - CLI 原语示例 `ov ls / ov tree / ov find / ov grep`

## 1. 设计目标

这套协议的核心不是“把 OpenViking CLI 暴露给模型”，而是：

- 保留 agent 可学习的高层语义
- 吃到 OpenViking 的目录结构和分层加载能力
- 显式区分“路径定位”和“证据检索”
- 让 reward、评测、日志都能区分每一步到底在干什么

因此不建议只保留一个模糊的 `search`。

## 2. 推荐工具集

### 2.1 核心工具

- `search_fs(query, base_uri, top_k, match_mode)`
  - 用于目录、文件、资源 URI 的定位
  - 对应 OpenViking 风格的 `ls/tree/find`

- `search_semantic(query, base_uri, top_k, filters)`
  - 用于语义证据召回
  - 对应 OpenViking README 里的 semantic retrieval

- `open_resource(uri, layer)`
  - 用于读取 `L0 / L1 / L2`
  - 首选 `L0/L1`，必要时才进 `L2`

- `grep_resource(pattern, uri, top_k)`
  - 用于已定位资源内的精确查找
  - 适合找字段名、条款关键词、版本号、参数名

### 2.2 可选工具

- `lookup_entity(entity_type, keys)`
  - 仅在实体库仍然独立于 OpenViking 时保留
  - 如果实体也进了 `viking://resources/entities/...`，后续可以并入 `search_fs + open_resource`

- `run_report_readonly(report_name, filters)`
  - 建议后置
  - 仅在业务问题大量依赖结构化报表时保留
  - 不建议作为 v2 主闭环核心工具

## 3. 工具语义分工

### 3.1 `search_fs`

目标：回答“去哪里看”

适用场景：

- 已知目录名、文件名、模块名、产品名
- 已知资源大概在某个路径下
- 想先缩小搜索范围

典型返回：

- 目录 URI
- 文件 URI
- breadcrumbs
- 匹配类型：`path / name / tag`

### 3.2 `search_semantic`

目标：回答“哪些片段可能是证据”

适用场景：

- 问题主题明确，但不知道文档名
- 需要跨多个文档先做召回
- 需要快速判断证据是否存在

典型返回：

- 候选片段
- snippet
- score
- 对应资源 URI

### 3.3 `open_resource`

目标：回答“把这个资源打开确认”

适用层级：

- `L0`: 快速 relevance check
- `L1`: 结构、摘要、关键点
- `L2`: 全文或完整内容

规则：

- 默认先 `L0 / L1`
- 只有确实需要证据闭环时才进 `L2`

### 3.4 `grep_resource`

目标：回答“在已知资源里精确找”

适用场景：

- 已知文档，但不知道具体段落
- 想找条款词、字段词、版本词
- 想减少整篇打开的 token 成本

## 4. 关键原则

### 4.1 区分三类结果对象

不要把所有检索命中都当成证据。

- `locator`
  - 只是定位结果
  - 例如目录、文件、路径命中

- `evidence_candidate`
  - 只是候选证据
  - 例如语义召回到的 snippet

- `verified_evidence`
  - 已被 `open_resource` 或 `grep_resource` 验证的证据
  - 才允许进入最终回答闭环

### 4.2 首版默认搜索策略

- 已知明确资源线索：`fs_first`
- 问题模糊但主题明确：`semantic_first`
- 既要先定位范围又要找证据：`hybrid`

### 4.3 并行规则

允许 `search_fs` 和 `search_semantic` 同轮并行，但要受预算约束：

- `max_parallel_calls`
- `max_turns`
- `max_calls`

首版建议：

- `max_turns = 2`
- `max_calls = 4`
- `max_parallel_calls = 2`

## 5. 统一协议

### 5.1 `plan`

```json
<plan>
{
  "sub_questions": [
    "先定位相关产品文档目录",
    "再确认等待期条款是否有特殊例外"
  ],
  "search_strategy": "fs_first|semantic_first|hybrid",
  "parallelizable": true,
  "budget": {
    "max_turns": 2,
    "max_calls": 4,
    "max_parallel_calls": 2
  }
}
</plan>
```

### 5.2 `tool_call`

```json
<tool_call>
{
  "calls": [
    {
      "id": "c1",
      "name": "search_fs",
      "arguments": {
        "query": "A计划 重疾险 等待期",
        "base_uri": "viking://resources/insurance",
        "top_k": 5,
        "match_mode": "name_or_path"
      }
    },
    {
      "id": "c2",
      "name": "search_semantic",
      "arguments": {
        "query": "A计划重疾险住院等待期如何规定",
        "base_uri": "viking://resources/insurance",
        "top_k": 5,
        "filters": {
          "layer": "L1"
        }
      }
    }
  ]
}
</tool_call>
```

### 5.3 `tool_response`

```json
<tool_response>
{
  "results": [
    {
      "call_id": "c1",
      "tool": "search_fs",
      "result_type": "locator",
      "items": [
        {
          "result_id": "c1:0",
          "uri": "viking://resources/insurance/products/A_plan/terms/waiting_period.md",
          "title": "waiting_period.md",
          "resource_type": "file",
          "match_type": "path",
          "score": 1.0,
          "breadcrumbs": ["insurance", "products", "A_plan", "terms"]
        }
      ]
    },
    {
      "call_id": "c2",
      "tool": "search_semantic",
      "result_type": "evidence_candidate",
      "items": [
        {
          "result_id": "c2:0",
          "uri": "viking://resources/insurance/products/A_plan/terms/waiting_period.md",
          "title": "等待期说明",
          "resource_type": "file",
          "match_type": "semantic",
          "score": 0.88,
          "snippet": "本产品等待期为90天，自合同生效日起计算...",
          "layer": "L1"
        }
      ]
    }
  ],
  "env_flags": {
    "empty": false,
    "tool_error": false,
    "timeout": false
  },
  "meta": {
    "snapshot_id": "snapshot_2026_04_15",
    "cached": true
  }
}
</tool_response>
```

### 5.4 `evidence_check`

```json
<evidence_check>
{
  "status": "enough|need_more|conflict|permission_denied|tool_error",
  "locator_hits": ["c1:0"],
  "candidate_evidence": ["c2:0"],
  "verified_evidence": [],
  "missing_slots": ["full clause wording"],
  "conflict_pairs": [],
  "next_action": "open_more|grep_more|answer|abstain"
}
</evidence_check>
```

### 5.5 `final_answer`

```json
<final_answer>
{
  "decision": "answer|abstain|clarify|fallback",
  "answer": "给用户看的最终文本",
  "reason_code": "none|insufficient_evidence|permission_denied|tool_error|conflict",
  "used_result_ids": ["c3:0"],
  "budget_usage": {
    "turns": 2,
    "calls": 3
  },
  "confidence": "high|medium|low"
}
</final_answer>
```

## 6. 统一字段约束

### 6.1 `result_type`

- `locator`
- `evidence_candidate`
- `verified_evidence`

### 6.2 `decision`

- `answer`
- `abstain`
- `clarify`
- `fallback`

### 6.3 `reason_code`

- `none`
- `insufficient_evidence`
- `permission_denied`
- `tool_error`
- `conflict`

### 6.4 错误码

训练和运行时统一：

- `empty`
- `timeout`
- `permission_denied`
- `validation_error`
- `upstream_error`

## 7. 推荐路由逻辑

### 7.1 文件系统优先

当问题中出现这些线索时，优先 `search_fs`：

- 产品名
- 制度名
- 模块名
- 文件名
- 规则编号
- 路径风格关键词

### 7.2 语义优先

当问题是这些风格时，优先 `search_semantic`：

- 用户只描述问题，不知道资源名
- 问题跨多个文档
- 问题偏概念或政策解释

### 7.3 混合

当问题同时具备：

- 有明显资源线索
- 也需要召回具体证据片段

就走 `hybrid`。

## 8. 一条完整示例轨迹

用户问题：

```text
A计划重疾险住院等待期怎么规定？有例外吗？
```

### Round 1

```json
<plan>
{
  "sub_questions": [
    "先定位 A计划 对应条款文件",
    "再确认等待期规则和例外"
  ],
  "search_strategy": "hybrid",
  "parallelizable": true,
  "budget": {
    "max_turns": 2,
    "max_calls": 4,
    "max_parallel_calls": 2
  }
}
</plan>
<tool_call>
{
  "calls": [
    {
      "id": "c1",
      "name": "search_fs",
      "arguments": {
        "query": "A计划 重疾险 等待期",
        "base_uri": "viking://resources/insurance",
        "top_k": 3,
        "match_mode": "name_or_path"
      }
    },
    {
      "id": "c2",
      "name": "search_semantic",
      "arguments": {
        "query": "A计划重疾险住院等待期如何规定 有无例外",
        "base_uri": "viking://resources/insurance",
        "top_k": 3,
        "filters": {
          "layer": "L1"
        }
      }
    }
  ]
}
</tool_call>
```

```json
<tool_response>
{
  "results": [
    {
      "call_id": "c1",
      "tool": "search_fs",
      "result_type": "locator",
      "items": [
        {
          "result_id": "c1:0",
          "uri": "viking://resources/insurance/products/A_plan/terms/waiting_period.md",
          "title": "waiting_period.md",
          "resource_type": "file",
          "match_type": "path",
          "score": 1.0
        }
      ]
    },
    {
      "call_id": "c2",
      "tool": "search_semantic",
      "result_type": "evidence_candidate",
      "items": [
        {
          "result_id": "c2:0",
          "uri": "viking://resources/insurance/products/A_plan/terms/waiting_period.md",
          "title": "等待期说明",
          "resource_type": "file",
          "match_type": "semantic",
          "score": 0.88,
          "snippet": "本产品等待期为90天，但因意外伤害导致的住院不受等待期限制。",
          "layer": "L1"
        }
      ]
    }
  ],
  "env_flags": {
    "empty": false,
    "tool_error": false,
    "timeout": false
  },
  "meta": {
    "snapshot_id": "snapshot_2026_04_15",
    "cached": true
  }
}
</tool_response>
<evidence_check>
{
  "status": "need_more",
  "locator_hits": ["c1:0"],
  "candidate_evidence": ["c2:0"],
  "verified_evidence": [],
  "missing_slots": ["full clause wording"],
  "conflict_pairs": [],
  "next_action": "open_more"
}
</evidence_check>
```

### Round 2

```json
<tool_call>
{
  "calls": [
    {
      "id": "c3",
      "name": "open_resource",
      "arguments": {
        "uri": "viking://resources/insurance/products/A_plan/terms/waiting_period.md",
        "layer": "L2"
      }
    }
  ]
}
</tool_call>
```

```json
<tool_response>
{
  "results": [
    {
      "call_id": "c3",
      "tool": "open_resource",
      "result_type": "verified_evidence",
      "items": [
        {
          "result_id": "c3:0",
          "uri": "viking://resources/insurance/products/A_plan/terms/waiting_period.md",
          "section_id": "sec_2",
          "content": "等待期为90天，自合同生效日起计算。因意外伤害导致的保险事故，不适用本等待期限制。"
        }
      ]
    }
  ],
  "env_flags": {
    "empty": false,
    "tool_error": false,
    "timeout": false
  },
  "meta": {
    "snapshot_id": "snapshot_2026_04_15",
    "cached": true
  }
}
</tool_response>
<evidence_check>
{
  "status": "enough",
  "locator_hits": ["c1:0"],
  "candidate_evidence": ["c2:0"],
  "verified_evidence": ["c3:0"],
  "missing_slots": [],
  "conflict_pairs": [],
  "next_action": "answer"
}
</evidence_check>
<final_answer>
{
  "decision": "answer",
  "answer": "A计划重疾险的住院等待期是90天，从合同生效日起计算。例外情况是因意外伤害导致的住院，这种情况通常不受等待期限制。",
  "reason_code": "none",
  "used_result_ids": ["c3:0"],
  "budget_usage": {
    "turns": 2,
    "calls": 3
  },
  "confidence": "high"
}
</final_answer>
```

## 9. 首版建议

如果现在就要进正式方案，我建议首版先冻结为：

- `search_fs`
- `search_semantic`
- `open_resource`
- `grep_resource`

可选：

- `lookup_entity`

后置：

- `run_report_readonly`

原因：

- OpenViking 已经给了你“目录定位 + 分层加载 + grep 精确查找”的完整资源访问链路
- 先把这条链路训练稳，比过早引入报表工具更重要

## 10. 一句话结论

如果系统既支持文件系统检索又支持语义检索，协议不应该只保留一个泛化的 `search`，而应该显式区分：

- `search_fs`: 找路径
- `search_semantic`: 找候选证据
- `open_resource / grep_resource`: 做证据确认

这样才能真正发挥 OpenViking 的文件系统范式，而不是只是把它当成另一个文档库后端。
