---
name: wwise-control
description: Control a Wwise project through natural-language instructions by driving the wwise_for_claude.py module over WAAPI. Use when the user asks to create/query/modify/delete Wwise objects (Sounds, Buses, Aux Buses, Random/Sequence Containers, Events), set properties (Volume, Pitch, routing/OutputBus, user-defined aux sends), create source/effect plug-ins (Synth One, Tone Generator, Peak Limiter), build RTPCs and LFO/Envelope modulators with curves, audition objects, or generate SoundBanks.
---

# Wwise Control

Drive a running Wwise project programmatically via the `pywwise` WAAPI wrapper, exposed through a tested helper module. Wwise must be open with the target project loaded and WAAPI enabled (default `ws://127.0.0.1:8080/waapi`, port 8080).

## The module

`wwise_for_claude.py` lives in **this skill's own directory** (next to this `SKILL.md`). Resolve its absolute path before running — do not assume a fixed location, since users install the skill in different places.

It is import-safe (no REPL on import). Always `connect()` first, `disconnect()` last.

Helper functions: `find`, `find_path`, `find_contains`, `create`, `rename`, `move`, `delete`, `get_property`, `set_property`, `set_reference`, `children`, `ls`, `count`, `types`, `play`, `stop_all`, `generate_soundbank`.

Higher-level builders for things pywwise can't do directly — `create_source`, `add_effect`, `add_rtpc`, `create_modulator`, `set_routing`, `list_plugins`, plus `raw_set`/`raw_get` and the `undo_group` context manager — are documented under **"Plug-ins, RTPC, modulators & routing"** below.

The live `pywwise` connection is `w.ak` — use it directly for anything the helpers don't cover.

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
2. **Wrap writes in an undo group** so the whole batch is a single Ctrl+Z for the user. Easiest is the `undo_group` context manager:
   ```python
   with w.undo_group("description"):
       # ... create/set ...
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

Key `EObjectType` members: `SOUND`, `BUS`, `AUX_BUS`, `RANDOM_SEQUENCE_CONTAINER`, `ACTOR_MIXER`, `WORK_UNIT`, `EVENT`, `GAME_PARAMETER`, `MODULATOR_LFO`, `SOURCE_PLUGIN`, `EFFECT`, `RTPC`.

Common standard Work Unit paths:
- `\Actor-Mixer Hierarchy\Default Work Unit`
- `\Master-Mixer Hierarchy\Default Work Unit\Master Audio Bus`
- `\Game Parameters\Default Work Unit`
- `\Modulators\Default Work Unit`
- `\Events\Default Work Unit`

## Plug-ins, RTPC, modulators & routing

`pywwise`'s typed API **cannot** create plug-ins, RTPCs, modulators or curves (its `set`/`SetObjectNode` has no `classId`, no references, no list creation). The module wraps the raw `ak.wwise.core.object.set` for these. **Prefer the builders**; drop to `raw_set`/`raw_get` only for what they don't cover.

```python
with w.undo_group("Build helicopter rotor"):
    rpm = w.create("Helicopter_RPM", pywwise.EObjectType.GAME_PARAMETER,
                   w.find_path(r"\Game Parameters\Default Work Unit").guid)
    snd = w.create("Helicopter_Rotor", pywwise.EObjectType.SOUND, w.dwu.guid)
    src = w.create_source(snd, "Wwise Synth One", NoiseLevel=0.0, BaseFrequency=60.0)
    lfo = w.create_modulator("LFO_RotorChop", "lfo",
                             LfoWaveform=w.LFO_WAVEFORMS["saw_down"], LfoFrequency=12.0, LfoDepth=100.0)
    bus = w.create("HELI", pywwise.EObjectType.BUS,
                   w.find_path(r"\Master-Mixer Hierarchy\Default Work Unit\Master Audio Bus").guid)
    w.add_effect(bus, "Wwise Peak Limiter")                       # default settings
    w.set_routing(snd, bus)                                        # OverrideOutput + OutputBus
    w.add_rtpc(src, "OutputLevel", lfo, [(0.0, -18.0), (1.0, 0.0)])   # chop: LFO output X is 0..1
    w.add_rtpc(snd, "Volume", rpm, [(0, -96), (20, -12), (100, 0)])   # RPM -> loudness
    w.add_rtpc(lfo, "LfoFrequency", rpm, [(0, 2), (20, 8), (100, 22)])# RPM -> chop rate
```

Builders (`plugin` = a name in `PLUGIN_CLASS_IDS` or a classId int):
- `create_source(sound, plugin, **props)` → source guid. Props are plug-in params, e.g. `NoiseLevel=0.0`.
- `add_effect(target, plugin)` → `(slot_guid, effect_guid)`. Works on Bus / Actor-Mixer / Sound.
- `add_rtpc(owner, property, control_input, points=None)` → rtpc guid. `control_input` is a Game Parameter **or** a Modulator. `points` = `[(x, y)]` or `[(x, y, shape)]`; omit for Wwise's default curve.
- `create_modulator(name, kind="lfo", **props)` → guid (`kind`: `lfo`/`envelope`/`time`).
- `set_routing(obj, bus)`, `set_reference(obj, ref, target)`, `list_plugins(keyword)`.

### Raw `object.set` rules (what the builders encode)

If you hand-write `raw_set(...)`, every special key is **`@`-prefixed**:
- `@<Property>` → property value (`@PropertyName`, `@Volume`).
- `@<Reference>` → a GUID string **or** an inline object to create (`@ControlInput`, `@Curve`, `@Effect`).
- `@<ListName>` → array of objects created *in a list* (`@RTPC`, `@Effects`).
- `children:[...]` is the child *hierarchy* only (Sound → SourcePlugin). RTPCs/Effects are **lists, not children** ("RTPC can't be child of Sound").
- A curve object accepts **only** `type` + `points` (each point `{x, y, shape}`); any extra key — including `name` — is rejected.
- In `get`, references/properties take **no** `@`; in `set`, everything takes `@`.
- A modulator used as a `ControlInput` has output range **0.0–1.0** (the curve X-axis).
- Failures return `None` silently; `raw_set` raises with the offending payload. For Wwise's real error text, replay the payload in a **separate process** with `waapi.WaapiClient(url, allow_exception=True)` (flipping `_allow_exception` at runtime does nothing, and two clients can't share one process).

### Reaching these objects with WAQL
- Effects live in the `Effects` list as `EffectSlot` → `Effect`. Read via `select Effects`, then the slot's `select Effect`.
- RTPCs live in the `RTPC` list. Read via `select RTPC` — **not** `select children` or `select descendants` (both return empty for RTPCs/source-plugins).
- `from type SourcePlugin` / `from type RTPC` return empty — reach them through their parent's `select children` / `select RTPC`.
- Resolve work units by object-reference path (`$ "\Game Parameters\Default Work Unit"`), not `from type WorkUnit`.
- Find plug-in classIds with `w.list_plugins()`; schema files ship on disk at `…/Authoring/Data/Schemas/Definitions/waapi_definitions.json`.

## If the connection fails

`connect()` raises if Wwise isn't running, the project isn't open, or WAAPI is disabled. Tell the user to open Wwise with the project and enable WAAPI (User Preferences -> Enable Wwise Authoring API, port 8080) rather than retrying blindly.
