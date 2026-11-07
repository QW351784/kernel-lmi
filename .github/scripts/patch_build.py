import sys

p = sys.argv[1]
s = open(p).read()

anchor = 'echo "MIUI-specific configs applied" >> "$LOG_FILE"'
inject = anchor + r'''

  # === custom perf opts ===
  scripts/config --file out/.config \
    -d DEBUG_KERNEL \
    -d SCHED_DEBUG \
    -d DEBUG_SPINLOCK \
    -d DEBUG_MUTEXES \
    -d DEBUG_LOCK_ALLOC \
    -d PROVE_LOCKING \
    -d PROFILING \
    -e CC_OPTIMIZE_FOR_PERFORMANCE \
    -e SECURITY_YAMA \
    -e SECURITY_DMESG_RESTRICT \
    -e FORTIFY_SOURCE \
    -d SCHEDSTATS \
    -d SCHED_INFO
  echo "custom perf opts applied" >> "$LOG_FILE"
'''

if anchor not in s:
    print("ANCHOR NOT FOUND, skip")
    sys.exit(1)

s = s.replace(anchor, inject, 1)
open(p, "w").write(s)
print("patched", p)
