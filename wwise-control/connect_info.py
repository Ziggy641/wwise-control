# -*- coding: utf-8 -*-
"""
connect_info.py — Wwise 连接 + 工程基本信息

会话开场用：连接正在运行的 Wwise 工程，打印基本信息和顶层结构概览，然后断开。
后续的具体操作（创建/查询/修改/试听/生成 SoundBank 等）由按需编写的小脚本完成。

运行（Windows，使用 py 启动器避开商店占位的 python）：
    $env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"; py "connect_info.py"
"""

import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wwise_for_claude as w
import pywwise


def main():
    try:
        w.connect()
    except Exception as e:
        print("[连接失败] 无法连接到 Wwise。")
        print(f"  原因: {e}")
        print("  请确认: (1) Wwise 已打开并加载了目标工程; "
              "(2) 已启用 WAAPI (User Preferences -> Enable Wwise Authoring API, 端口 8080)。")
        return 1

    core = w.ak.wwise.core
    obj = core.object
    info = core.get_info()
    pi = core.get_project_info()

    # license 状态从标题栏推断（无 license key 时标题含该字样）
    license_note = "无 license key" if "No license key" in (pi.title or "") else "已授权"
    langs = ", ".join(l.name for l in pi.languages) or "(无)"
    plats = ", ".join(p.name for p in pi.platforms) or "(无)"
    sb_path = pi.platforms[0].sound_bank_path if pi.platforms else "(无)"

    print("=" * 64)
    print("已连接到 Wwise 工程")
    print("=" * 64)
    print(f"  工程名      : {pi.name}")
    print(f"  Wwise 版本  : {info.version.display_name} (build {info.version.build})")
    print(f"  工程路径    : {pi.path}")
    print(f"  平台        : {plats}")
    print(f"  语言        : {langs}")
    print(f"  未保存修改  : {'是' if pi.is_dirty else '否'} (is_dirty={pi.is_dirty})")
    print(f"  License     : {license_note}")
    print(f"  SoundBank   : {sb_path}")

    # 顶层结构概览：Actor-Mixer Hierarchy 的 Default Work Unit 下有什么
    print("-" * 64)
    print("Actor-Mixer Hierarchy \\ Default Work Unit:")
    if w.dwu:
        kids = obj.get(rf'$ "{w.dwu.guid}" select children', ('name', 'type'))
        if kids:
            for k in kids:
                print(f"    • {k.name}  [{k.type.name}]")
        else:
            print("    (空)")
    else:
        print("    (未找到 Default Work Unit)")

    # Events 数量速览
    try:
        evts = obj.get('$ from type Event')
        print(f"Events 总数   : {len(evts)}")
    except Exception:
        pass

    print("=" * 64)
    print("WAAPI 就绪，可读写。请下达指令。")

    w.disconnect()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
