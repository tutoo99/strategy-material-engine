# Retrieval Evaluation Protocol

Use this protocol when the library reaches roughly 30, 100, 300, or 1000 materials.

## What to measure

- `Recall@2 / @5 / @10`: whether known good materials appear in the top results
- `Precision@2 / @5 / @10`: how many top results are truly relevant
- `BadHit@K`: whether clearly wrong materials appear in the top results
- `Direct usable count`: how many results meet your expected type/role and are in the known-good set
- `Diversity`: how many distinct `type` and `source` values appear in the top results

## Query file design

Store evaluation queries in YAML with fields such as:

- `id`
- `query`
- `wanted_counts`
- `expected_type`
- `expected_role`
- `known_good_paths`
- `bad_paths`
- `must_have_claims`
- `notes`

## Interpretation

- If `Recall@5` is low, the recall layer is weak
- If `Recall@10` is fine but `Precision@5` is low, ranking is weak
- If known good items rank low despite high vector similarity, tune quality / reuse / role weighting
- If the same items dominate many queries, reduce overexposure through `use_count` and `last_used_at`

## Poor Top-N Diagnostic Hierarchy

When top-N results are clearly irrelevant, diagnose in this order. Each step either identifies the root cause or eliminates one variable before moving to the next.

### Step 1: Is the candidate pool large enough?

Run with `--debug-material-queries` (framework_flow.py) or compare raw_candidates vs deduped_candidates. If deduped is very low (e.g. < 8), the problem is query coverage — all queries are hitting the same small cluster of materials. Fix: expand queries (keyword_concat, multi-angle).

If deduped is reasonable (10+) but top-N is still bad, proceed to Step 2.

### Step 2: Is reranker the fix?

Run the same queries with `--reranker none` vs default reranker enabled. Compare top-N.

- If reranker on clearly improves top-N → ranking was the bottleneck. Consider enabling reranker in production (weigh speed cost vs quality gain).
- If reranker on does NOT improve (or only helps 1/4 topics) → ranking is not the root cause. Do not enable reranker. Proceed to Step 3.

### Step 3: Does relevant content even exist?

This is the most common root cause at small library sizes (under 200 materials).

Do two checks:
1. **Text search**: grep the library for core keywords from the topic (e.g. "外包", "求职", "舒适区"). If zero hits, coverage is the problem.
2. **Semantic search**: run 2-3 "ideal recall" queries against the library. If top results are only tangentially related (泛认知相邻项), not directly on-topic, coverage is confirmed as the bottleneck.

If coverage is the problem, adding more relevant materials will improve top-N far more than any query or ranking tweak.

### Decision flow

```
deduped_candidates < 8?
  → YES: fix query expansion, re-test
  → NO ↓
reranker on/off comparison shows clear improvement?
  → YES: enable reranker, done
  → NO ↓
text + semantic search confirms no relevant materials exist?
  → YES: add materials (root cause is coverage)
  → NO: investigate why existing relevant materials aren't surfacing (index/embedding issue)
```

### Lessons learned

- **Do not add materials before ruling out query/ranking issues.** At small scale, every material counts — adding irrelevant materials to a small library increases noise and can make top-N worse.
- **Do not enable reranker without A/B testing.** Reranker adds latency and cost. Only 1/4 of test topics improved in practice — the rest showed no change.
- **4 diverse topics is sufficient to form a directional conclusion.** Going from 4 to 8-10 test topics mostly confirms what you already know. If the signal is consistent across 4, act. If it's mixed, you need more data.
- **When migrating between material libraries**, all prior benchmarks are invalidated. Re-run the full diagnostic on the new library before drawing conclusions.
