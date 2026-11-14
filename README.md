# kernel-lmi

红米 K30 Pro（`lmi`）的 4.19.325 自编译内核 —— 内置 KernelSU 变体、SUSFS 隐藏、KPM 扩展。

**作者：QW351784** · https://github.com/QW351784

---

## 这是给哪台机器用的

| 项 | 值 |
|---|---|
| 机型 | Redmi K30 Pro |
| 代号 | `lmi` |
| 平台 | 高通 SM8250（骁龙 865） |
| 系统 | MIUI（AOSP 版另有一份包） |
| 刷入分区 | `boot`（`/dev/block/bootdevice/by-name/boot`） |

只认 `lmi`。刷机脚本里有 `do.devicecheck=1` + `device.name1=lmi`，别的机型会直接拦下不刷。

## 内核是什么

- **基线**：nidhi 4.19.325（`kaixenberg/kernel_xiaomi_sm8250`）
- **长期维护补丁**：CIP `cip136`
- **当前版本串**：`4.19.325-Nidhi-1.3.0-e9f0f7d-cip136 SMP preempt mod_unload modversions aarch64`
- **工具链**：Neutron clang 24.0.0git + Neutron LLD 24.0.0
- **编译优化**：thin LTO（`LTO_CLANG_THIN`），保留 `DEBUG_INFO`
- **构建环境**：GitHub Actions，`ubuntu-24.04`，`JOBS=4`

## 带的东西

### Root

- **SukiSU-Ultra** 41180（包名 `com.sukisu.ultra`），不是原版 KernelSU
- **KPM** 真正启用，刷完在管理器里能看到 `KPM is built in`

> 管理器版本低于 41180 会提示「需要更新内核」，那是管理器旧了，不是内核坏了。

### 隐藏

- **SUSFS** 开启（`KSU_SUSFS`），日志输出已关闭

### 关键修补（4.19 专属，5.x 的写法在这里全不成立）

1. `do_mount()` —— 4.19 第二个参数是路径字符串，不是 `struct path *`（`path_mount` 是 5.7 才有）。改用 `d_path()` 转换后再调，`MS_PRIVATE | MS_REC` 才真正生效，之前是静默失败。
2. `fsnotify_ops.handle_event` —— 4.19 的 `file_name` 是 `const unsigned char *`，不是 `struct qstr *`（改 qstr 是 5.9）。在函数内构造 `struct qstr` 再判断，包名观察才不是空壳。

### 其它

- `PANIC_TIMEOUT=5`
- 输入提升（`input_boost_ms` / `input_boost_freq`）
- 充电功率与 DCP 电流调整
- `MODULE_IMPORT_NS` 适配、seccomp 与 SELinux 相关改动

## 打包方式

**AnyKernel3**，不是整包镜像。

- 结构：`anykernel.sh` + `META-INF/com/google/android/` + `tools/`（`magiskboot`、`busybox`）+ `kernels/`
- 只替换 `boot`，不动 `system`、不动 `vendor`
- Recovery 直接刷（TWRP / OrangeFox 都行）
- `kernel.string` 内容：`NidhiKernel 4.19.325-Nidhi-1.3.0-e9f0f7d-cip136 (miui, lmi)`
- 包内 `banner` 末尾：`Build by QW351784 · github.com/QW351784`


## 怎么刷

1. **先备份 boot**（Recovery 备份，或 `dd if=/dev/block/bootdevice/by-name/boot`）
2. Recovery 里 install 这个 zip
3. 重启

出问题刷回备份的 boot 就行，不会变砖。

## 版本

`Releases` 里从 `v1.0` 到最新的 build 一共 10 个版本，越往后越稳，挑最新的下。

每个版本的说明都按七项写：**性能 / 安全 / 稳定 / 功能 / 兼容性 / 功耗耗电 / 发热**。没实测的标没实测，不编数字。

## 已知限制

- **最新版没有在真机上刷过**，能不能开机、KPM 是否实际可用，需要自己验证
- 每个 release 说明里都单独列了未验证项
- 4.19 是老内核，新硬件特性和新版 Android 的部分机制不支持

## 作者

**QW351784**

全部改动在 `patch_kernel.py`，构建流程在 `.github/workflows/build.yml`，都是公开的，可以自己看。

## 借鉴与致谢

这个项目不是从零做出来的，底子全是别人的。每一条都写明了**借谁、在哪、借了什么**：

- **nidhi 4.19.325 内核基线** — kaixenberg · https://github.com/kaixenberg/kernel_xiaomi_sm8250
- **CIP cip136 长期维护补丁** — CIP 团队 · https://git.kernel.org/pub/scm/linux/kernel/git/cip/linux-cip.git
- **SukiSU-Ultra**（内置 root 与 KPM）— https://github.com/SukiSU-Ultra/SukiSU-Ultra
- **KernelSU 上游** — tiann · https://github.com/tiann/KernelSU
- **SUSFS**（痕迹隐藏）— sidex15 · https://github.com/sidex15/susfs4ksu-module
- **Neutron clang**（工具链）— https://github.com/Neutron-Toolchains/clang-build-catalogue
- **AnyKernel3**（刷机包框架）— osm0sis · https://github.com/osm0sis/AnyKernel3
- **MagicTime**（刷入 banner 版式）— TIMISONG-dev

完整的「借了什么 / 用在哪 / 致谢」在 [CREDITS.md](CREDITS.md)。

漏了谁、写错了谁，提 issue，我立刻补上。
