"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    conditional = bool(sustainability and sustainability.get("savings_scope_note"))
    scenario_label = " (conditional scenario)" if conditional else ""
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"- **Period:** {period}",
        f"- **Baseline spend:** ${baseline_usd:,.0f}",
        f"- **Optimized spend{scenario_label}:** ${optimized_usd:,.0f}",
        f"- **Projected savings{scenario_label}:** ${savings:,.0f} (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        scope_note = sustainability.get("savings_scope_note")
        if scope_note:
            lines += ["", f"**Savings scope:** {scope_note}"]
        efficiency = sustainability.get("gpu_efficiency")
        if efficiency:
            lines += [
                "",
                "## GPU utilization and cost",
                "",
                "GPU-Util measures how long a device is active, not how much useful compute it delivers. Memory stalls, synchronization, or small kernels can keep a GPU busy while MFU stays low.",
                "",
                "| GPU | Tier | GPU-Util | MFU | On-demand rate | Cost at 720 h/month |",
                "|---|---|---:|---:|---:|---:|",
            ]
            for item in efficiency.get("lies", []):
                lines.append(
                    f"| {item['gpu_id']} | {item['gpu_type']} | {item['gpu_util_pct']:.1f}% | "
                    f"{item['mfu']:.3f} | ${item['on_demand_hr']:.2f}/h | ${item['full_month_cost']:,.0f} |"
                )
            lines += [
                "",
                "The monthly values show on-demand capacity cost if held for 24 hours a day; they are not a measured waste estimate. Profile throughput before resizing or changing the workload.",
            ]
            idle_gpus = efficiency.get("idle_gpus", [])
            if idle_gpus:
                details = "; ".join(
                    f"{item['gpu_id']} was idle {item['idle_hours']} h/day"
                    for item in idle_gpus
                )
                lines.append(
                    f"Direct idle waste is ${efficiency['idle_waste_daily']:,.2f}/day "
                    f"(${efficiency['idle_waste_monthly']:,.0f}/month): {details}."
                )
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query ({sustainability.get('reference_region', 'reference region')}): {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Lowest-carbon region: {sustainability.get('cleanest_region', sustainability.get('best_region', 'n/a'))}",
            f"- Lowest-electricity-cost region: {sustainability.get('cheapest_region', 'n/a')}",
        ]
        region_metrics = sustainability.get("region_metrics", {})
        cleanest = sustainability.get("cleanest_region")
        cheapest = sustainability.get("cheapest_region")
        if cleanest in region_metrics and cheapest in region_metrics:
            clean = region_metrics[cleanest]
            cheap = region_metrics[cheapest]
            lines += [
                "",
                f"At {sustainability.get('wh_per_query', 0):.2f} Wh/query, {cleanest} "
                f"({clean['carbon_g_per_kwh']:.0f} gCO2e/kWh) emits "
                f"{clean['carbon_g_per_query']:.3f} gCO2e/query and costs "
                f"${clean['electricity_usd_per_query']:.8f} in electricity. {cheapest} "
                f"(${cheap['electricity_usd_per_kwh']:.3f}/kWh) costs "
                f"${cheap['electricity_usd_per_query']:.8f}/query and emits "
                f"{cheap['carbon_g_per_query']:.3f} gCO2e/query.",
                "These are electricity-only estimates; balance grid emissions and power prices with GPU rates, data transfer, and user latency.",
            ]
        stages = sustainability.get("inference_stages_monthly")
        if stages:
            stage_per_m = sustainability.get("inference_stage_per_m", {})
            lines += [
                "",
                "### Inference cost per million tokens",
                "",
                "All stages use the same token volume. Each saving is marginal after the preceding lever; M5 purchasing savings are separate from inference cost per token.",
                "",
                "| Stage | Cost ($/1M tokens) | Lever savings/month |",
                "|---|---:|---:|",
                f"| Baseline | ${stage_per_m.get('baseline', 0):.3f} | — |",
                f"| After cascade | ${stage_per_m.get('after_cascade', 0):.3f} | ${stages.get('cascade', 0):,.2f} |",
                f"| After cache | ${stage_per_m.get('after_cache', 0):.3f} | ${stages.get('cache', 0):,.2f} |",
                f"| Optimized after batch | ${stage_per_m.get('after_batch', 0):.3f} | ${stages.get('batch', 0):,.2f} |",
            ]
        recommendations = sustainability.get("rightsize_recommendations")
        if recommendations is not None:
            lines += [
                "",
                "### MBU-based right-sizing estimates",
                "",
                "Candidates preserve the sampled peak VRAM and compute, and fit the observed peak bandwidth at a 65% MBU target.",
                "",
                "| GPU | Workload | Current → candidate | $/GB-VRAM | Est. monthly savings |",
                "|---|---|---|---:|---:|",
            ]
            for item in recommendations:
                lines.append(
                    f"| {item['gpu_id']} | {item['workload']} | "
                    f"{item['current_type']} → {item['recommended_type']} | "
                    f"${item['current_usd_per_gb']:.4f} → ${item['recommended_usd_per_gb']:.4f} | "
                    f"${item['monthly_savings']:,.2f} |"
                )
            lines += [
                "",
                "These estimates use one synthetic day and 30 days at up to 24 billed hours/day, reduced by observed idle hours. Confirm application performance, vendor support, and software compatibility before changing GPU families.",
            ]
        reasoning = sustainability.get("reasoning")
        if reasoning:
            lines += [
                "",
                "### Reasoning budget (observed cohort; modeled energy)",
                "",
                "Reasoning rows are already included in inference spend above; this table is a breakdown, not an extra saving.",
                "",
                "| Traffic | Requests | Tokens | Spend/day | $/1M tokens | Energy/day (Wh) | Wh/1k tokens | Token share | Cost share | Energy share |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
            for key, label in (("reasoning", "Reasoning"), ("standard", "Standard")):
                group = reasoning[key]
                lines.append(
                    f"| {label} | {group['requests']:,} | {group['tokens']:,} | "
                    f"${group['cost_usd']:,.2f} | ${group['cost_per_m']:.4f} | "
                    f"{group['energy_wh']:,.2f} | {group['wh_per_1k_tokens']:.2f} | "
                    f"{group['token_share']:.1%} | {group['cost_share']:.1%} | {group['energy_share']:.1%} |"
                )
            same_tokens = reasoning["same_token_energy_wh"]
            lines += [
                "",
                f"At the same reasoning-token volume, the model estimates {same_tokens['standard']:.2f} Wh "
                f"for standard traffic and {same_tokens['reasoning']:.2f} Wh for reasoning traffic.",
                "The energy totals are estimates from `wh_per_query()`; reasoning rows are all in the eval cohort, so this is an observed cohort breakdown.",
            ]
        if levers:
            purchasing = next((v for k, v in levers.items() if k.lower().startswith("purchasing")), 0)
            inference = next((v for k, v in levers.items() if k.lower().startswith("inference")), 0)
            rightsize = next((v for k, v in levers.items() if k.lower().startswith("right-size")), 0)
            idle = next((v for k, v in levers.items() if "idle" in k.lower()), 0)
            lines += [
                "",
                "## First actions for NimbusAI",
                "",
                f"1. Start with interruptible jobs and checkpointing: purchasing is the largest modeled lever at ${purchasing:,.0f}/month; reserve only after confirming duty cycle and commitment length.",
                f"2. Route simple requests to smaller models, then apply cache and batching where latency allows; inference saves ${inference:,.0f}/month in this scenario.",
                f"3. Right-size and shut down idle GPUs for a further ${rightsize + idle:,.0f}/month, then reconcile resource IDs and required team/project tags before treating the combined forecast as bill-ready.",
            ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write a baseline-to-optimized spend waterfall PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    values = [float(levers[name]) for name in names]
    baseline = float(baseline_usd) if baseline_usd is not None else sum(values)
    optimized = baseline - sum(values)
    positions = list(range(len(values) + 2))
    labels = ["Baseline"] + [name.replace(" (", "\n(") for name in names] + ["Optimized"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(positions[0], baseline, color="#2e548a", width=0.68)

    current = baseline
    offset = max(abs(baseline) * 0.012, 20)
    ax.text(positions[0], baseline + offset, f"${baseline:,.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    if values:
        ax.plot([0.34, 0.66], [current, current], color="#777777", linewidth=1)
    for index, amount in enumerate(values, start=1):
        next_value = current - amount
        ax.bar(
            positions[index], abs(amount), bottom=min(current, next_value),
            color="#39856a" if amount >= 0 else "#bd5a4a", width=0.68,
        )
        ax.text(
            positions[index], max(current, next_value) + offset,
            f"${amount:,.0f}", ha="center", va="bottom", fontsize=8,
        )
        current = next_value
        if index < len(values):
            ax.plot([positions[index] + 0.34, positions[index] + 0.66], [current, current], color="#777777", linewidth=1)

    final_position = positions[-1]
    if values:
        ax.plot([positions[-2] + 0.34, final_position - 0.34], [current, current], color="#777777", linewidth=1)
    ax.bar(final_position, optimized, color="#2e548a", width=0.68)
    ax.text(final_position, optimized + offset, f"${optimized:,.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax.set_xticks(positions, labels)
    ax.set_ylabel("Monthly spend (USD)")
    ax.set_title("Baseline to optimized GPU spend")
    ax.set_ylim(0, baseline + offset * 4)
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
