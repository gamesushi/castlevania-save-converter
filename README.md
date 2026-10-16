# Castlevania: Belmont's Curse — PC ↔ Switch ↔ PS5 Save Converter

《恶魔城：贝尔蒙特的诅咒》多平台存档互转工具。PC / Switch / PS5 三端存档内部均为
Unity 导出的**明文 JSON**，schema 在已知版本（1.1.0 / 1.1.1）间 100% 一致，因此
互转在数据层等于"搬文件 + 对齐版本号 + 调整文件名约定"。

> 该游戏 2026-10-15 全平台发售（PC / Switch / PS5 / Xbox），本工具覆盖 PC / Switch / PS5 三向。

## 三个平台的关键差异

| 项 | PC | Switch | PS5 |
|---|---|---|---|
| 文件名 | `BuildSave_1.sav`（带 `.sav`，槽位从 1） | `BuildSave_0`（无扩展名，槽位从 0） | 待校准（暂按 `.sav` 假设） |
| 版本号 | 实测 `1.1.1` | 实测 `1.1.0` | 待校准（未知） |
| 容器 | 直接读写文件 | 系统级加密容器，需破解机 + Checkpoint 解密 dump / restore | 主机级加密，需破解机 + Apollo Save Tool / Save Mounter 解密并重新签名 |

Switch 与 PS5 存档容器都是加密的，本工具只处理**解密后的内部 JSON**；真正的写回主机
（restore / 重新签名注入）要在对应主机上用上述工具完成。

> ⚠️ **PS5 尚未用真实样本校准**：目前 PS5 的文件名约定与版本号均为合理假设，转换后请
> 务必在主机上验证存档可被读取。如有 PS5 解密 dump，发我即可校准 `PLATFORMS["ps5"]`。

> 📌 **扩展名速记**：PC 存档是 `BuildSave_N.sav`（**带 `.sav`**），Switch 存档是 `BuildSave_N`（**无扩展名**）。
> `--target pc` 产出 `.sav`，`--target switch` 产出无扩展名文件——二者都正确，取决于你要在哪台机器上用。
> **不要把 `.sav` 删掉后缀再喂给 Checkpoint（Switch 工具）**，那是反方向、无效的操作；要放回 Switch 请直接用 `--target switch` 生成无扩展名文件。

## 功能

- **解析 / 校验**：结构校验，输出可读进度摘要（等级、装备、Arcana 塔罗、探索房间、
  世界进度、进度板）。
- **无损往返**：不做任何改动时**逐字节原样复制**，绝不破坏存档。
- **平台转换**：`--target pc|switch|ps5` 决定输出文件名约定（PC=`.sav` / Switch=无扩展名 / PS5=`.sav`）。
  版本号默认**自动对齐**目标平台参考版本（PC=1.1.1 / Switch=1.1.0），仍可用 `--set-version` 强制覆盖。
- **DLC 独占剥离**：`--strip` 可按子串剔除目标平台无授权的内容（如预购皮肤）。
- **国际化**：网页工具内置 中文 / English / 日本語，默认跟随浏览器语言并记忆选择。

## CLI 用法

```bash
# 校验 + 进度摘要（不写盘）
python3 cc_convert.py samples/switch_BuildSave_0 --report

# Switch 存档 → PC（版本默认自动对齐到 1.1.1，无需再写 --set-version）
python3 cc_convert.py samples/switch_BuildSave_0 --target pc --out out_pc/BuildSave_1.sav

# 若你的 PC 游戏仍是旧版 1.1.0、想强制保持，可显式指定：
python3 cc_convert.py samples/switch_BuildSave_0 --target pc --set-version 1.1.0 \
    --out out_pc/BuildSave_1.sav

# PC → Switch（仅作数据备份 / 待主机 restore）
python3 cc_convert.py samples/pc_BuildSave_1.sav --target switch --out BuildSave_0

# Switch / PC 存档 → PS5（⚠️ 未校准:文件名/版本为假设,转换后需在主机验证）
python3 cc_convert.py samples/switch_BuildSave_0 --target ps5 --set-version 1.1.1 \
    --out BuildSave_1.sav

# 剥离目标平台无授权的独占皮肤
python3 cc_convert.py pc.sav --strip Skin_MC_Alucard,Skin_MC_Trevor --out out.sav
```

### 参数

| 参数 | 说明 |
|---|---|
| `input` | `.sav` 文件 或 Checkpoint dump 目录（递归找所有存档） |
| `--target {pc,switch,ps5}` | 目标平台，**仅决定文件名约定**（PS5 为未校准假设） |
| `--set-version X.Y.Z` | 强制写回的版本号；**不传则默认对齐目标平台参考版本**（PC=1.1.1 / Switch=1.1.0），可用于覆盖 |
| `--strip a,b` | 逗号分隔的 item 子串，匹配则剥离 |
| `--out` / `--out-dir` | 单文件 / 目录镜像输出 |
| `--report` | 仅打印校验 + 摘要 |

## 网页工具

`web/index.html` 是纯浏览器离线工具，拖入 `.sav`（或 Switch 无扩展名文件）即可：
校验、看进度、选目标平台 + 版本号、下载转换结果。**无需任何环境，可直接分发给朋友。**

## Switch 端操作流程（需破解机）

1. Switch 上 Checkpoint → Backup《恶魔城：贝尔蒙特的诅咒》→ 导出到 SD
   `/switch/Checkpoint/saves/<Title>/<时间戳>/`
2. 把该文件夹拷到电脑，跑上面的命令
3. 生成的文件**改名回 `BuildSave_0` / `BuildSave_1`** 放回原槽位目录
4. Switch 上 Checkpoint → Restore

> ⚠️ 文件名必须是 `BuildSave_0` / `BuildSave_1`（**无 `.sav` 后缀**）；版本号现已默认对齐 1.1.0，
> 一般无需手动处理。若游戏仍拒读，用 `--set-version` 对齐。（注：存档内 `PLAYERPREFS` 含 `transfer_save_done=1`，
> 说明游戏自带存档转移机制，建议优先试官方转移，本工具作离线兜底。）

## 已知风险

- **版本漂移**：PC 1.1.1 与 Switch 1.0.x 字段可能不一致，游戏或拒读 → 用 `--set-version` 对齐。
- **DLC 独占**：若存档含目标平台未购买的皮肤 / 魔导器，可能隐藏或异常 → 转换时可 `--strip`。
- **PS5 未校准**：`PLATFORMS["ps5"]` 的文件名 / 版本均为假设（基于"三端同款 Unity JSON"推断），
  尚无真实 PS5 解密样本验证。转换结果请务必在主机上确认可读。
- **Switch / PS5 落地**：无破解机 = 无法真正写回对应主机（官方云存档不跨平台还原；PS5 还需
  Apollo Save Tool / Save Mounter 重新签名）。

## 文件结构

```
castlevania_save.py   # 核心：解析 / 校验 / 摘要 / 清洗 / 落盘
cc_convert.py         # CLI 入口
web/index.html        # 离线网页工具（含 i18n）
samples/              # 样本存档（PC 1.1.1 + Switch 1.1.0 + PLAYERPREFS）
```

## 免责声明

存档转换有风险，操作前请备份原文件。本工具按"忠实搬运 + 最小可枚举改动"原则设计，
不对因使用本工具导致的任何进度丢失负责。
