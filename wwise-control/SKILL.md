---
name: wwise-control
description: Control a Wwise project through natural-language instructions by driving the wwise_for_claude.py module over WAAPI. Use when the user asks to create/query/modify/delete Wwise objects (Sounds, Buses, Aux Buses, Random/Sequence Containers, Events), set properties (Volume, Pitch, routing/OutputBus, user-defined aux sends), audition objects, or generate SoundBanks.
---

# Wwise Control

Drive a running Wwise project programmatically via the `pywwise` WAAPI wrapper, exposed through a tested helper module. Wwise must be open with the target project loaded and WAAPI enabled (default `ws://127.0.0.1:8080/waapi`, port 8080).

## The module

`wwise_for_claude.py` lives in **this skill's own directory** (next to this `SKILL.md`). Resolve its absolute path before running — do not assume a fixed location, since users install the skill in different places.

It is import-safe (no REPL on import). Always `connect()` first, `disconnect()` last.

Helper functions: `find`, `find_path`, `find_contains`, `create`, `rename`, `move`, `delete`, `get_property`, `set_property`, `children`, `ls`, `count`, `types`, `play`, `stop_all`, `generate_soundbank`. The live `pywwise` connection is `w.ak` — use it directly for anything the helpers don't cover.

## How to run

Write a short temp script (e.g. `_exec.py`) next to the module, run it with the system Python, then delete it. Prefer a temp file over `-c`/stdin (multi-line code and non-ASCII paths survive intact in a file).

```bash
# macOS / Linux
python3 "/path/to/skill/_exec.py"
```

```powershell
# Windows (PowerShell). The two env vars prevent mojibake in console output;
# quote all paths in case the install path contains spaces or non-ASCII chars.
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"; python "C:/path/to/skill/_exec.py"
```

Temp script skeleton:

```python
# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wwise_for_claude as w
import pywwise

w.connect()
# ... operations ...
w.disconnect()
```

## Workflow discipline (follow in order)

1. **Probe before writing.** For any unfamiliar object type, property, or reference, run a read-only probe first to confirm exact names. Use `obj_ns.get_property_and_reference_names(<EObjectType or guid>)` to list a type's valid property/reference names.
2. **Wrap writes in an undo group** so the whole batch is a single Ctrl+Z for the user:
   ```python
   undo = getattr(w.ak.wwise.core, "undo", None)
   try:
       if undo: undo.begin_group()
       # ... create/set ...
   finally:
       if undo: undo.end_group(display_name="description")
   ```
3. **Verify after writing** by reading the properties/references back (don't trust the set call's return alone).
4. **Confirm before `delete()`** — it is not auto-undoable per call; deleting a container also deletes its children.
5. **Clean up temp scripts** after the operation.
6. **Track created GUIDs** in your run output so you can undo/delete precisely later.

## WAQL & API gotchas (hard-won, not visible from the code)

These were discovered through live testing against pywwise. Trust them over intuition:

- **Object identity is `obj.guid`, NOT `obj.id`.** `WwiseObjectInfo` has `guid`, `name`, `type`, `path`, `other`.
- **Path lookup:** use object-reference syntax `$ "<path>"`. The `from path "..."` form may return empty depending on pywwise/Wwise version.
- **Fuzzy / "contains" search:** WAQL uses `:` as a regex-match operator -> `$ where name : "keyword"`. There is no `contains` operator.
- **Reading a property value:** pass return options as the 2nd arg to `get`, then read from `.other`:
  ```python
  r = obj_ns.get(rf'$ "{obj.guid}"', ('@Volume', '@Pitch'))
  vol = r[0].other.get('@Volume')
  ```
  There is no `get_property` method on the WAAPI object namespace.
- **Rename** = `ak.wwise.core.object.set_name(guid, new_name)` (there is no `rename`).
- **Set property** = `set_property(guid, name, value)` (not `set_attrib`).
- **Set reference** (routing, sends) = `set_reference(guid, reference_name, target_guid)`.
- **SoundBank namespace is `ak.wwise.core.soundbank`** (one word), and `generate()` takes `SoundBankInfo` structs, not plain name strings.
- **Transport:** `transport.create(guid)` returns an int id; `transport.execute_action(pywwise.ETransportExecuteActions.PLAY, transport_id)` — action enum is **plural** `ETransportExecuteActions`, and action comes **before** the id. There is no `stop_all`; stop each transport with `STOP` then `destroy(id)`.
- **Name conflict strategy** members are only `FAIL`, `RENAME`, `REPLACE` (no `MERGE`).

## Naming rules enforced by Wwise

- **Bus and Aux Bus names cannot be purely numeric** — they must contain at least one letter. `set_name`/`create` silently sanitizes (e.g. `"250"` -> `"_50"`) or returns `False`. If the user wants a numeric bus name, propose an alternative containing a letter (e.g. `Aux250`, `_250`, `Bus250`).
- **Sound objects DO allow purely numeric names** (e.g. `6411` is fine).

## Common operations reference

```python
# Routing (output bus) — also set the override so it takes effect:
obj_ns.set_property(cont.guid, "OverrideOutput", True)
obj_ns.set_reference(cont.guid, "OutputBus", bus.guid)

# User-defined aux send (slots 0-3) to an Aux Bus, with send volume in dB:
obj_ns.set_property(cont.guid, "OverrideUserAuxSends", True)
obj_ns.set_reference(cont.guid, "UserAuxSend0", aux_bus.guid)
obj_ns.set_property(cont.guid, "UserAuxSendVolume0", 3.0)

# Create (parent takes a GUID):
obj_ns.create(name="X", etype=pywwise.EObjectType.RANDOM_SEQUENCE_CONTAINER,
              parent=parent.guid,
              name_conflict_strategy=pywwise.ENameConflictStrategy.FAIL)
```

Key `EObjectType` members: `SOUND`, `BUS`, `AUX_BUS`, `RANDOM_SEQUENCE_CONTAINER`, `ACTOR_MIXER`, `WORK_UNIT`, `EVENT`.

Common standard Work Unit paths:
- `\Actor-Mixer Hierarchy\Default Work Unit`
- `\Master-Mixer Hierarchy\Default Work Unit\Master Audio Bus`

## If the connection fails

`connect()` raises if Wwise isn't running, the project isn't open, or WAAPI is disabled. Tell the user to open Wwise with the project and enable WAAPI (User Preferences -> Enable Wwise Authoring API, port 8080) rather than retrying blindly.
