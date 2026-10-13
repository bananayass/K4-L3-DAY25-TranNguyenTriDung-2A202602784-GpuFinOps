"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing
from finops import sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = cascade_cost = cache_cost = opt_cost = 0.0
    total_tokens = 0
    traffic = {
        False: {"requests": 0, "tokens": 0, "cost": 0.0, "energy_wh": 0.0},
        True: {"requests": 0, "tokens": 0, "cost": 0.0, "energy_wh": 0.0},
    }
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # Apply each lever in sequence to the same traffic for marginal savings.
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cascade_cost += pricing.request_cost(inp, out, pin, pout)
        cache_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached)
        request_cost = pricing.request_cost(
            inp, out, pin, pout, cached_in=cached, batch=is_batch,
        )
        opt_cost += request_cost

        group = traffic[is_reasoning]
        group["requests"] += 1
        group["tokens"] += inp + out
        group["cost"] += request_cost
        group["energy_wh"] += sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    stage_costs = {
        "baseline": base_cost,
        "after_cascade": cascade_cost,
        "after_cache": cache_cost,
        "after_batch": opt_cost,
    }
    stage_savings = {
        "cascade": base_cost - cascade_cost,
        "cache": cascade_cost - cache_cost,
        "batch": cache_cost - opt_cost,
    }

    total_energy = sum(group["energy_wh"] for group in traffic.values())
    total_optimized_cost = sum(group["cost"] for group in traffic.values())
    total_requests = sum(group["requests"] for group in traffic.values())
    reasoning = {}
    for is_reasoning, group in traffic.items():
        key = "reasoning" if is_reasoning else "standard"
        tokens = group["tokens"]
        reasoning[key] = {
            "requests": group["requests"],
            "tokens": tokens,
            "cost_usd": round(group["cost"], 4),
            "cost_per_m": round(pricing.dollars_per_million(group["cost"], tokens), 4),
            "energy_wh": round(group["energy_wh"], 3),
            "wh_per_1k_tokens": round(group["energy_wh"] / tokens * 1000, 3) if tokens else 0.0,
            "request_share": group["requests"] / total_requests if total_requests else 0.0,
            "token_share": tokens / total_tokens if total_tokens else 0.0,
            "cost_share": group["cost"] / total_optimized_cost if total_optimized_cost else 0.0,
            "energy_share": group["energy_wh"] / total_energy if total_energy else 0.0,
        }
    reasoning_tokens = traffic[True]["tokens"]
    reasoning["same_token_energy_wh"] = {
        "standard": round(sustainability.wh_per_query(reasoning_tokens), 3),
        "reasoning": round(sustainability.wh_per_query(reasoning_tokens, is_reasoning=True), 3),
    }

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print("stepwise levers (same tokens; marginal savings are sequential):")
        print(f"  after cascade: ${cascade_cost:,.2f}/day  saved ${stage_savings['cascade']:,.2f}")
        print(f"  after cache  : ${cache_cost:,.2f}/day  saved ${stage_savings['cache']:,.2f}")
        print(f"  after batch  : ${opt_cost:,.2f}/day  saved ${stage_savings['batch']:,.2f}")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("reasoning cohort (observed traffic; energy is modeled):")
        for key in ("reasoning", "standard"):
            g = reasoning[key]
            print(
                f"  {key:9} {g['requests']:4} requests, {g['tokens']:,} tokens, "
                f"${g['cost_usd']:,.2f}, {g['energy_wh']:,.2f} Wh; "
                f"shares: tokens {g['token_share']:.1%}, cost {g['cost_share']:.1%}, "
                f"energy {g['energy_share']:.1%}"
            )
        print(
            "  same reasoning-token volume energy: "
            f"{reasoning['same_token_energy_wh']['standard']:.2f} Wh standard vs "
            f"{reasoning['same_token_energy_wh']['reasoning']:.2f} Wh reasoning"
        )

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "stage_costs": {k: round(v, 2) for k, v in stage_costs.items()},
        "stage_savings": {k: round(v, 2) for k, v in stage_savings.items()},
        "stage_per_m": {k: round(pricing.dollars_per_million(v, total_tokens), 3) for k, v in stage_costs.items()},
        "reasoning": reasoning,
    }


if __name__ == "__main__":
    run()
