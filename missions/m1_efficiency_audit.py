"""M1 — Efficiency Audit: MFU/MBU, the GPU-Util lie, and idle waste (deck §5).

Run: python missions/m1_efficiency_audit.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num, catalog_by_type
from finops import metrics

RIGHTSIZE_TARGET_MBU = 0.65


def run(verbose: bool = True) -> dict:
    tel = load_csv("gpu_telemetry.csv")
    cat = catalog_by_type()

    # per-row MFU/MBU, then aggregate per GPU
    agg = defaultdict(lambda: {
        "util": [], "mfu": [], "mbu": [], "type": None, "workload": None,
        "idle_hours": 0, "achieved_bw": [], "achieved_tflops": [], "mem_used_gb": [],
    })
    for r in tel:
        gtype = r["gpu_type"]
        peak_fp16 = num(cat[gtype]["peak_tflops_fp16"])
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        mfu = metrics.compute_mfu(num(r["achieved_tflops"]), peak_fp16)
        mbu = metrics.compute_mbu(num(r["achieved_bw_tbs"]), peak_bw)
        a = agg[r["gpu_id"]]
        a["type"] = gtype
        a["workload"] = r["workload"]
        a["util"].append(num(r["gpu_util_pct"]))
        a["mfu"].append(mfu)
        a["mbu"].append(mbu)
        a["achieved_bw"].append(num(r["achieved_bw_tbs"]))
        a["achieved_tflops"].append(num(r["achieved_tflops"]))
        a["mem_used_gb"].append(num(r["mem_used_gb"]))
        if num(r["gpu_util_pct"]) < 10:  # effectively idle this interval (1h)
            a["idle_hours"] += 1

    summary = []
    for gid, a in agg.items():
        summary.append({
            "gpu_id": gid, "gpu_type": a["type"],
            "gpu_util_pct": round(sum(a["util"]) / len(a["util"]), 1),
            "mfu": round(sum(a["mfu"]) / len(a["mfu"]), 3),
            "mbu": round(sum(a["mbu"]) / len(a["mbu"]), 3),
            "idle_hours": a["idle_hours"],
            "workload": a["workload"],
            "peak_achieved_bw_tbs": max(a["achieved_bw"], default=0.0),
            "peak_achieved_tflops": max(a["achieved_tflops"], default=0.0),
            "peak_mem_used_gb": max(a["mem_used_gb"], default=0.0),
        })

    lies = metrics.flag_util_lies(summary)
    idle_waste = 0.0
    for s in summary:
        on_demand = num(cat[s["gpu_type"]]["on_demand_hr"])
        idle_waste += metrics.idle_waste_usd(s["idle_hours"], on_demand)

    # Right-size against the observed daily peak, with enough compute and VRAM
    # to preserve the sampled workload and enough bandwidth to stay below the
    # target MBU. The extension targets inference/embed workloads; this is a
    # catalog-fit estimate from one synthetic day.
    rightsize_recommendations = []
    for s in summary:
        if s["workload"] not in {"infer", "embed"}:
            continue
        if s["mbu"] >= RIGHTSIZE_TARGET_MBU:
            continue
        current = cat[s["gpu_type"]]
        current_rate = num(current["on_demand_hr"])
        candidates = []
        for gpu_type, candidate in cat.items():
            rate = num(candidate["on_demand_hr"])
            if rate >= current_rate:
                continue
            if num(candidate["hbm_gb"]) < s["peak_mem_used_gb"]:
                continue
            if num(candidate["peak_bw_tbs"]) * RIGHTSIZE_TARGET_MBU < s["peak_achieved_bw_tbs"]:
                continue
            if num(candidate["peak_tflops_fp16"]) < s["peak_achieved_tflops"]:
                continue
            candidates.append((rate, gpu_type, candidate))

        if not candidates:
            continue
        rate, gpu_type, candidate = min(candidates, key=lambda item: item[0])
        active_hours_per_day = max(0, 24 - s["idle_hours"])
        monthly_savings = (current_rate - rate) * active_hours_per_day * 30
        rightsize_recommendations.append({
            "gpu_id": s["gpu_id"], "workload": s["workload"],
            "current_type": s["gpu_type"], "recommended_type": gpu_type,
            "current_mbu": s["mbu"], "target_mbu": RIGHTSIZE_TARGET_MBU,
            "peak_achieved_bw_tbs": round(s["peak_achieved_bw_tbs"], 3),
            "peak_mem_used_gb": round(s["peak_mem_used_gb"], 1),
            "current_usd_per_gb": current_rate / num(current["hbm_gb"]),
            "recommended_usd_per_gb": rate / num(candidate["hbm_gb"]),
            "current_on_demand_hr": current_rate,
            "recommended_on_demand_hr": rate,
            "active_hours_per_day": active_hours_per_day,
            "monthly_savings": round(monthly_savings, 2),
        })
    rightsize_savings = round(sum(r["monthly_savings"] for r in rightsize_recommendations), 2)

    if verbose:
        print("== M1 Efficiency Audit ==")
        print(f"{'GPU':14}{'type':7}{'util%':>7}{'MFU':>7}{'MBU':>7}{'idle_h':>8}")
        for s in sorted(summary, key=lambda x: x["mfu"]):
            print(f"{s['gpu_id']:14}{s['gpu_type']:7}{s['gpu_util_pct']:>7}{s['mfu']:>7}{s['mbu']:>7}{s['idle_hours']:>8}")
        print(f"\nGPU-Util LIES (util>=90% but MFU<30%): {[l['gpu_id'] for l in lies]}")
        print(f"Idle waste (1 day): ${idle_waste:,.2f}  ->  ${idle_waste*30:,.0f}/month")
        print("$/GB-VRAM at on-demand rates:")
        for gpu_type, gpu in sorted(cat.items()):
            usd_per_gb = num(gpu["on_demand_hr"]) / num(gpu["hbm_gb"])
            print(f"  {gpu_type:7} ${usd_per_gb:.4f}/GB")
        print(f"\nRight-sizing estimates (target MBU <= {RIGHTSIZE_TARGET_MBU:.0%}; preserve peak VRAM, BW, and compute):")
        if rightsize_recommendations:
            for r in rightsize_recommendations:
                print(
                    f"  {r['gpu_id']}: {r['current_type']} -> {r['recommended_type']}  "
                    f"${r['current_usd_per_gb']:.4f} -> ${r['recommended_usd_per_gb']:.4f}/GB-VRAM  "
                    f"(${r['monthly_savings']:,.0f}/month)"
                )
        else:
            print("  no cheaper catalog fit preserves the sampled peaks")
        print(f"  estimated monthly savings: ${rightsize_savings:,.0f} (720 billed hours/month, less observed idle hours)")
        print("  Validate workload performance and software compatibility before changing GPU families.")

    return {
        "summary": summary, "lies": lies, "idle_waste_daily": round(idle_waste, 2),
        "rightsize_recommendations": rightsize_recommendations,
        "rightsize_savings_monthly": rightsize_savings,
    }


if __name__ == "__main__":
    run()
