"""
run_retrieval_sweep.py — 检索随机化 × 社会流动 的对照实验跑批器
================================================================================
⚠ 本脚本尚未在真实 LLM 上跑过（写它的会话里没有可用的 API key）。
   逻辑已按可复现方式写好，但**第一次跑请先用 --ticks 3 做小样验证**，
   确认 6 个 agent 都真的产生了行动（否则 N/U 的分母是 0，数字没意义）。

自变量    SINA_RETRIEVAL_MODE ∈ {topk, random, tail} × ratio p ∈ [0,1]
          （topk 即条件 A；random 即 B；tail 即 C —— 见 sina/memory/retrieval_policy.py）
计量表    SINA_MOBILITY=1：资源 → 阶级 动态回写（见 core/social_mobility.py）
结局变量  1) 资源存量的绝对轨迹 & 末值（不要用 quantile 模式的 class 当结局，那是重言式）
          2) N = 联想对数 / 输出实体对数，以及 ungrounded_rate（见 sina/memory/novelty.py）
          3) U = 1 - 现实拦截数 / 行动意图数

用法
----
  export DEEPSEEK_API_KEY=sk-...
  python sandboxes/run_retrieval_sweep.py --ticks 60 \
      --modes topk,random,tail --ratios 0,0.2,0.4,0.6,0.8 \
      --seeds 1,2,3 --out results/retrieval_sweep

先做的最小验证：
  python sandboxes/run_retrieval_sweep.py --ticks 3 --modes topk,random --ratios 0,0.5 --seeds 1
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dag_simulation import DAGSmallvilleSimulation
from sina.memory.novelty import (
    aggregate_novelty,
    build_memory_entity_index,
    compute_novelty,
    known_entities_from_sim,
)


def _configure_env(args, mode: str, ratio: float, seed: int, run_dir: str) -> None:
    """用环境变量配置每次 run（这样跑的就是真实的生产配置路径，而非旁路赋值）。"""
    os.environ["SINA_DATA_DIR"] = run_dir
    os.environ["SINA_RETRIEVAL_MODE"] = mode
    os.environ["SINA_RETRIEVAL_RATIO"] = str(ratio)
    os.environ["SINA_RETRIEVAL_SEED"] = str(seed)
    os.environ["SINA_MOBILITY"] = "1"
    os.environ["SINA_MOBILITY_MODE"] = args.mobility_mode
    os.environ["SINA_MOBILITY_INTERVAL"] = str(args.mobility_interval)
    os.environ["SINA_MOBILITY_EMA"] = str(args.mobility_ema)


def _resource_snapshot(sim) -> Dict[str, float]:
    """资源存量的绝对量（结局变量，与阶级映射方式无关）。"""
    return {name: float(sum(a.inventory.values())) for name, a in sim.world_agents.items()}


def _novelty_metrics(sim) -> Dict[str, float]:
    """按「run 结束时该 agent 的记忆库」作为知识参照，算联想/幻觉分解。

    注意：这是**近似**——严格做法是逐 tick 用当时的记忆快照。用末态参照会让
    N 略偏低（后来的记忆把早期的「新连接」追认成已知）。做趋势对比够用，
    但写论文时要披露这一点。
    """
    known = known_entities_from_sim(sim)
    per_text: List[dict] = []
    for entry in sim.agent_text_log or []:
        agent = entry["agent"]
        memories = sim.memory_manager.vector_store.get_agent_memories(agent)
        seen, cooccur = build_memory_entity_index(memories, known)
        text = f"{entry['thought']} {entry['action']}"
        res = compute_novelty(text, seen, cooccur, known)
        res["tick"] = entry["tick"]
        res["agent"] = agent
        per_text.append(res)

    agg = aggregate_novelty(per_text)
    agg["texts"] = len(per_text)
    return agg


def run_one(args, mode: str, ratio: float, seed: int) -> dict:
    run_dir = os.path.join(os.path.abspath(args.out), f"{mode}_p{ratio}_s{seed}", "data")
    os.makedirs(run_dir, exist_ok=True)
    _configure_env(args, mode, ratio, seed, run_dir)

    sim = DAGSmallvilleSimulation(world_name=args.world, resume=False)
    sim.agent_text_log = []
    resources_before = _resource_snapshot(sim)

    asyncio.run(sim.run_dag_loop(ticks=args.ticks))

    resources_after = _resource_snapshot(sim)
    intents = sim.stats["intents"]
    interceptions = sim.stats["interceptions"]

    record = {
        "mode": mode,
        "ratio": ratio,
        "seed": seed,
        "ticks": args.ticks,
        "mobility_mode": args.mobility_mode,
        "config": {
            "k": args.top_k,
            "decay_seed": sim.memory_manager.decay_engine.rng is not None,
        },
        "resources_before": resources_before,
        "resources_after": resources_after,
        "resource_delta": {n: resources_after[n] - resources_before.get(n, 0.0) for n in resources_after},
        "class_final": {n: sim.memory_manager.get_persona(n).class_index for n in sim.world_agents},
        "novelty": _novelty_metrics(sim),
        "U": (1.0 - interceptions / intents) if intents else None,
        "intents": intents,
        "interceptions": interceptions,
        "mobility_history": sim.mobility.history,
    }

    run_path = os.path.join(os.path.dirname(run_dir), "result.json")
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def _summarize(records: List[dict]) -> List[dict]:
    """按 (mode, ratio) 聚合多个 seed：均值 ± 标准差。没有误差棒的结论不算结论。"""
    buckets: Dict[tuple, List[dict]] = {}
    for r in records:
        buckets.setdefault((r["mode"], r["ratio"]), []).append(r)

    rows = []
    for (mode, ratio), group in sorted(buckets.items()):
        ns = [g["novelty"]["N"] for g in group]
        ungs = [g["novelty"]["ungrounded_rate"] for g in group]
        deltas = [
            statistics.fmean(g["resource_delta"].values()) if g["resource_delta"] else 0.0
            for g in group
        ]
        us = [g["U"] for g in group if g["U"] is not None]
        rows.append({
            "mode": mode,
            "ratio": ratio,
            "n_seeds": len(group),
            "N_mean": statistics.fmean(ns) if ns else None,
            "N_std": statistics.pstdev(ns) if len(ns) > 1 else 0.0,
            "ungrounded_mean": statistics.fmean(ungs) if ungs else None,
            "resource_delta_mean": statistics.fmean(deltas) if deltas else None,
            "resource_delta_std": statistics.pstdev(deltas) if len(deltas) > 1 else 0.0,
            "U_mean": statistics.fmean(us) if us else None,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="检索随机化 × 社会流动 对照实验")
    ap.add_argument("--ticks", type=int, default=60)
    ap.add_argument("--world", default="smallville")
    ap.add_argument("--modes", default="topk,random,tail")
    ap.add_argument("--ratios", default="0,0.2,0.4,0.6,0.8")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--out", default="results/retrieval_sweep")
    ap.add_argument("--mobility-mode", default="absolute",
                    help="绝对模式才不会让「阶级」退化成资源排名的别名（quantile 是零和的）")
    ap.add_argument("--mobility-interval", type=int, default=5)
    ap.add_argument("--mobility-ema", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=3, help="仅记录用：assemble_prompt_context 的 top_k_episodes")
    args = ap.parse_args()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("✗ 缺少 DEEPSEEK_API_KEY —— AgentThinkNode 需要真实 LLM，否则每个 tick 都是"
              "「思考异常」，intents=0，N/U 的分母为 0，跑出来一堆空数字。")
        return 2

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    ratios = [float(r) for r in args.ratios.split(",") if r.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    records: List[dict] = []
    total = len(modes) * len(ratios) * len(seeds)
    i = 0
    for mode in modes:
        for ratio in ratios:
            if mode == "topk" and ratio != 0.0:
                continue  # A 条件下 ratio 无意义，跳过重复格子
            for seed in seeds:
                i += 1
                print(f"\n{'=' * 70}\n[{i}/{total}] mode={mode} ratio={ratio} seed={seed}\n{'=' * 70}")
                try:
                    records.append(run_one(args, mode, ratio, seed))
                except Exception as exc:  # 单个 run 失败不该毁掉整个 sweep
                    print(f"  ✗ run 失败: {type(exc).__name__}: {exc}")

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    summary = _summarize(records)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"args": vars(args), "rows": summary}, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 78}\n汇总（N=联想率，U=1-约束违反率，Δresource=平均资源增量）\n{'=' * 78}")
    print(f"{'mode':>8} {'ratio':>6} {'seeds':>6} {'N':>16} {'ungrounded':>12} {'Δresource':>18} {'U':>8}")
    for row in summary:
        n_str = f"{row['N_mean']:.3f}±{row['N_std']:.3f}" if row["N_mean"] is not None else "n/a"
        d_str = (f"{row['resource_delta_mean']:.1f}±{row['resource_delta_std']:.1f}"
                 if row["resource_delta_mean"] is not None else "n/a")
        u_str = f"{row['U_mean']:.3f}" if row["U_mean"] is not None else "n/a"
        ung_str = f"{row['ungrounded_mean']:.3f}" if row["ungrounded_mean"] is not None else "n/a"
        print(f"{row['mode']:>8} {row['ratio']:>6.2f} {row['n_seeds']:>6} {n_str:>16} "
              f"{ung_str:>12} {d_str:>18} {u_str:>8}")
    print(f"\n逐 run 明细与完整轨迹: {out_dir}/<mode>_p<ratio>_s<seed>/result.json")
    print(f"汇总表: {out_dir}/summary.json")
    print("\n判读提醒：只看 N 会被骗 —— N 高且 ungrounded 同步走高 = 它在胡说，不是联想。"
          "B(random) 与 C(tail) 的差才归因于随机性本身。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
