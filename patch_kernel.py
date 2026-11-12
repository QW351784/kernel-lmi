#!/usr/bin/env python3
"""lmi cip136 第二轮优化补丁脚本（10 项）
在 kernel/ 目录下执行：python3 patch_kernel.py
任何一处未命中都会 FAIL 并退出非零，避免静默失效。
"""
import re, sys, pathlib

FAIL = []
OK = []

def sub(path, old, new, expect=None, label=""):
    p = pathlib.Path(path)
    if not p.exists():
        FAIL.append(f"[{label}] 文件不存在: {path}")
        return
    with open(p, newline='') as f:
        s = f.read()
    n = s.count(old)
    if n == 0:
        FAIL.append(f"[{label}] 未命中: {path} :: {old[:70]!r}")
        return
    if expect is not None and n != expect:
        FAIL.append(f"[{label}] 命中数异常 {path}: 期望 {expect}, 实际 {n}")
        return
    with open(p, 'w', newline='') as f:
        f.write(s.replace(old, new))
    OK.append(f"[{label}] {path} ({n}处)")

def add_config(path, line, label=""):
    p = pathlib.Path(path)
    if not p.exists():
        FAIL.append(f"[{label}] 文件不存在: {path}")
        return
    with open(p, newline='') as f:
        s = f.read()
    if line in s:
        OK.append(f"[{label}] 已存在: {line}")
        return
    with open(p, 'w', newline='') as f:
        f.write(s.rstrip() + "\n" + line + "\n")
    OK.append(f"[{label}] 追加: {line}")

# ---------- 1. 调度 base_slice 700000 -> 600000 ----------
sub("kernel/sched/fair.c", "= 700000ULL;", "= 600000ULL;", expect=2, label="1-base_slice")

# ---------- 2. 调度特性 关两个 ----------
sub("kernel/sched/features.h",
    "SCHED_FEAT(PLACE_REL_DEADLINE, true)", "SCHED_FEAT(PLACE_REL_DEADLINE, false)",
    expect=1, label="2-PLACE_REL_DEADLINE")
sub("kernel/sched/features.h",
    "SCHED_FEAT(RUN_TO_PARITY, true)", "SCHED_FEAT(RUN_TO_PARITY, false)",
    expect=1, label="2-RUN_TO_PARITY")

# ---------- 3/4. 触控 boost：时长 40->120ms，小核默认 1.2GHz ----------
sub("drivers/cpufreq/cpu-boost.c",
    "static unsigned int input_boost_ms = 40;", "static unsigned int input_boost_ms = 120;",
    expect=1, label="3-input_boost_ms")
sub("drivers/cpufreq/cpu-boost.c",
    "\t\ts->cpu = cpu;",
    "\t\ts->cpu = cpu;\n\t\t/* 小核(cpu0-3)触控默认加速到 1.2GHz，其余核不 boost */\n\t\ts->input_boost_freq = (cpu < 4) ? 1200000 : 0;",
    expect=1, label="4-input_boost_freq")

# ---------- 5. FORTIFY_SOURCE ----------
add_config("arch/arm64/configs/lmi_defconfig", "CONFIG_FORTIFY_SOURCE=y", label="5-FORTIFY")

# ---------- 6. PANIC_TIMEOUT -1 -> 5 ----------
sub("arch/arm64/configs/lmi_defconfig", "CONFIG_PANIC_TIMEOUT=-1", "CONFIG_PANIC_TIMEOUT=5",
    expect=1, label="6-PANIC_TIMEOUT")

# ---------- 7. SUSFS 日志关闭 ----------
sub("arch/arm64/configs/vendor/xiaomi/magictime-common.config",
    "CONFIG_KSU_SUSFS_ENABLE_LOG=y", "# CONFIG_KSU_SUSFS_ENABLE_LOG is not set",
    expect=1, label="7-SUSFS_LOG")
# 注意：nidhi-variant.config 是 build.sh 运行时由 magictime-common.config 生成的，不在此改

# ---------- 8. KPM ----------
add_config("arch/arm64/configs/lmi_defconfig", "CONFIG_KPM=y", label="8-KPM")

# ---------- 9. 充电满速：thermal-mitigation 首档 + pd-power-max ----------
sub("arch/arm64/boot/dts/vendor/xiaomi/lmi-sm8250.dtsi",
    "qcom,thermal-mitigation = <3000000 ", "qcom,thermal-mitigation = <3100000 ",
    expect=1, label="9-mitigation首档")
sub("arch/arm64/boot/dts/vendor/xiaomi/lmi-sm8250.dtsi",
    "mi,pd-power-max = <33>", "mi,pd-power-max = <36>",
    expect=2, label="9-pd_power_max")

# ---------- 10. DCP 普通充电器 1.8A -> 2.0A（仅前9档） ----------
dts = pathlib.Path("arch/arm64/boot/dts/vendor/xiaomi/lmi-sm8250.dtsi")
with open(dts, newline='') as f:
    s = f.read()
m = re.search(r"(qcom,thermal-mitigation-dcp\s*=\s*<)(.*?)(>;)", s, re.S)
if not m:
    FAIL.append("[10-dcp] 未找到 thermal-mitigation-dcp 块")
else:
    body = m.group(2)
    new_body, cnt = re.subn(r"1800000", "2000000", body, count=9)
    if cnt != 9:
        FAIL.append(f"[10-dcp] 期望替换9个 1.8A 档，实际 {cnt} 个")
    else:
        s = s[:m.start(2)] + new_body + s[m.end(2):]
        with open(dts, 'w', newline='') as f:
            f.write(s)
        OK.append("[10-dcp] 前9档 1800000 -> 2000000")

print("=" * 60)
for k in OK: print("OK  ", k)
for f in FAIL: print("FAIL", f)
print("=" * 60)
if FAIL:
    print(f"共 {len(FAIL)} 处失败，终止")
    sys.exit(1)
print(f"全部通过（{len(OK)} 项）")
