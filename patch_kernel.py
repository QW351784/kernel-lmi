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

def sub_optional(path, old, new, expect=None, label=""):
    """文件不存在则跳过（用于仅 Ultra 源码才有的文件）"""
    if not pathlib.Path(path).exists():
        OK.append(f"[{label}] 跳过：{path} 不存在（非 Ultra 环境）")
        return
    sub(path, old, new, expect=expect, label=label)

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

# ---------- 5. FORTIFY_SOURCE：跳过 ----------
# security/Kconfig 里 FORTIFY_SOURCE 有 "depends on !CC_IS_CLANG"，
# clang 24 工具链下该项被 Kconfig 强制禁用，写进 defconfig 也会被丢弃。
OK.append("[5-FORTIFY] 跳过：clang 工具链下 FORTIFY_SOURCE 被 Kconfig 禁用（depends on !CC_IS_CLANG）")

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

# ---------- 8b. KPROBES：Ultra 的 config KSU 硬依赖 ----------
# Ultra: config KSU  depends on KPROBES && EXT4_FS
# 不开 KPROBES -> KSU 不可见 -> 整个 KernelSU/SuSFS 被 defconfig 丢弃
add_config("arch/arm64/configs/vendor/xiaomi/magictime-common.config",
           "CONFIG_KPROBES=y", label="8b-KPROBES")

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

# ---------- 11. Ultra 兼容 4.19：MODULE_IMPORT_NS 宏不存在 ----------
# 4.19 没有符号命名空间机制，MODULE_IMPORT_NS 未定义，
# clang 会把它当隐式函数声明直接报 -Wimplicit-int 错误。
sub_optional("drivers/kernelsu/core/init.c",
             "MODULE_IMPORT_NS(VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver);",
             "/* MODULE_IMPORT_NS: unavailable on 4.19, removed */",
             expect=1, label="11-MODULE_IMPORT_NS")

# ---------- 12. Ultra file_wrapper.c 兼容 4.19 ----------
# 4.19 的 struct file_operations 没有 iopoll(5.1+) / remap_file_range(4.20+)
fwp = pathlib.Path("drivers/kernelsu/infra/file_wrapper.c")
if not fwp.exists():
    OK.append("[12-file_wrapper] 跳过：文件不存在（非 Ultra 环境）")
else:
    s = fwp.read_text()
    pairs = [
        ("12A-iopoll-head",
         "#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 1, 0)\nstatic int ksu_wrapper_iopoll",
         "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)\n#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 1, 0)\nstatic int ksu_wrapper_iopoll"),
        ("12B-iopoll-tail",
         "    return orig->f_op->iopoll(kiocb, spin);\n}\n#endif\n\n#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0)",
         "    return orig->f_op->iopoll(kiocb, spin);\n}\n#endif\n#endif  /* iopoll: >= 5.1.0 only */\n\n#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0)"),
        ("12C-iopoll-assign",
         "    p->ops.iopoll = fp->f_op->iopoll ? ksu_wrapper_iopoll : NULL;\n",
         "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)\n    p->ops.iopoll = fp->f_op->iopoll ? ksu_wrapper_iopoll : NULL;\n#endif\n"),
        ("12D-remap-head",
         "static loff_t ksu_wrapper_remap_file_range(",
         "#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 20, 0)\nstatic loff_t ksu_wrapper_remap_file_range("),
        ("12E-remap-tail",
         "        return orig->f_op->remap_file_range(orig, pos_in, file_out, pos_out, len, remap_flags);\n    }\n}\n",
         "        return orig->f_op->remap_file_range(orig, pos_in, file_out, pos_out, len, remap_flags);\n    }\n}\n#endif  /* remap_file_range: >= 4.20 only */\n"),
        ("12F-remap-assign",
         "    p->ops.remap_file_range = fp->f_op->remap_file_range ? ksu_wrapper_remap_file_range : NULL;\n",
         "#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 20, 0)\n    p->ops.remap_file_range = fp->f_op->remap_file_range ? ksu_wrapper_remap_file_range : NULL;\n#endif\n"),
    ]
    for label, old, new in pairs:
        n = s.count(old)
        if n != 1:
            FAIL.append(f"[{label}] 命中数异常: {n}")
            continue
        s = s.replace(old, new)
        OK.append(f"[{label}] ok")
    fwp.write_text(s)

# ---------- 13. Ultra seccomp_cache.c 兼容 4.19 ----------
# 4.19 没有 seccomp cache(5.9+)，保留符号为空实现，避免 setuid_hook 链接失败
scp = pathlib.Path("drivers/kernelsu/infra/seccomp_cache.c")
if not scp.exists():
    OK.append("[13-seccomp] 跳过：文件不存在（非 Ultra 环境）")
else:
    s2 = scp.read_text()
    inc = '#include "infra/seccomp_cache.h"'
    if s2.count(inc) == 1:
        s2 = s2.replace(inc, inc + """

#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 9, 0)
/* 4.19: no seccomp cache support; keep the symbols as no-ops */
void ksu_seccomp_clear_cache(struct seccomp_filter *filter, int nr) { (void)filter; (void)nr; }
void ksu_seccomp_allow_cache(struct seccomp_filter *filter, int nr) { (void)filter; (void)nr; }
#else""", 1)
        s2 = s2.rstrip("\n") + "\n\n#endif /* LINUX_VERSION_CODE < KERNEL_VERSION(5, 9, 0) */\n"
        scp.write_text(s2)
        OK.append("[13-seccomp] 4.19 下改为空实现")
    else:
        FAIL.append(f"[13-seccomp] include 未命中: {s2.count(inc)}")


# ---------- 14. Ultra su_mount_ns.c 兼容 4.19 ----------
# 4.19 没有 uapi/linux/mount.h（5.x 才拆出），MS_* 常量在 uapi/linux/fs.h（已被 linux/fs.h 包含）
smp = pathlib.Path("drivers/kernelsu/infra/su_mount_ns.c")
if not smp.exists():
    OK.append("[14-mount] 跳过：文件不存在（非 Ultra 环境）")
else:
    s3 = smp.read_text()
    old = "#include <uapi/linux/mount.h>"
    if s3.count(old) == 1:
        s3 = s3.replace(old, "/* uapi/linux/mount.h: absent on 4.19; MS_* comes from linux/fs.h */")
        smp.write_text(s3)
        OK.append("[14-mount] 移除 uapi/linux/mount.h 包含")
    else:
        FAIL.append(f"[14-mount] 命中数异常: {s3.count(old)}")

# ---------- 15. Ultra pkg_observer.c 兼容 4.19（fsnotify_ops 只有 handle_event） ----------
# 4.19 的 struct fsnotify_ops 没有 handle_inode_event（5.9 才有），但 handle_event 可用，
# 参数不同。做一次签名适配，功能完整保留，不再降级成空实现。
pkg = pathlib.Path("drivers/kernelsu/manager/pkg_observer.c")
if not pkg.exists():
    OK.append("[15-pkg_observer] 跳过：文件不存在（非 Ultra 环境）")
else:
    s4 = pkg.read_text()
    old_impl = """static int ksu_handle_inode_event(struct fsnotify_mark *mark, u32 mask, struct inode *inode, struct inode *dir,
                                  const struct qstr *file_name, u32 cookie)
{
    if (!file_name)
        return 0;
    if (mask & FS_ISDIR)
        return 0;
    if (file_name->len == 13 && !memcmp(file_name->name, "packages.list", 13)) {
        pr_info("packages.list detected: %d\\n", mask);
        ksu_defer_track_throne();
    }
    return 0;
}

static const struct fsnotify_ops ksu_ops = {
    .handle_inode_event = ksu_handle_inode_event,
};"""
    new_impl = """static void ksu_check_packages_list(const struct qstr *file_name, u32 mask)
{
    if (!file_name)
        return;
    if (mask & FS_ISDIR)
        return;
    if (file_name->len == 13 && !memcmp(file_name->name, "packages.list", 13)) {
        pr_info("packages.list detected: %d\\n", mask);
        ksu_defer_track_throne();
    }
}

#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 9, 0)
/* 4.19: fsnotify_ops only has handle_event; adapt its signature */
static int ksu_handle_event(struct fsnotify_group *group, struct inode *inode,
                            u32 mask, const void *data, int data_type,
                            const unsigned char *file_name, u32 cookie,
                            struct fsnotify_iter_info *iter_info)
{
    struct qstr name;

    (void)group;
    (void)inode;
    (void)data;
    (void)data_type;
    (void)cookie;
    (void)iter_info;

    if (!file_name)
        return 0;

    name.name = file_name;
    name.len = strlen(file_name);
    name.hash = 0;

    ksu_check_packages_list(&name, mask);
    return 0;
}

static const struct fsnotify_ops ksu_ops = {
    .handle_event = ksu_handle_event,
};
#else
static int ksu_handle_inode_event(struct fsnotify_mark *mark, u32 mask, struct inode *inode, struct inode *dir,
                                  const struct qstr *file_name, u32 cookie)
{
    (void)mark;
    (void)inode;
    (void)dir;
    (void)cookie;
    ksu_check_packages_list(file_name, mask);
    return 0;
}

static const struct fsnotify_ops ksu_ops = {
    .handle_inode_event = ksu_handle_inode_event,
};
#endif"""
    if s4.count(old_impl) == 1:
        s4 = s4.replace(old_impl, new_impl, 1)
        pkg.write_text(s4)
        OK.append("[15-pkg_observer] 4.19 改用 handle_event 适配，功能保留")
    else:
        FAIL.append("[15-pkg_observer] 目标实现未命中: %d" % (s4.count(old_impl),))


# ---------- 16. Ultra 4.19 兼容：TWA_RESUME / path_umount / path_mount ----------
for f in ["drivers/kernelsu/policy/allowlist.c", "drivers/kernelsu/supercall/supercall.c"]:
    fp = pathlib.Path(f)
    if fp.exists():
        s5 = fp.read_text()
        if "define TWA_RESUME" in s5:
            OK.append(f"[16-twa] {f} 已有保护")
        else:
            lines = s5.split("\n")
            idxs = [i for i, l in enumerate(lines) if l.strip().startswith("#include")]
            ins = idxs[-1] + 1 if idxs else 0
            lines[ins:ins] = ["", "#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 8, 0) && !defined(TWA_RESUME)",
                              "#define TWA_RESUME true", "#endif"]
            fp.write_text("\n".join(lines))
            OK.append(f"[16-twa] {f} 加保护宏")
    else:
        OK.append(f"[16-twa] {f} 跳过（不存在）")

sub_optional("drivers/kernelsu/feature/kernel_umount.c",
    "extern int path_umount(struct path *path, int flags);",
    """#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 7, 0)
/* 4.19 has no path_umount(); kern_unmount() is exported */
static int path_umount(struct path *path, int flags) { (void)flags; kern_unmount(path->mnt); return 0; }
#else
extern int path_umount(struct path *path, int flags);
#endif""", 1, "16-path_umount")

sub_optional("drivers/kernelsu/infra/su_mount_ns.c",
    """extern int path_mount(const char *dev_name, struct path *path, const char *type_page, unsigned long flags,
                      void *data_page);""",
    """#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 7, 0)
#include <linux/err.h>
#include <linux/mm.h>

/* 4.19 has no path_mount(); do_mount() takes a path *string* (dir_name), not struct path */
extern long do_mount(const char *dev_name, const char *dir_name, const char *type_page,
                     unsigned long flags, void *data_page);
static inline int path_mount(const char *dev_name, struct path *path, const char *type_page,
                             unsigned long flags, void *data_page)
{
    char *buf, *p;
    int ret;

    buf = (char *)__get_free_page(GFP_KERNEL);
    if (!buf)
        return -ENOMEM;

    p = d_path(path, buf, PAGE_SIZE);
    if (IS_ERR(p)) {
        ret = (int)PTR_ERR(p);
    } else {
        ret = (int)do_mount(dev_name, p, type_page, flags, data_page);
    }
    free_page((unsigned long)buf);
    return ret;
}
#else
extern int path_mount(const char *dev_name, struct path *path, const char *type_page, unsigned long flags,
                      void *data_page);
#endif""", 1, "16-path_mount")

# ---------- 17. Ultra app_profile.c 兼容 4.19 ----------
# 4.19 的 struct seccomp 没有 filter_count（5.9 加 seccomp cache 时才有）
sub_optional("drivers/kernelsu/policy/app_profile.c",
    "    atomic_set(&current->seccomp.filter_count, 0);",
    """#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)
    atomic_set(&current->seccomp.filter_count, 0);
#endif""", 1, "17-seccomp-filter-count")

# ---------- 17. Ultra app_profile.c 兼容 4.19（seccomp.filter_count） ----------
sub_optional("drivers/kernelsu/policy/app_profile.c",
    "    atomic_set(&current->seccomp.filter_count, 0);",
    """#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)
    atomic_set(&current->seccomp.filter_count, 0);
#endif""", 1, "17-filter_count")

# ---------- 18. Ultra cpu_spoof.c 兼容 4.19（vDSO 时钟接口是 5.3+） ----------
sub_optional("drivers/kernelsu/extension/cpu_spoof.c",
    "                {\n                    struct clocksource **curr_cs_ptr =",
    "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 3, 0)\n                {\n                    struct clocksource **curr_cs_ptr =",
    1, "18-vdso-head")
sub_optional("drivers/kernelsu/extension/cpu_spoof.c",
    """                        pr_warn("ksu: set_spoof_cpu failed to resolve 'cpu_hwcaps' / 'system_cpucaps'\\n");
                        ++missing;
                    }
                }""",
    """                        pr_warn("ksu: set_spoof_cpu failed to resolve 'cpu_hwcaps' / 'system_cpucaps'\\n");
                        ++missing;
                    }
                }
#endif /* LINUX_VERSION_CODE < 5.3.0 */""",
    1, "18-vdso-tail")

# ---------- 19. Ultra SELinux 子系统兼容 4.19（selinux_policy 是 5.9+ 才分离出来） ----------
def stub_file(path, anchor, body, label):
    fp = pathlib.Path(path)
    if not fp.exists():
        OK.append(f"[{label}] 跳过：{path} 不存在")
        return
    s6 = fp.read_text()
    if s6.count(anchor) != 1:
        FAIL.append(f"[{label}] anchor 命中数异常: {s6.count(anchor)}")
        return
    s6 = s6.replace(anchor, anchor + "\n\n#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 9, 0)\n" + body + "\n#else", 1)
    s6 = s6.rstrip("\n") + "\n\n#endif /* LINUX_VERSION_CODE < KERNEL_VERSION(5, 9, 0) */\n"
    fp.write_text(s6)
    OK.append(f"[{label}] 4.19 下空实现/跳过")

stub_file("drivers/kernelsu/selinux/rules.c", '#include "xfrm.h"',
    """/* 4.19 keeps policy inside struct selinux_ss; the selinux_policy split exists only from 5.9 */
struct selinux_policy;
struct selinux_policy *backup_sepolicy = NULL;
void apply_kernelsu_rules(void) { }
int handle_sepolicy(void __user *user_data, u64 data_len) { (void)user_data; (void)data_len; return -EINVAL; }""",
    "19-rules")

stub_file("drivers/kernelsu/feature/selinux_hide.c", '#include "ksu.h"',
    """/* 4.19: selinux_policy split does not exist, hide feature disabled */
void ksu_selinux_hide_init(void) { }
void ksu_selinux_hide_exit(void) { }
void ksu_selinux_hide_drop_backup_if_unused(void) { }
void ksu_selinux_hide_handle_second_stage(void) { }
void ksu_selinux_hide_handle_post_fs_data(void) { }""",
    "19-selinux_hide")

stub_file("drivers/kernelsu/selinux/sepolicy.c", '#include "ss/symtab.h"',
    """/* 4.19: sepolicy helpers are unused once rules.c and selinux_hide.c are stubbed */""",
    "19-sepolicy")

# ---------- 20. sulog 引用 5.0+ 才有的 linux/minmax.h ----------
sub_optional("drivers/kernelsu/sulog/event.c",
    '#include <linux/minmax.h>',
    '#include <linux/kernel.h>',
    1, "20-sulog-minmax")

# ---------- 21. 链接期未定义符号：seccomp_filter_release（5.9+）+ nidhi SUSFS 期望的 3 个符号 ----------
sub_optional("drivers/kernelsu/policy/app_profile.c",
    "void seccomp_filter_release(struct task_struct *tsk);",
    "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)\nvoid seccomp_filter_release(struct task_struct *tsk);\n#endif",
    1, "21-seccomp-decl")

sub_optional("drivers/kernelsu/policy/app_profile.c",
    "    seccomp_filter_release(fake);",
    "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)\n    seccomp_filter_release(fake);\n#endif",
    1, "21-seccomp-call")

fp = pathlib.Path("drivers/kernelsu/core/init.c")
if fp.exists():
    s21 = fp.read_text()
    if "susfs_is_current_ksu_domain" not in s21:
        s21 = s21.rstrip("\n") + """

#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 9, 0)
/* nidhi SUSFS expects these from the KSU side; Ultra does not provide them */
bool susfs_is_current_ksu_domain(void) { return false; }
unsigned int susfs_ksu_sid = 0;
unsigned int susfs_priv_app_sid = 0;
#endif
"""
        fp.write_text(s21)
        OK.append("[21-susfs-sym] 4.19 下补 3 个空实现符号")
    else:
        OK.append("[21-susfs-sym] 已存在，跳过")

# ---------- 22. 打开 KPM（config KPM 是 default n，且 select KALLSYMS_ALL） ----------
add_config("arch/arm64/configs/vendor/xiaomi/magictime-common.config",
           "CONFIG_KPM=y", label="22-KPM")

# ---------- 23. KPM: access_ok 4.19 需要三参数 ----------
sub("KernelSU/kernel/extension/kpm/kpm.c",
    "if (!access_ok(u64_to_user_ptr(cmd.result_code), sizeof(result))) return -EFAULT;\n",
    "#if LINUX_VERSION_CODE < KERNEL_VERSION(5,0,0)\n"
    "    if (!access_ok(VERIFY_WRITE, u64_to_user_ptr(cmd.result_code), sizeof(result)))\n"
    "        return -EFAULT;\n"
    "#else\n"
    "    if (!access_ok(u64_to_user_ptr(cmd.result_code), sizeof(result)))\n"
    "        return -EFAULT;\n"
    "#endif\n",
    label="23-KPM-access_ok")

# ---------- 23b. KPM: 补 linux/version.h 以定义 KERNEL_VERSION ----------
sub("KernelSU/kernel/extension/kpm/kpm.c",
    "#include <linux/uaccess.h>\n",
    "#include <linux/uaccess.h>\n#include <linux/version.h>\n",
    label="23b-KPM-version-h")

print("=" * 60)
for k in OK: print("OK  ", k)
for f in FAIL: print("FAIL", f)
print("=" * 60)
if FAIL:
    print(f"共 {len(FAIL)} 处失败，终止")
    sys.exit(1)
print(f"全部通过（{len(OK)} 项）")
