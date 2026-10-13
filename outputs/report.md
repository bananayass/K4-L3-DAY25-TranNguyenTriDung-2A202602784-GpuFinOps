# NimbusAI — GPU Cost Optimization Report

- **Period:** monthly
- **Baseline spend:** $27,133
- **Optimized spend (conditional scenario):** $15,137
- **Projected savings (conditional scenario):** $11,996 (**44%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size by MBU (catalog fit) | $144 |
| Kill idle GPUs | $600 |

**Savings scope:** The headline baseline contains M2 inference plus M3 workload spend. It adds M1 telemetry right-sizing and idle savings, but the input CSVs neither include M1 fleet spend in that baseline nor map gpu_id values to M3 workload resources. Treat the combined total as conditional until resource IDs are reconciled; separate fleets omit M1 baseline spend, while overlap can double-count savings.

## GPU utilization and cost

GPU-Util measures how long a device is active, not how much useful compute it delivers. Memory stalls, synchronization, or small kernels can keep a GPU busy while MFU stays low.

| GPU | Tier | GPU-Util | MFU | On-demand rate | Cost at 720 h/month |
|---|---|---:|---:|---:|---:|
| gpu-h100-4 | H100 | 98.2% | 0.194 | $2.50/h | $1,800 |
| gpu-a10g-1 | A10G | 96.9% | 0.268 | $1.00/h | $720 |

The monthly values show on-demand capacity cost if held for 24 hours a day; they are not a measured waste estimate. Profile throughput before resizing or changing the workload.
Direct idle waste is $20.00/day ($600/month): gpu-h100-5 was idle 8 h/day.

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query (us-east-1): 0.091 gCO2e
- Lowest-carbon region: europe-north1
- Lowest-electricity-cost region: us-east-wa

At 0.24 Wh/query, europe-north1 (30 gCO2e/kWh) emits 0.007 gCO2e/query and costs $0.00002160 in electricity. us-east-wa ($0.055/kWh) costs $0.00001320/query and emits 0.022 gCO2e/query.
These are electricity-only estimates; balance grid emissions and power prices with GPU rates, data transfer, and user latency.

### Inference cost per million tokens

All stages use the same token volume. Each saving is marginal after the preceding lever; M5 purchasing savings are separate from inference cost per token.

| Stage | Cost ($/1M tokens) | Lever savings/month |
|---|---:|---:|
| Baseline | $6.488 | — |
| After cascade | $1.523 | $1,122.00 |
| After cache | $1.365 | $36.00 |
| Optimized after batch | $1.126 | $53.70 |

### MBU-based right-sizing estimates

Candidates preserve the sampled peak VRAM and compute, and fit the observed peak bandwidth at a 65% MBU target.

| GPU | Workload | Current → candidate | $/GB-VRAM | Est. monthly savings |
|---|---|---|---:|---:|
| gpu-a10g-0 | infer | A10G → L4 | $0.0417 → $0.0333 | $144.00 |

These estimates use one synthetic day and 30 days at up to 24 billed hours/day, reduced by observed idle hours. Confirm application performance, vendor support, and software compatibility before changing GPU families.

### Reasoning budget (observed cohort; modeled energy)

Reasoning rows are already included in inference spend above; this table is a breakdown, not an extra saving.

| Traffic | Requests | Tokens | Spend/day | $/1M tokens | Energy/day (Wh) | Wh/1k tokens | Token share | Cost share | Energy share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Reasoning | 201 | 1,241,156 | $1.40 | $1.1251 | 29,787.74 | 24.00 | 16.5% | 16.5% | 94.0% |
| Standard | 2,199 | 6,291,871 | $7.09 | $1.1266 | 1,887.56 | 0.30 | 83.5% | 83.5% | 6.0% |

At the same reasoning-token volume, the model estimates 372.35 Wh for standard traffic and 29787.74 Wh for reasoning traffic.
The energy totals are estimates from `wh_per_query()`; reasoning rows are all in the eval cohort, so this is an observed cohort breakdown.

## First actions for NimbusAI

1. Start with interruptible jobs and checkpointing: purchasing is the largest modeled lever at $10,040/month; reserve only after confirming duty cycle and commitment length.
2. Route simple requests to smaller models, then apply cache and batching where latency allows; inference saves $1,212/month in this scenario.
3. Right-size and shut down idle GPUs for a further $744/month, then reconcile resource IDs and required team/project tags before treating the combined forecast as bill-ready.

