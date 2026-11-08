#!/usr/bin/env python3
"""Conservative CFS scheduler tuning.

Modest, low-risk tweaks only:
  sched_latency_ns        6.0ms -> 4.0ms   (faster response for touch/UI)
  sched_min_granularity   0.75ms -> 0.9ms  (keep fairness while avoiding too-frequent preemption)
  sched_wakeup_granularity 1.0ms -> 1.3ms  (slightly fewer wakeup preemptions, saves a bit of power)

Everything else left untouched. Revert by dropping this step.
"""
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "kernel"
p = os.path.join(BASE, "kernel/sched/fair.c")

if not os.path.exists(p):
    print(f"[SKIP] {p} not found")
    sys.exit(0)

with open(p, encoding="utf-8", errors="ignore") as f:
    c = f.read()

pairs = [
    # (old, new, label)
    ("unsigned int sysctl_sched_latency			= 6000000ULL;",
     "unsigned int sysctl_sched_latency			= 4000000ULL;", "latency"),
    ("unsigned int normalized_sysctl_sched_latency		= 6000000ULL;",
     "unsigned int normalized_sysctl_sched_latency		= 4000000ULL;", "normalized latency"),
    ("unsigned int sysctl_sched_min_granularity		= 750000ULL;",
     "unsigned int sysctl_sched_min_granularity		= 900000ULL;", "min_granularity"),
    ("unsigned int normalized_sysctl_sched_min_granularity	= 750000ULL;",
     "unsigned int normalized_sysctl_sched_min_granularity	= 900000ULL;", "normalized min_granularity"),
    ("unsigned int sysctl_sched_wakeup_granularity		= 1000000UL;",
     "unsigned int sysctl_sched_wakeup_granularity		= 1300000UL;", "wakeup_granularity"),
    ("unsigned int normalized_sysctl_sched_wakeup_granularity	= 1000000UL;",
     "unsigned int normalized_sysctl_sched_wakeup_granularity	= 1300000UL;", "normalized wakeup_granularity"),
]

hits = 0
for old, new, label in pairs:
    if old in c:
        c = c.replace(old, new, 1)
        hits += 1
        print(f"[OK] {label} patched")
    else:
        print(f"[WARN] {label} pattern not found (already patched or line differs)")

if hits:
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
print(f"[DONE] {hits}/{len(pairs)} scheduler values updated")
