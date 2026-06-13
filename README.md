# wwise-control

A [Claude Code](https://claude.com/claude-code) **skill** + Python module for controlling an [Audiokinetic Wwise](https://www.audiokinetic.com/) project through natural-language instructions.

Tell your AI coding agent what you want — *"create a Random Container under the Actor-Mixer hierarchy and route it to the SFX bus with a +3 dB aux send"* — and it drives Wwise for you over the Wwise Authoring API (WAAPI), no manual scripting and no opening the terminal yourself.

## What's inside

```
wwise-control/
├── SKILL.md             # The skill: operating manual + hard-won WAAPI/WAQL gotchas
└── wwise_for_claude.py  # The executor: import-safe pywwise helper module
```

- **`wwise_for_claude.py`** — a tested helper layer over `pywwise`: connect, find/create/move/rename/delete objects, read/write properties, set routing and aux sends, audition, generate SoundBanks. Also runs standalone as an interactive REPL.
- **`SKILL.md`** — tells the agent how to use the module *and* captures non-obvious WAAPI/WAQL behavior discovered through live testing (e.g. object identity is `.guid` not `.id`; WAQL "contains" is the `:` regex operator; Wwise rejects purely-numeric Bus names).

## Requirements

- **Wwise** open with your project loaded
- **WAAPI enabled**: Wwise → *User Preferences* → *Enable Wwise Authoring API* (default port `8080`)
- **Python 3.10+**
- **pywwise**: `pip install pywwise`

## Install

### As a Claude Code skill (recommended)

Copy the `wwise-control/` folder into your skills directory:

```bash
# macOS / Linux
cp -r wwise-control ~/.claude/skills/

# Windows (PowerShell)
Copy-Item -Recurse wwise-control "$env:USERPROFILE\.claude\skills\"
```

Restart Claude Code. The skill auto-activates when you ask to do Wwise work. The script travels inside the skill folder, so the agent always finds it.

### As a standalone Python module

```bash
python wwise-control/wwise_for_claude.py   # interactive REPL
```

…or import it in your own scripts:

```python
import sys, os
sys.path.insert(0, "path/to/wwise-control")
import wwise_for_claude as w
import pywwise

w.connect()
dwu = w.find_path(r"\Actor-Mixer Hierarchy\Default Work Unit")
w.create("MySound", pywwise.EObjectType.SOUND, dwu.guid)  # see SKILL.md for full API
w.disconnect()
```

## Quick API tour

| Function | Purpose |
|---|---|
| `connect()` / `disconnect()` | Open / close the WAAPI connection |
| `find(name)` / `find_path(path)` / `find_contains(kw)` | Locate objects |
| `create(name, etype, parent_guid)` | Create an object |
| `rename` / `move` / `delete` | Restructure |
| `get_property` / `set_property` | Read / write properties (Volume, Pitch, …) |
| `ls` / `children` / `count` / `types` | Browse and summarize |
| `play` / `stop_all` | Audition |
| `generate_soundbank(names)` | Build SoundBanks |

The live `pywwise` connection is exposed as `w.ak` for anything the helpers don't wrap.

## Safety notes

- The skill instructs the agent to **probe before writing**, **wrap edits in a Wwise undo group** (one Ctrl+Z to revert a batch), **verify after writing**, and **confirm before deleting** (deleting a container also deletes its children).
- Always work on a **version-controlled or backed-up project**.

## Credits

Created by [Ziggy641](https://github.com/Ziggy641).

Built on [pywwise](https://pypi.org/project/pywwise/). Wwise is a trademark of Audiokinetic Inc. This project is not affiliated with or endorsed by Audiokinetic.

## License

[MIT](LICENSE)
