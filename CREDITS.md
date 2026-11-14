# 致谢与借鉴来源 / Credits & Acknowledgements

本仓库（`kernel-lmi`，红米 K30 Pro「lmi」自编译内核）的工作建立在一批开源项目之上。
下面逐条写明**借鉴了谁、他的位置（仓库地址）、借鉴的具体内容，以及致谢**。
刷机包的 `banner` 与 `kernel.string` 里也同步标注了这些来源。

---

## 一、内核基线

### 1. kernel_xiaomi_sm8250（nidhi 分支）
- **作者 / 位置**：https://github.com/kaixenberg/kernel_xiaomi_sm8250
- **借鉴内容**：整棵 4.19.325 内核源码基线；内核版本串里的 `Nidhi` 就来自这里。
- **致谢**：感谢 kaixenberg 维护的 nidhi 内核，本项目的全部改动都是在它的基础上打补丁，没有这份源码就没有这个项目。

### 2. CIP（Civil Infrastructure Platform）
- **作者 / 位置**：https://git.kernel.org/pub/scm/linux/kernel/git/cip/linux-cip.git
- **借鉴内容**：`cip136` 长期维护补丁（版本串后缀 `-cip136`）。
- **致谢**：感谢 CIP 团队持续为 4.19 提供安全与稳定性回补，这是这颗老内核还能日常使用的重要原因。

---

## 二、Root 与隐藏

### 3. SukiSU-Ultra
- **作者 / 位置**：https://github.com/SukiSU-Ultra/SukiSU-Ultra
- **借鉴内容**：内置的 KernelSU 变体（`com.sukisu.ultra`）、KPM 扩展模块（`extension/kpm`）。
- **致谢**：感谢 SukiSU-Ultra 团队。本项目在 4.19 上做的 `su_mount_ns`、`pkg_observer` 等兼容修补，都是围绕着他们的代码进行的。

### 4. KernelSU（上游）
- **作者 / 位置**：https://github.com/tiann/KernelSU
- **借鉴内容**：KernelSU 的原始实现，SukiSU-Ultra 亦源自此。
- **致谢**：感谢 tiann 及其贡献者创造了 KernelSU 这套内核级 root 方案。

### 5. SUSFS（susfs4ksu）
- **作者 / 位置**：https://github.com/sidex15/susfs4ksu-module
- **借鉴内容**：root 痕迹隐藏（Suspicious Files System），本内核编译时开启 `KSU_SUSFS`，并关闭其日志输出。
- **致谢**：感谢 sidex15 的 susfs4ksu 项目，它在隐藏效果上是目前最实用的一套。

---

## 三、编译与打包

### 6. Neutron clang
- **作者 / 位置**：https://github.com/Neutron-Toolchains/clang-build-catalogue
- **借鉴内容**：编译工具链（Neutron clang 24.0.0git / Neutron LLD 24.0.0），下载地址见 `.github/workflows/build.yml`。
- **致谢**：感谢 Neutron-Toolchains 团队持续产出针对内核优化的 LLVM 工具链，性能优化的很大一部分来自它的 O3/LTO/BOLT/Polly 构建。

### 7. AnyKernel3
- **作者 / 位置**：https://github.com/osm0sis/AnyKernel3
- **借鉴内容**：刷机包框架——`anykernel.sh`、`META-INF`、`tools/`（`magiskboot`、`busybox` 等）。
- **致谢**：感谢 osm0sis 与 AnyKernel3 的所有贡献者。没有它，就没有这种"不碰 system、只换 boot"的安全刷入方式。

### 8. MagicTime
- **作者 / 位置**：TIMISONG-dev（署名保留在刷机包 `banner` 中：`Based on MagicTime by TIMISONG-dev`）
- **借鉴内容**：刷入界面 banner 的版式设计。
- **致谢**：感谢 TIMISONG-dev 的 MagicTime 项目提供的 banner 模板。

---

## 四、本项目自身

- **作者**：QW351784 · https://github.com/QW351784
- **本仓库**：https://github.com/QW351784/kernel-lmi
- **改动补丁**：`patch_kernel.py`
- **构建流程**：`.github/workflows/build.yml`
- **刷机包署名**：`banner` 末尾 `Build by QW351784 · github.com/QW351784`；`anykernel.sh` 的 `kernel.string` 末尾 `by QW351784`

---

## 五、最后

以上每一位作者的工作都是公开可见的。如果这里漏了谁、或者署名写错了，请提 issue，我会立刻更正并补上致谢——**该谢的人一个都不能少**。
