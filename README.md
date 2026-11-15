# kernel-lmi

红米 K30 Pro（`lmi`）的 4.19.325 自编译内核 —— 内置 KernelSU 变体、SUSFS 隐藏、KPM 扩展。

**作者：QW351784**

---

## 这是给哪台机器用的

| 项 | 值 |
|---|---|
| 机型 | Redmi K30 Pro |
| 代号 | `lmi` |
| 平台 | 高通 SM8250（骁龙 865） |
| 刷入分区 | `boot`（`/dev/block/bootdevice/by-name/boot`） |

只认 `lmi`。刷机脚本里有 `do.devicecheck=1` + `device.name1=lmi`，别的机型会直接拦下不刷。

## 内核是什么

**基线**：nidhi 4.19.325（`kaixenberg/kernel_xiaomi_sm8250`）。作者官方只列 alioth / apollo / pipa，lmi 不在支持范围，得自己验。

**长期维护补丁（CIP）**：

- v1.0 ~ v1.5 用的是 **cip127**，走作者早前的 GitLab `android16-aptusitu` 分支
- v1.6 换代到作者的 GitHub `nidhi` 分支，作者本人已经把 CIP 从 cip127 上移到 **cip136**
- 这一步跨了 9 个 CIP 小版本，net / fs / drivers 等 1700+ 文件跟着更新，和内核的 `localversion-cip=-cip136`、`localversion-st=-st20` 对得上
- v1.6 之后一直停在 cip136，没有再往上走

**工具链（换了三次）**：

- v1.0 ~ v1.1：**ZyC clang 15.0.7** + GNU ld
- v1.2：还是 ZyC clang 15.0.7，这版动的是 LTO，不是工具链
- v1.3：ZyC clang **16.0.6-20260807**
- v1.4 起：**Neutron clang 24.0.0git**（06092026）+ Neutron LLD 24.0.0，一直用到现在的 v1.9 和修复版
- 从 15 到 24，跨了 8 个 LLVM 大版本

**编译优化**：

- v1.0 ~ v1.3：**LTO 是关的**。从包里的 Image 抠出来的 config 写的是 `CONFIG_LTO_NONE=y`；v1.0 / v1.1 的 Image 53.8 MB，v1.2 / v1.3 是 47.5 MB。LTO 一关，`CFI_CLANG` 因为依赖 LTO 也跟着自动关掉了，所以这四个版本压根没有 CFI 校验这回事，自然不会有卡 fastboot 的问题
- v1.4 起把 **thin LTO** 打开（`CONFIG_LTO_CLANG=y` + `CONFIG_THINLTO=y`），`CFI_CLANG` 跟着回来了，Image 落在 51.4 MB 上下
- v1.6 那版 Image 一度涨到 57.7 MB（thin + CFI，加上调度器换成 EEVDF 之后编译单元变大）
- **修复版（v1.4 起重编）**：thin LTO 保留，但**关掉 `CFI_CLANG` 和 `SHADOW_CALL_STACK`**。原因是 clang 24 出的是 KCFI 新格式，4.19 内核里的 CFI 运行时还是老格式，对不上会在启动早期跳转校验失败，表现就是刷进去了卡在 fastboot。这六个包都解出来验过，Image 里明确是 `# CONFIG_CFI_CLANG is not set`
- v1.9 单独走 **full LTO**（显式 `# CONFIG_THINLTO is not set`）+ 单线程。之前一版漏了这行显式关闭，Kconfig 的默认 y 又把它选回来，实际跑成了 thin，是后来查 Image 里的 config 才发现并修掉的

**版本串差异**：v1.0 ~ v1.5 版本串是 `Nidhi-1.2.5`，v1.6 起变 `Nidhi-1.3.0`。

**当前版本串**：`4.19.325-Nidhi-1.3.0-97de058-cip136 SMP preempt mod_unload modversions aarch64`

**构建环境**：GitHub Actions，`ubuntu-24.04`，`JOBS=2`（免费 runner 只有 2 核，开 4 反而互相抢核）

## 带的东西

### Root

**管理器换过三代**：

- **v1.0**：内置 BakaSU v4.2.0-rc3，但没打 manual hook，root 编进去了却不工作
- **v1.1 ~ v1.5**：还是 BakaSU，v1.1 补了 5 处 manual hook 之后 root 才真正能用
- **v1.6**：换成作者内置的 **backslashxx KernelSU**（version code 32725），管理器得配 backslashxx 版或 KOWX712 版
- **v1.7**：换成 **SukiSU-Ultra**，第一次在 4.19 上编得过，代价是 `pkg_observer` 和 `seccomp_cache` 只是空实现
- **v1.8**：Ultra **41179**，同时 `CONFIG_KPM=y` 真正打开，`strings Image` 里能看到 `KPM is built in`
- **v1.9**：Ultra **41180**，修好 `do_mount` 与 `handle_event`，包名观察恢复，KPM 仍然 built in

**KPM**：v1.0 ~ v1.7 都没真正启用，v1.8 起才打开。为这个改了三处 4.19 兼容：`access_ok()` 的三参数形式、补 `linux/version.h`、整行替换避免括号不配对。

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

谢谢下面这些团队的支持：

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

---

**酷安作者账号：QW123456780**

---

### 支持作者

作者制作维护不容易，爱心捐款，一杯奶茶价钱，就是作者继续维护更新的动力。

<img src="docs/wechat-qrcode.webp" alt="微信赞赏码" width="240">
