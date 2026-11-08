#!/usr/bin/env python3
"""clang 21 compatibility patch for 4.19 kernel source.

Fixes -Werror failures that only appear with newer clang:
1. drivers/xiaomi/cpu_pcost.c: sizeof(buf) on a char* pointer -> PAGE_SIZE
   (all show_* functions are sysfs readers whose buffer is PAGE_SIZE)
2. qca-wifi-host-cmn ce_main.c: returning A_STATUS enum where QDF_STATUS
   is expected -> explicit cast
"""
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "kernel"

# --- 1. cpu_pcost.c ---
p1 = os.path.join(BASE, "drivers/xiaomi/cpu_pcost.c")
if not os.path.exists(p1):
    print(f"[SKIP] {p1} not found")
else:
    with open(p1, encoding="utf-8", errors="ignore") as f:
        c = f.read()
    n = c.count("snprintf(buf, sizeof(buf)")
    c = c.replace("snprintf(buf, sizeof(buf)", "snprintf(buf, PAGE_SIZE")
    with open(p1, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"[OK] cpu_pcost.c: replaced {n} sizeof(buf) -> PAGE_SIZE")

# --- 2. ce_main.c ---
p2 = os.path.join(BASE, "drivers/staging/qca-wifi-host-cmn/hif/src/ce/ce_main.c")
if not os.path.exists(p2):
    print(f"[SKIP] {p2} not found")
else:
    with open(p2, encoding="utf-8", errors="ignore") as f:
        c = f.read()
    n = c.count("return A_ERROR;")
    c = c.replace("return A_ERROR;", "return (QDF_STATUS)A_ERROR;")
    with open(p2, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"[OK] ce_main.c: replaced {n} return A_ERROR -> (QDF_STATUS)A_ERROR")

# --- 3. extra guard: any other `snprintf(x, sizeof(x))` inside xiaomi dir ---
for root, _dirs, files in os.walk(os.path.join(BASE, "drivers/xiaomi")):
    for fn in files:
        if not fn.endswith(".c"):
            continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, encoding="utf-8", errors="ignore") as f:
                c = f.read()
        except Exception:
            continue
        if "sizeof(buf)" in c and "PAGE_SIZE" in c:
            orig = c
            c = c.replace("snprintf(buf, sizeof(buf)", "snprintf(buf, PAGE_SIZE")
            if c != orig:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(c)
                print(f"[OK] {fp}: extra sizeof(buf) fix")
