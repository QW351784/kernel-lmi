#!/usr/bin/env python3
"""适配 BakaSU v4.2.0-rc3 的 manual_hook 集成要求（源码是旧 SUSFS 内联钩子）"""
import sys, os

src = sys.argv[1] if len(sys.argv) > 1 else "kernel"
changes = []

# 1) fs/read_write.c —— 删除 BakaSU 已不提供的旧 bool 钩子，保留无条件调用
p = os.path.join(src, "fs/read_write.c")
s = open(p).read()
old_ext = """#ifdef CONFIG_KSU
extern bool ksu_vfs_read_hook __read_mostly;
extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd,
				char __user **buf_ptr, size_t *count_ptr);
#endif"""
new_ext = """#ifdef CONFIG_KSU
extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd,
				char __user **buf_ptr, size_t *count_ptr);
#endif"""
if old_ext in s:
    s = s.replace(old_ext, new_ext, 1)
    changes.append("read_write.c: 移除 ksu_vfs_read_hook extern")

old_call = """#ifdef CONFIG_KSU
	if (unlikely(ksu_vfs_read_hook)) 
		ksu_handle_sys_read(fd, &buf, &count);
#endif"""
new_call = """#ifdef CONFIG_KSU
	ksu_handle_sys_read(fd, &buf, &count);
#endif"""
if old_call in s:
    s = s.replace(old_call, new_call, 1)
    changes.append("read_write.c: 调用改为无条件")
if "ksu_vfs_read_hook" in s:
    print("[WARN] read_write.c 仍残留 ksu_vfs_read_hook")
open(p, "w").write(s)

# 2) fs/stat.c —— 补 newfstat_ret / fstat64_ret 钩子
p = os.path.join(src, "fs/stat.c")
s = open(p).read()

old_newfstat = """SYSCALL_DEFINE2(newfstat, unsigned int, fd, struct stat __user *, statbuf)
{
	struct kstat stat;
	int error = vfs_fstat(fd, &stat);

	if (!error)
		error = cp_new_stat(&stat, statbuf);

	return error;
}"""
new_newfstat = """SYSCALL_DEFINE2(newfstat, unsigned int, fd, struct stat __user *, statbuf)
{
	struct kstat stat;
	int error = vfs_fstat(fd, &stat);

	if (!error)
		error = cp_new_stat(&stat, statbuf);

#ifdef CONFIG_KSU
	extern void ksu_handle_newfstat_ret(unsigned int *fd, struct stat __user **statbuf_ptr);
	ksu_handle_newfstat_ret(&fd, &statbuf);
#endif
	return error;
}"""
if old_newfstat in s:
    s = s.replace(old_newfstat, new_newfstat, 1)
    changes.append("stat.c: 增加 newfstat_ret 钩子")
else:
    print("[WARN] newfstat 函数体未精确匹配")

old_fstat64 = """SYSCALL_DEFINE2(fstat64, unsigned long, fd, struct stat64 __user *, statbuf)
{
	struct kstat stat;
	int error = vfs_fstat(fd, &stat);

	if (!error)
		error = cp_new_stat64(&stat, statbuf);

	return error;
}"""
new_fstat64 = """SYSCALL_DEFINE2(fstat64, unsigned long, fd, struct stat64 __user *, statbuf)
{
	struct kstat stat;
	int error = vfs_fstat(fd, &stat);

	if (!error)
		error = cp_new_stat64(&stat, statbuf);

#ifdef CONFIG_KSU
	extern void ksu_handle_fstat64_ret(unsigned long *fd, struct stat64 __user **statbuf_ptr);
	ksu_handle_fstat64_ret(&fd, &statbuf);
#endif
	return error;
}"""
if old_fstat64 in s:
    s = s.replace(old_fstat64, new_fstat64, 1)
    changes.append("stat.c: 增加 fstat64_ret 钩子")
else:
    print("[WARN] fstat64 函数体未精确匹配")
open(p, "w").write(s)

# 3) build.sh —— KSU 配置切到 manual hook，并关闭旧 SUSFS 内联
p = os.path.join(src, "build.sh")
s = open(p).read()
anchor = 'echo "MIUI-specific configs applied" >> "$LOG_FILE"'
if anchor not in s:
    print("[ERR] build.sh 锚点未找到")
    sys.exit(1)

ksu_cfg = '''
  # === BakaSU manual hook 集成 ===
  scripts/config --file out/.config \\
    -e KSU \\
    -e KSU_MANUAL_HOOK \\
    -e KSU_MANUAL_HOOK_AUTO_SETUID_HOOK \\
    -e KSU_MANUAL_HOOK_AUTO_INITRC_HOOK \\
    -e KSU_MANUAL_HOOK_AUTO_INPUT_HOOK \\
    -d KSU_SUSFS
  echo "BakaSU manual hook config applied" >> "$LOG_FILE"
'''
if "BakaSU manual hook 集成" not in s:
    s = s.replace(anchor, anchor + "\n" + ksu_cfg, 1)
    changes.append("build.sh: 注入 manual hook 配置")
open(p, "w").write(s)

print("=== 变更 ===")
for c in changes:
    print(" -", c)
print("总计:", len(changes), "处")
