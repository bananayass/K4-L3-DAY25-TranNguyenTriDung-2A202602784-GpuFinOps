"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import ROOT, catalog_by_type, num
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing

DAYS = 30


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = r1["rightsize_savings_monthly"]

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size by MBU (catalog fit)": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    cleanest_region = min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get)
    cheapest_region = min(sustainability.REGION_PRICE_KWH, key=sustainability.REGION_PRICE_KWH.get)
    region_metrics = {
        region: {
            "electricity_usd_per_kwh": sustainability.REGION_PRICE_KWH[region],
            "carbon_g_per_kwh": sustainability.REGION_CARBON[region],
            "electricity_usd_per_query": sustainability.energy_cost_usd(wh, region),
            "carbon_g_per_query": sustainability.carbon_g(wh, region),
        }
        for region in sustainability.REGION_CARBON
    }
    catalog = catalog_by_type()
    gpu_lies = []
    for item in r1["lies"]:
        rate = num(catalog[item["gpu_type"]]["on_demand_hr"])
        gpu_lies.append({
            "gpu_id": item["gpu_id"], "gpu_type": item["gpu_type"],
            "gpu_util_pct": item["gpu_util_pct"], "mfu": item["mfu"],
            "on_demand_hr": rate, "full_month_cost": rate * 24 * DAYS,
        })
    idle_gpus = [
        {
            "gpu_id": item["gpu_id"], "gpu_type": item["gpu_type"],
            "idle_hours": item["idle_hours"],
        }
        for item in r1["summary"] if item["idle_hours"] > 0
    ]
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "reference_region": "us-east-1",
        "best_region": cleanest_region,
        "cleanest_region": cleanest_region,
        "cheapest_region": cheapest_region,
        "region_metrics": region_metrics,
        "gpu_efficiency": {
            "lies": gpu_lies,
            "idle_gpus": idle_gpus,
            "idle_waste_daily": r1["idle_waste_daily"],
            "idle_waste_monthly": round(r1["idle_waste_daily"] * DAYS),
        },
        "reasoning": r2["reasoning"],
        "inference_stages_monthly": {
            key: round(value * DAYS, 2) for key, value in r2["stage_savings"].items()
        },
        "inference_stage_per_m": r2["stage_per_m"],
        "rightsize_recommendations": r1["rightsize_recommendations"],
        "savings_scope_note": (
            "The headline baseline contains M2 inference plus M3 workload spend. It adds M1 telemetry right-sizing and idle savings, "
            "but the input CSVs neither include M1 fleet spend in that baseline nor map gpu_id values to M3 workload resources. "
            "Treat the combined total as conditional until resource IDs are reconciled; separate fleets omit M1 baseline spend, while overlap can double-count savings."
        ),
    }

    md = report.build_report(baseline, optimized, levers, sustainability=sust)
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as f:
        f.write(md)
    png = report.savings_waterfall(
        levers, os.path.join(ROOT, "outputs", "savings.png"), baseline_usd=baseline,
    )

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
