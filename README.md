# Castlevania: Belmont's Curse — PC ↔ Switch Save Converter

《恶魔城：贝尔蒙特的诅咒》多平台存档互转工具。PC 版与 Switch 版存档内部均为
Unity 导出的**明文 JSON**，schema 在已知版本（1.1.0 / 1.1.1）间 100% 一致，因此
互转在数据层等于"搬文件 + 对齐版本号 + 调整文件名约定"。

> 该游戏 2026-10-15 全平台发售（PC / Switch / PS5 / Xbox），本工具覆盖 PC 与 Switch 双向。

## 两个平台的关键差异

| 项 | PC | Switch |
|---|---|---|
| 文件名 | `BuildSave_1.sav`（带 `.sav`，槽位从 1） | `BuildSave_0`（无扩展名，槽位从 0） |
| 版本号 | 实测 `1.1.1` | 实测 `1.1.0` |
| 容器 | 直接读写文件 | 系统级加密容器，需破解机 + Checkpoint 解密 dump / restore |

Switch 存档容器是系统级加密，本工具只处理**解密后的 dump**；真正的写回主机
（restore）要在 Switch 上用 Checkpoint / JKSV 完成。

## 功能

- **解析 / 校验**：结构校验，输出可读进度摘要（等级、装备、Arcana 塔罗、探索房间、
  世界进度、进度板）。
- **无损往返**：不做任何改动时**逐字节原样复制**，绝不破坏存档。
- **平台转换**：`--target pc|switch` 只改文件名约定；`--set-version` 独立指定版本号，
  两者互不绑定。
- **DLC 独占剥离**：`--strip` 可按子串剔除目标平台无授权的内容（如预购皮肤）。
- **国际化**：网页工具内置 中文 / English / 日本語，默认跟随浏览器语言并记忆选择。

## CLI 用法

```bash
# 校验 + 进度摘要（不写盘）
python3 cc_convert.py samples/switch_BuildSave_0 --report

# Switch 存档 → PC（自动对齐版本到 1.1.1，仅改名 + 改扩展名）
python3 cc_convert.py samples/switch_BuildSave_0 --target pc --set-version 1.1.1 \
    --out out_pc/BuildSave_1.sav

# PC → Switch（仅作数据备份 / 待主机 restore）
python3 cc_convert.py samples/pc_BuildSave_1.sav --target switch --out BuildSave_0

# 剥离目标平台无授权的独占皮肤
python3 cc_convert.py pc.sav --strip Skin_MC_Alucard,Skin_MC_Trevor --out out.sav
```

### 参数

| 参数 | 说明 |
|---|---|
| `input` | `.sav` 文件 或 Checkpoint dump 目录（递归找所有存档） |
| `--target {pc,switch}` | 目标平台，**仅决定文件名约定** |
| `--set-version X.Y.Z` | 强制写回的版本号（与平台独立），不传则保留原版本 |
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

> ⚠️ 文件名必须是 `BuildSave_0` / `BuildSave_1`；若版本漂移导致游戏拒读，用
> `--set-version` 对齐。（注：存档内 `PLAYERPREFS` 含 `transfer_save_done=1`，
> 说明游戏自带存档转移机制，建议优先试官方转移，本工具作离线兜底。）

## 已知风险

- **版本漂移**：PC 1.1.1 与 Switch 1.0.x 字段可能不一致，游戏或拒读 → 用 `--set-version` 对齐。
- **DLC 独占**：若存档含目标平台未购买的皮肤 / 魔导器，可能隐藏或异常 → 转换时可 `--strip`。
- **Switch 落地**：无破解机 = 无法真正写回 Switch（官方云存档不跨平台还原）。

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
