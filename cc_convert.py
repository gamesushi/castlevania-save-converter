#!/usr/bin/env python3
"""
cc_convert.py — Castlevania: Belmont's Curse 存档转换/校验 CLI
================================================================
支持平台: PC / Switch / PS5(PS5 文件名/版本尚未用真实样本校准,见下方警告)
================================================================
用法:
  # 校验 + 摘要报告
  python3 cc_convert.py switch_BuildSave_0 --report

  # Switch -> PC:生成 PC 可用的 BuildSave_N.sav(version 对齐到 1.1.1)
  python3 cc_convert.py switch_BuildSave_0 --target pc --out BuildSave_1.sav

  # PC -> Switch:生成 Switch 用的 BuildSave_N(无扩展名,version->1.1.0)
  python3 cc_convert.py sample_BuildSave_1.sav --target switch --out BuildSave_0

  # 跨平台但保留原 version(不自动对齐)
  python3 cc_convert.py switch_BuildSave_0 --target pc --keep-version --out BuildSave_1.sav

  # 指定目标槽位(PC 从1/Switch 从0)
  python3 cc_convert.py switch_BuildSave_0 --target pc --slot 2 --out BuildSave_2.sav

  # 目标平台 与 版本号 各自独立选择:
  #   --target 只决定输出文件名扩展名(.sav / 无扩展名)
  #   --set-version 单独决定版本号(不传则保持原存档版本号,二者互不影响)
  python3 cc_convert.py switch_BuildSave_0 --target pc --set-version 1.1.1 --out BuildSave_1.sav
  # 只换平台、版本号保持 1.1.0 不动:
  python3 cc_convert.py switch_BuildSave_0 --target pc --out BuildSave_1.sav

  # 剥离目标平台无授权的独占皮肤(可选,默认不剥离)
  python3 cc_convert.py pc.sav --strip Skin_MC_Alucard,Skin_MC_Trevor --target switch --out BuildSave_0

  # 处理 Checkpoint dump 出来的整个目录(递归找所有 .sav,镜像输出并改扩展名)
  python3 cc_convert.py ./checkpoint_dump/ --target pc --out-dir ./converted/

  # 强制改写版本号(与 --target 完全独立)
  python3 cc_convert.py pc.sav --set-version 1.0.1 --out out.sav
================================================================
"""
from __future__ import annotations
import argparse
import json
import os
import sys

import castlevania_save as cs


def _print_report(data, path):
    issues = cs.validate(data)
    print(f"\n=== 校验: {os.path.basename(path)} ===")
    errs = [m for lvl, m in issues if lvl == "error"]
    warns = [m for lvl, m in issues if lvl == "warning"]
    infos = [m for lvl, m in issues if lvl == "info"]
    for m in errs:
        print(f"  [错误] {m}")
    for m in warns:
        print(f"  [告警] {m}")
    if not errs and not warns:
        print("  [OK] 结构完整,无异常。")

    if any(lvl == "error" for lvl, _ in issues):
        return  # 结构坏了,不打印摘要

    s = cs.summarize(data)
    print(f"\n=== 摘要: {os.path.basename(path)} ===")
    flat = [
        ("版本", s.get("version")),
        ("玩家ID", s.get("player_id")),
        ("存档时间", s.get("save_date")),
        ("游戏时长(s)", s.get("play_time_seconds")),
        ("等级", s.get("level")),
        ("经验", s.get("experience")),
        ("当前HP/MP", f"{s.get('current_health')}/{s.get('current_mana')}"),
        ("治疗次数", s.get("heal_charges")),
        ("死亡反抗(The Hermit)", s.get("death_defiance")),
        ("武器", s.get("equipped_weapon")),
        ("法术", s.get("equipped_spell")),
        ("皮肤", s.get("equipped_skin")),
        ("护符", ", ".join(s.get("equipped_charms") or [])),
        ("背包数量", s.get("inventory_count")),
        ("已习得体术(vaniaMoves)", len(s.get("vania_moves") or [])),
        ("主线目标完成", s.get("main_objectives_done")),
        ("Arcana 完成任务", s.get("arcana_completed_tasks")),
        ("Arcana 解锁天赋", s.get("arcana_unlocked_talents")),
        ("已看剧情", s.get("watched_cutscenes")),
        ("已完成教学", s.get("completed_tutorials")),
        ("已发现地标", s.get("discovered_landmarks")),
        ("已探索房间", s.get("explored_rooms")),
        ("当前诅咒", s.get("current_curse")),
    ]
    for k, v in flat:
        print(f"  {k:<22}: {v}")
    if s.get("worlds"):
        print("  世界进度:")
        for name, w in s["worlds"].items():
            print(f"    - {name}: 完成物{w.get('completion_items')} / 实体{w.get('savable_entities')}")
    pb = s.get("progression_board")
    if pb:
        print(f"  进度板: 解锁 {pb['unlocked']}/{pb['total']}")


def main():
    ap = argparse.ArgumentParser(
        description="Castlevania: Belmont's Curse PC<->Switch<->PS5 存档工具")
    ap.add_argument("input", help=".sav 文件 或 Checkpoint dump 目录")
    ap.add_argument("--out", help="单文件输出路径(输入为文件时)")
    ap.add_argument("--out-dir", help="目录输出(输入为目录时,镜像结构)")
    ap.add_argument("--target", choices=list(cs.PLATFORMS.keys()), default="pc",
                    help="目标平台:只决定输出文件名扩展名(.sav / 无扩展名),不影响版本号。"
                         "可选: " + ", ".join(cs.PLATFORMS.keys()))
    ap.add_argument("--slot", type=int, default=None,
                    help="目标槽位序号(各平台独立;不指定则沿用原文件名数字)")
    ap.add_argument("--report", action="store_true", help="打印校验 + 摘要")
    ap.add_argument("--strip", help="逗号分隔的 item 子串,匹配则剥离(DLC 独占内容)")
    ap.add_argument("--set-version", help="版本号(与 --target 完全独立;不传则保持原存档版本号)")
    ap.add_argument("--quiet", action="store_true", help="仅输出最终状态")
    args = ap.parse_args()

    if args.out and args.out_dir:
        ap.error("--out 与 --out-dir 互斥")

    loaded = cs.load_any(args.input)
    if not loaded:
        print(f"[错误] 在 {args.input} 未找到任何 .sav", file=sys.stderr)
        sys.exit(1)

    # 目标平台未校准(如 PS5 暂无真实样本)→ 醒目警告
    if not cs.platform_verified(args.target):
        print(f"⚠️  警告:目标平台 '{args.target}' 尚未用真实存档样本校准"
              f"(文件名/版本为假设值)。转换结果请务必在目标主机上验证可读性。\n")

    strip = [x.strip() for x in (args.strip or "").split(",") if x.strip()]

    # 报告模式:只报告不写盘
    if args.report and not (args.out or args.out_dir):
        for path, raw, data in loaded:
            _print_report(data, path)
        return

    # 写盘
    for path, raw, data in loaded:
        if "__load_error__" in data:
            print(f"[跳过] 解析失败: {path} -> {data['__load_error__']}")
            continue

        # 目标平台(文件名)与版本号(可选)各自独立传入;二者互不影响
        converted, changes, modified = cs.convert_to_platform(
            data, args.target, version=args.set_version,
            strip_items=strip or None)

        # 输出路径
        if args.out:
            out_path = args.out
        elif args.out_dir:
            rel = (os.path.relpath(path, args.input)
                   if os.path.isdir(args.input) else os.path.basename(path))
            rel = cs.platform_filename(os.path.basename(rel), args.target, args.slot)
            out_path = os.path.join(args.out_dir, rel)
        else:
            new_name = cs.platform_filename(os.path.basename(path), args.target, args.slot)
            out_path = os.path.join(os.getcwd(), new_name)

        # 防误覆盖源文件
        if os.path.abspath(out_path) == os.path.abspath(path):
            out_path += ".converted"

        if modified:
            cs.save(converted, out_path)
        else:
            cs.save_raw(raw, out_path)     # 无改动 → 逐字节原样复制
        if not args.quiet:
            print(f"[写出] {out_path}")
            for c in changes:
                print(f"         - {c}")
            issues = cs.validate(converted)
            errs = sum(1 for lvl, _ in issues if lvl == "error")
            print(f"         校验: {'有错误!' if errs else ('通过(字节保真)' if not modified else '通过')}")

    if not args.quiet:
        tip = {
            "switch": "Switch 端请用 Checkpoint 把生成的文件放回 "
                      "/switch/Checkpoint/saves/.../ 对应槽位再 restore。",
            "ps5": "PS5 端需要破解版主机 + Apollo Save Tool / Save Mounter 解密与重新签名;"
                   "本工具只产出内部 JSON 文件,实际回注需你在主机上完成。",
        }.get(
            args.target,
            "PC 端把生成的 .sav 放进游戏存档目录(如 Steam userdata 下的 "
            "remote/)对应空槽位即可。")
        print("\n完成。" + tip)


if __name__ == "__main__":
    main()
