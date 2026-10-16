"""
Castlevania: Belmont's Curse — PC <-> Switch 存档工具核心
=================================================================
存档本质:Unity 导出的明文 JSON(文件头 {"version":"...",...})。
PC 与 Switch(Untiy)内部写入存档容器的,极大概率是同一套 JSON;
真正的难点在 Switch 存档容器的系统级加密 —— 那一步在主机的
Checkpoint / JKSV 里 dump / restore,本工具只处理"已解密"的 .sav。

设计原则(防破坏存档):
  * 忠实往返:加载后尽量按原貌写回(紧凑无空格分隔符)。
  * m_keys/m_values 是 Unity 字典的并行数组序列化,原样保留。
  * worldRoomExplorationStates / arcanaTaskStates 等的 m_values 是
    "被字符串化的 JSON"(如 "{\"hitCount\":20}"),它们是字符串,
    不是对象 —— 绝不能当 JSON 二次解析,否则会破坏结构。
  * 所有"转换"都是最小、可枚举的改动;默认纯身份往返 + 校验 + 摘要。
=================================================================
"""
from __future__ import annotations
import json
import os
import glob
import re

# ---- 期望结构(用于校验/告警,缺字段只告警不报错,避免误杀) -----------------

EXPECTED_TOP_KEYS = ["version", "playerSave", "worldSaves", "progressionBoardSave"]

REQUIRED_PLAYER_KEYS = [
    "id", "saveDate", "playTimeInSeconds", "levelId", "position",
    "level", "experienceCurrent", "currentHealth", "currentMana",
    "equippedWeaponItem", "equippedSpellItem", "equippedSkin",
    "itemsInInventory", "equippedCharmItems",
]

# 已观测版本(均来自真实样本,已确认 schema 100% 一致):
#   PC 样本   = 1.1.1  (文件 BuildSave_1.sav)
#   Switch 样本 = 1.1.0 (Checkpoint dump 的 BuildSave_0,无扩展名)
# 两个版本 playerSave 的 79 个键完全相同,worldSaves / progressionBoardSave
# 结构也一致,因此跨版本搬运是纯元数据对齐,无数据风险。
KNOWN_VERSIONS = {"1.1.0", "1.1.1"}

PC_REF_VERSION = "1.1.1"
SWITCH_REF_VERSION = "1.1.0"

# 平台文件名约定(实测):
#   Switch (Checkpoint dump): BuildSave_0, BuildSave_1, ...  ← 无扩展名,槽位从 0 起
#   PC     (Steam/PC 存档目录): BuildSave_1.sav, BuildSave_2.sav, ... ← .sav 扩展名,槽位从 1 起
# 槽位数字本身只代表"第几个存档槽",PC 与 Switch 各自独立;转换时保留原数字,
# 仅切换扩展名,目标槽位由用户用 --out / --slot 指定。

# 预购/午夜版独占皮肤(待游戏内确认,默认不剥离)。
# 注:Switch 与 PC 样本里 equippedSkin 都是 Skin_MC_Alucard,说明它至少是
# 通用解锁皮肤而非强制独占 —— 是否 DLC 独占需你在游戏内核实后再决定是否剥离。
ASSUMED_DLC_SKINS = [
    "Skin_MC_Alucard",   # 预购/DLC Alucard 风格(待确认)
    "Skin_MC_Trevor",    # 预购/DLC Trevor 风格(待确认)
    "Skin_MC_Sypha",     # 预购/DLC Sypha 风格(待确认)
]


# ---- 加载 ---------------------------------------------------------------

def _find_sav_files(path: str):
    """返回 path 下所有 .sav(递归)。path 是文件则直接返回它本身。"""
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "**", "*.sav"), recursive=True))
        return files
    return [path]


def load(path: str):
    """加载单个 .sav 为 Python 对象。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_raw(path: str):
    """返回 (原始文本, 解析后的对象)。保留原始字节以便无改动时逐字节复制。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return text, json.loads(text)


def load_any(path: str):
    """path 可为文件或目录(Checkpoint dump)。返回 [(path, raw_text, data), ...]。"""
    out = []
    for fp in _find_sav_files(path):
        try:
            raw, data = load_raw(fp)
            out.append((fp, raw, data))
        except Exception as e:  # noqa: BLE001
            out.append((fp, "", {"__load_error__": str(e)}))
    return out


# ---- 工具:Unity 字典(m_keys/m_values)处理 -------------------------------

def is_mkv(obj):
    return (isinstance(obj, dict) and "m_keys" in obj and "m_values" in obj
            and isinstance(obj["m_keys"], list) and isinstance(obj["m_values"], list))


def mkv_to_dict(obj):
    """把 m_keys/m_values 还原成 {k: v};仅用于"读取/计数",绝不用于写回。"""
    if not is_mkv(obj):
        return None
    return dict(zip(obj["m_keys"], obj["m_values"]))


# ---- 校验 ---------------------------------------------------------------

def validate(data):
    """返回 [(level, msg), ...],level 为 'error' | 'warning' | 'info'。"""
    issues = []
    if not isinstance(data, dict) or "__load_error__" in data:
        return [("error", f"无法解析为 JSON 对象: {data.get('__load_error__','?')}")]

    for k in EXPECTED_TOP_KEYS:
        if k not in data:
            issues.append(("error", f"缺少顶层字段: {k}"))
    for k in data:
        if k not in EXPECTED_TOP_KEYS:
            issues.append(("warning", f"出现未知顶层字段(保留): {k}"))

    ver = data.get("version")
    if ver is None:
        issues.append(("warning", "无 version 字段"))
    elif ver not in KNOWN_VERSIONS:
        issues.append(("warning",
                       f"version={ver} 不在已知列表 {sorted(KNOWN_VERSIONS)};"
                       "PC 与 Switch 版本号若不同,字段可能不一致,请谨慎。"))

    ps = data.get("playerSave")
    if isinstance(ps, dict):
        for k in REQUIRED_PLAYER_KEYS:
            if k not in ps:
                issues.append(("warning", f"playerSave 缺少字段: {k}"))
    else:
        issues.append(("error", "playerSave 缺失或非对象"))

    return issues


# ---- 摘要 ---------------------------------------------------------------

def summarize(data):
    """产出人类可读的进度摘要(dict)。"""
    s = {}
    s["version"] = data.get("version")
    ps = data.get("playerSave", {}) if isinstance(data.get("playerSave"), dict) else {}
    s["player_id"] = ps.get("id")
    s["save_date"] = ps.get("saveDate")
    s["play_time_seconds"] = ps.get("playTimeInSeconds")
    s["level"] = ps.get("level")
    s["experience"] = ps.get("experienceCurrent")
    s["current_health"] = ps.get("currentHealth")
    s["current_mana"] = ps.get("currentMana")
    s["heal_charges"] = ps.get("currentHealChargesCount")
    s["death_defiance"] = ps.get("currentTheHermitDeathDefianceCount")
    s["equipped_weapon"] = ps.get("equippedWeaponItem")
    s["equipped_spell"] = ps.get("equippedSpellItem")
    s["equipped_skin"] = ps.get("equippedSkin")
    s["equipped_charms"] = ps.get("equippedCharmItems", [])
    inv = ps.get("itemsInInventory", []) or []
    s["inventory_count"] = len(inv)
    s["inventory"] = inv
    s["vania_moves"] = ps.get("vaniaMoves", [])
    s["main_objectives_done"] = len(ps.get("receivedMainObjectives", []) or [])
    s["arcana_completed_tasks"] = len(ps.get("arcanaCompletedTasks", []) or [])
    s["arcana_unlocked_talents"] = len(ps.get("arcanaUnlockedTalents", []) or [])
    s["watched_cutscenes"] = len(ps.get("watchedCutscenes", []) or [])
    s["completed_tutorials"] = len(ps.get("completedTutorials", []) or [])
    s["discovered_landmarks"] = len(ps.get("discoveredLandmarks", []) or [])
    s["current_curse"] = ps.get("currentCurseID")

    # 探索房间数(从 worldRoomExplorationStates.m_values 计)
    wres = ps.get("worldRoomExplorationStates")
    if is_mkv(wres):
        s["explored_rooms"] = len(wres["m_values"])

    # 世界进度
    worlds = {}
    ws = data.get("worldSaves")
    if is_mkv(ws):
        for name, wdata in zip(ws["m_keys"], ws["m_values"]):
            if isinstance(wdata, dict):
                ent = wdata.get("savableEntityStates")
                worlds[name] = {
                    "completion_items": wdata.get("currentCompletionItemCount"),
                    "savable_entities": len(ent["m_values"]) if is_mkv(ent) else None,
                }
    s["worlds"] = worlds

    # 进度板
    pbs = data.get("progressionBoardSave", {})
    pbi = pbs.get("progressionBoardItemsStates") if isinstance(pbs, dict) else None
    if is_mkv(pbi):
        total = len(pbi["m_values"])
        unlocked = sum(1 for v in pbi["m_values"] if str(v).strip().lower() == "true")
        s["progression_board"] = {"unlocked": unlocked, "total": total}
    return s


# ---- 转换 / 清洗 --------------------------------------------------------

def convert(data, strip_items=None, set_version=None):
    """
    对 data 做最小化、可枚举的改动。返回 (data, changes, modified:bool)。
    无任何实际改动时 modified=False,调用方应逐字节复制原文件(保真)。
    strip_items: 要剥离的 item 名子串列表(用于剔除目标平台无授权的 DLC 内容)。
    set_version: 强制写回的版本号。
    """
    changes = []
    modified = False
    ps = data.get("playerSave")
    if not isinstance(ps, dict):
        changes.append("playerSave 非对象,跳过清洗")
        return data, changes, False

    if strip_items:
        subs = [s.lower() for s in strip_items]
        inv = ps.get("itemsInInventory")
        if isinstance(inv, list):
            before = len(inv)
            ps["itemsInInventory"] = [
                it for it in inv
                if not any(sub in str(it).lower() for sub in subs)
            ]
            removed = before - len(ps["itemsInInventory"])
            if removed:
                changes.append(f"从 itemsInInventory 移除 {removed} 项匹配剥离规则")
                modified = True

        for key in ("equippedWeaponItem", "equippedSpellItem", "equippedSkin"):
            val = ps.get(key)
            if val and any(sub in str(val).lower() for sub in subs):
                ps[key] = None
                changes.append(f"清空被剥离的 {key}: {val}")
                modified = True

        ch = ps.get("equippedCharmItems")
        if isinstance(ch, list):
            before = len(ch)
            ps["equippedCharmItems"] = [
                it for it in ch
                if not any(sub in str(it).lower() for sub in subs)
            ]
            removed = before - len(ps["equippedCharmItems"])
            if removed:
                changes.append(f"从 equippedCharmItems 移除 {removed} 项")
                modified = True

    if set_version:
        old = data.get("version")
        data["version"] = set_version
        changes.append(f"version: {old} -> {set_version}")
        modified = True

    if not modified:
        changes.append("无内容改动(纯身份往返,原文件逐字节复制)")
    return data, changes, modified


# ---- 平台转换(文件名约定 + 版本对齐) ------------------------------------

def detect_slot(filename: str):
    """
    从文件名解析 (prefix, slot_index, ext)。
      BuildSave_0      -> ('BuildSave_', 0, '')      # Switch
      BuildSave_1.sav  -> ('BuildSave_', 1, '.sav')  # PC
    无法解析返回 None。
    """
    m = re.match(r"^(.*?)(\d+)(\.sav)?$", filename, re.IGNORECASE)
    if not m:
        return None
    return m.group(1), int(m.group(2)), (m.group(3) or "").lower()


def platform_filename(name: str, to_platform: str, slot: int | None = None):
    """
    按目标平台约定重写文件名(只改扩展名,保留槽位数字;slot 可显式覆盖)。
    to_platform='pc'    -> 加 '.sav'
    to_platform='switch' -> 去掉 '.sav'
    """
    info = detect_slot(name)
    if not info:
        return name
    prefix, _, _ = info
    if slot is None:
        slot = info[1]
    if to_platform == "pc":
        return f"{prefix}{slot}.sav"
    if to_platform == "switch":
        return f"{prefix}{slot}"
    return name


def platform_version(to_platform: str):
    """仅用于"建议版本"提示;实际转换时版本与目标平台完全解耦,由调用方显式决定。"""
    return PC_REF_VERSION if to_platform == "pc" else SWITCH_REF_VERSION


def convert_to_platform(data, to_platform: str, version: str = None,
                        strip_items=None):
    """
    跨平台转换。
    目标平台(to_platform)只决定输出文件名扩展名(.sav / 无扩展名);
    版本号与平台完全解耦 —— 只有显式传入 version 时才改写,否则保持原存档的版本号。
    返回 (data, changes, modified)。
    """
    set_ver = version if version else None
    _, changes, modified = convert(data, strip_items=strip_items,
                                   set_version=set_ver)
    if set_ver:
        changes.insert(0, f"目标平台: {to_platform} (version -> {set_ver})")
    else:
        changes.insert(0, f"目标平台: {to_platform} (version 保持原值 {data.get('version')})")
    return data, changes, modified


# ---- 落盘 ---------------------------------------------------------------

def save(data, path: str):
    """紧凑无空格写回,尽量逼近原始字节布局。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)


def save_raw(text: str, path: str):
    """逐字节写回原始文本(无改动时保真)。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def default_out_path(in_path: str, tag: str = "converted") -> str:
    base, ext = os.path.splitext(in_path)
    return f"{base}.{tag}{ext}"
