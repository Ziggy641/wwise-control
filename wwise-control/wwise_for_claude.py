# -*- coding: utf-8 -*-
"""
Wwise programmable interface module / Wwise 可编程接口模块

A WAAPI helper layer (built on pywwise) for controlling a running Wwise
project from code or from an AI coding agent (e.g. Claude Code). Import-safe:
importing the module does NOT start the REPL.

Requirements:
    - Wwise open with the target project loaded
    - Wwise Authoring API (WAAPI) enabled (User Preferences -> Enable Wwise
      Authoring API), default port 8080
    - Python 3.10+ and the `pywwise` package (`pip install pywwise`)

Programmatic use:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import wwise_for_claude as w
    w.connect()
    # ... operations ...
    w.disconnect()

Interactive REPL (run directly):
    python wwise_for_claude.py
"""

import sys
import pywwise
from collections import Counter, defaultdict

WAAPI_URL = "ws://127.0.0.1:8080/waapi"

# ── 全局连接状态 ──────────────────────────────────────────
ak = None
project = None
dwu = None


# ── 连接管理 ──────────────────────────────────────────────

def connect(url=WAAPI_URL):
    """连接 Wwise 并预加载常用对象。Claude Code 调用前必须先执行此函数。"""
    global ak, project, dwu
    ak = pywwise.new_waapi_connection(url)
    project = ak.wwise.core.get_project_info()
    dwu = find_path(r"\Actor-Mixer Hierarchy\Default Work Unit")
    return ak, project, dwu


def disconnect():
    """断开 Wwise 连接。"""
    global ak
    if ak is not None:
        ak.disconnect()
        ak = None


def _ensure_connected():
    """内部用：检查连接是否就绪，未连接则抛出异常（不发 WAAPI 请求）。"""
    if ak is None:
        raise RuntimeError("[错误] 未连接到 Wwise，请先调用 connect()")


# ── 查找 ──────────────────────────────────────────────────

def find(name, obj_type=None, first_only=True):
    """按名称精确查找对象。

    参数：
        name       - 对象名称（精确匹配）
        obj_type   - 可选，限定类型（如 'Sound'、'Event'）
        first_only - True 时只返回第一个匹配项，False 时返回完整列表
    """
    _ensure_connected()
    try:
        if obj_type:
            result = ak.wwise.core.object.get(rf'$ where name = "{name}" and type = {obj_type}')
        else:
            result = ak.wwise.core.object.get(rf'$ where name = "{name}"')
        if not result:
            return None
        return result[0] if first_only else result
    except Exception as e:
        print(f"[查找失败] {e}")
        return None


def find_path(path):
    """按路径精确查找对象（使用 WAQL 对象引用语法 $ "<path>"）。

    示例：
        find_path(r'\\Actor-Mixer Hierarchy\\Default Work Unit')
    """
    _ensure_connected()
    try:
        result = ak.wwise.core.object.get(rf'$ "{path}"')
        if result:
            return result[0] if len(result) == 1 else result
    except Exception as e:
        print(f"[查找失败] {e}")
    return None


def find_contains(keyword, obj_type=None):
    """按名称关键词模糊搜索（自然语言控制最常用）。

    示例：
        find_contains('BGM')                   # 所有名称含 BGM 的对象
        find_contains('BGM', 'Sound')          # 只找 Sound 类型
        find_contains('BGM', 'RandomSequenceContainer')
    """
    _ensure_connected()
    try:
        # WAQL 的 ':' 是正则匹配运算符，用于"包含"语义
        if obj_type:
            q = rf'$ from type {obj_type} where name : "{keyword}"'
        else:
            q = rf'$ where name : "{keyword}"'
        result = ak.wwise.core.object.get(q)
        return result if result else []
    except Exception as e:
        print(f"[模糊查找失败] {e}")
        return []


# ── 创建 / 重命名 / 移动 / 删除 ──────────────────────────

def create(name, etype, parent_guid):
    """创建新对象。

    参数：
        name        - 对象名称（字符串）
        etype       - 对象类型（pywwise.EObjectType.XXX）
        parent_guid - 父对象的 GUID（如 dwu.guid）
    """
    _ensure_connected()
    try:
        new_obj = ak.wwise.core.object.create(name=name, etype=etype, parent=parent_guid)
        if new_obj:
            print(f"[创建成功] {new_obj.name} ({new_obj.type}) @ {new_obj.path}")
            return new_obj
        print("[创建失败] 返回 None，对象可能已存在或参数有误")
    except Exception as e:
        print(f"[创建失败] {e}")
    return None


def rename(obj, new_name):
    """重命名对象。

    示例：
        rename(find('OldName'), 'NewName')
    """
    _ensure_connected()
    try:
        ak.wwise.core.object.set_name(obj.guid, new_name)
        print(f"[重命名成功] → {new_name}")
    except Exception as e:
        print(f"[重命名失败] {e}")


def move(obj, new_parent_guid):
    """将对象移动到新的父级下。

    示例：
        move(find('MySound'), target_container.guid)
    """
    _ensure_connected()
    try:
        ak.wwise.core.object.move(obj.guid, new_parent_guid)
        print(f"[移动成功] {obj.name} → 新父级")
    except Exception as e:
        print(f"[移动失败] {e}")


def delete(obj):
    """删除对象（不可撤销，请谨慎使用）。"""
    _ensure_connected()
    try:
        ak.wwise.core.object.delete(obj.guid)
        print(f"[删除成功] {obj.name}")
    except Exception as e:
        print(f"[删除失败] {e}")


# ── 属性读写 ──────────────────────────────────────────────

def get_property(obj, prop_name):
    """读取对象属性值。

    常用属性：
        'Volume'、'Pitch'、'LowPassFilter'、'HighPassFilter'、'OutputBus'
    示例：
        vol = get_property(sound_obj, 'Volume')
    """
    _ensure_connected()
    try:
        key = f'@{prop_name}'
        result = ak.wwise.core.object.get(rf'$ "{obj.guid}"', (key,))
        if result and getattr(result[0], 'other', None):
            return result[0].other.get(key)
        return None
    except Exception as e:
        print(f"[读取属性失败] {prop_name}: {e}")
        return None


def set_property(obj, prop_name, value):
    """设置对象属性值。

    示例：
        set_property(sound_obj, 'Volume', -6.0)
        set_property(sound_obj, 'Pitch', 100)
    """
    _ensure_connected()
    try:
        ak.wwise.core.object.set_property(obj.guid, prop_name, value)
        print(f"[设置成功] {obj.name}.{prop_name} = {value}")
    except Exception as e:
        print(f"[设置属性失败] {prop_name}: {e}")


# ── 子对象 / 列表展示 ──────────────────────────────────────

def children(parent_obj):
    """获取某对象的直接子对象（WAAPI 原生 parent.id 查询，性能高）。"""
    _ensure_connected()
    if parent_obj is None:
        print("[错误] parent_obj 为 None")
        return []
    if not hasattr(parent_obj, 'guid'):
        print("[错误] parent_obj 没有 guid 属性")
        return []
    try:
        result = ak.wwise.core.object.get(rf'$ where parent.id = "{parent_obj.guid}"')
        return result if result else []
    except Exception as e:
        print(f"[获取子对象失败] {e}")
        return []


def ls(parent_obj=None):
    """列出对象下的直接子对象（按类型分组）。默认列出 dwu 下的对象。"""
    if parent_obj is None:
        if dwu is None:
            print("[错误] dwu 未初始化，请检查 Wwise 连接，或手动传入 parent_obj")
            return
        parent_obj = dwu
    childs = children(parent_obj)
    if not childs:
        print("(无子对象)")
        return
    groups = defaultdict(list)
    for c in childs:
        t = str(c.type).replace('EObjectType.', '')
        groups[t].append(c)
    for t in sorted(groups.keys()):
        print(f"\n[{t}]:")
        for c in sorted(groups[t], key=lambda x: str(x.name).lower()):
            print(f"  • {c.name}")


# ── 统计 ──────────────────────────────────────────────────

def count(obj_type):
    """统计某类型对象的总数量。

    示例：
        count('Sound')
        count('Event')
    """
    _ensure_connected()
    try:
        result = ak.wwise.core.object.get(rf'$ from type {obj_type}')
        n = len(result)
        print(f"{obj_type}: {n} 个")
        return n
    except Exception as e:
        print(f"[统计失败] {e}")
        return 0


def types(parent_obj=None):
    """统计对象类型分布。

    参数：
        parent_obj - 指定时只统计该对象的直接子对象（快）；
                     不传则统计整个工程（大项目较慢）。
    """
    _ensure_connected()
    if parent_obj is not None:
        childs = children(parent_obj)
        if not childs:
            print("(无子对象)")
            return
        counter = Counter(
            str(obj.type).replace('EObjectType.', '') for obj in childs
        )
        print(f"\n『{parent_obj.name}』下的对象类型统计：")
    else:
        print("[提示] 正在统计整个工程，大型项目可能需要几秒...")
        try:
            all_objs = ak.wwise.core.object.get(r'$ where name != ""')
        except Exception as e:
            print(f"[统计失败] {e}")
            return
        counter = Counter(
            str(obj.type).replace('EObjectType.', '') for obj in all_objs
        )
        childs = all_objs
        print("\n对象类型统计（全工程）：")
    print("─" * 40)
    for t, n in counter.most_common():
        print(f"  {t:.<30} {n:>5}")
    print("─" * 40)
    print(f"  {'总计':.<30} {len(childs):>5}")


# ── 传输控制（试听）──────────────────────────────────────

# 跟踪本会话创建的 transport，供 stop_all 统一停止/销毁
_transports = []


def play(obj):
    """在 Wwise 中试听指定对象。"""
    _ensure_connected()
    try:
        transport_id = ak.wwise.core.transport.create(obj.guid)
        ak.wwise.core.transport.execute_action(
            pywwise.ETransportExecuteActions.PLAY, transport_id
        )
        _transports.append(transport_id)
        print(f"[播放] {obj.name}")
    except Exception as e:
        print(f"[播放失败] {e}")


def stop_all():
    """停止并销毁本会话创建的所有 transport。"""
    _ensure_connected()
    stopped = 0
    for tid in _transports:
        try:
            ak.wwise.core.transport.execute_action(
                pywwise.ETransportExecuteActions.STOP, tid
            )
            ak.wwise.core.transport.destroy(tid)
            stopped += 1
        except Exception as e:
            print(f"[停止 transport {tid} 失败] {e}")
    _transports.clear()
    print(f"[已停止 {stopped} 个播放]")


# ── Soundbank ─────────────────────────────────────────────

def generate_soundbank(bank_names, write_to_disk=True):
    """生成 Soundbank。

    参数：
        bank_names    - SoundBank 名称（字符串）或名称列表
        write_to_disk - 是否写入磁盘（默认 True）

    示例：
        generate_soundbank('Main')
        generate_soundbank(['Main', 'UI'])

    注意：底层 soundbank.generate 接收 SoundBankInfo 结构。
    本函数按名称查找对应 SoundBank 对象后构造，若工程结构特殊导致
    构造失败，可改为直接调用 ak.wwise.core.soundbank.generate(...)。
    """
    _ensure_connected()
    if isinstance(bank_names, str):
        bank_names = [bank_names]
    try:
        from pywwise.structs import SoundBankInfo
        infos = [SoundBankInfo(name=n) for n in bank_names]
        result = ak.wwise.core.soundbank.generate(
            sound_banks=infos, write_to_disk=write_to_disk
        )
        print(f"[Soundbank 生成完成] {', '.join(bank_names)}")
        return result
    except Exception as e:
        print(f"[Soundbank 生成失败] {e}")
        return None


# ── 启动入口（直接运行时进入 REPL）────────────────────────

if __name__ == "__main__":
    import code as _code

    print("=" * 60)
    print("Wwise 交互式操作终端（wwise_for_claude）")
    print("=" * 60)
    print()

    print("[1/2] 连接 Wwise...")
    try:
        connect()
        print(f"      OK - 已连接: {project.name}")
    except Exception as e:
        print(f"      FAIL - {e}")
        sys.exit(1)

    print("[2/2] 预加载 dwu...")
    if dwu:
        print(f"      OK - dwu = {dwu.name}")
    else:
        print("      WARN - 未找到 Default Work Unit")

    print()
    print("─" * 60)
    print("已就绪！快捷变量：ak / project / dwu")
    print()
    print("查找：  find(name)  |  find_path(path)  |  find_contains(keyword)")
    print("操作：  create / rename / move / delete")
    print("属性：  get_property(obj, prop)  |  set_property(obj, prop, value)")
    print("浏览：  ls(obj)  |  children(obj)  |  count(type)  |  types(obj)")
    print("试听：  play(obj)  |  stop_all()")
    print("导出：  generate_soundbank(name)")
    print()
    print("输入 exit() 或 Ctrl+Z 回车退出")
    print("─" * 60)
    print()

    _code.interact(
        banner="",
        local={
            'ak': ak, 'project': project, 'dwu': dwu,
            'pywwise': pywwise, 'Counter': Counter, 'defaultdict': defaultdict,
            'connect': connect, 'disconnect': disconnect,
            'find': find, 'find_path': find_path, 'find_contains': find_contains,
            'create': create, 'rename': rename, 'move': move, 'delete': delete,
            'get_property': get_property, 'set_property': set_property,
            'children': children, 'ls': ls,
            'count': count, 'types': types,
            'play': play, 'stop_all': stop_all,
            'generate_soundbank': generate_soundbank,
        },
        exitmsg="\n断开 Wwise 连接... 再见！"
    )

    disconnect()
