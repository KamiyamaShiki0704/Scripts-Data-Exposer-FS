# Scripts-Data-Exposer-FS
Adds functions to HKS that let you access more data about the game to use in your scripts.

See examples/tutorials in NewHksInfo.lua

## Game compatibility

- Supports Elden Ring WW 2.7.0.0 (Steam build 23850278).
- `WORLD_CHR_MAN_BASE` resolves the `WorldChrMan` instance through an AOB scan,
  so HKS pointer chains no longer depend on a version-specific executable RVA.
- Existing scripts that start a `GAME_BASE` chain with the previously documented
  `WorldChrMan` RVA (`0x3D65F88`) are translated automatically.

## Installation

1. Copy `Scripts-Data-Exposer-FS.dll` into your mod directory.
2. Add the DLL path to your Mod Engine `external_dlls` list.
3. Use the constants and examples in `NewHksInfo.lua` when authoring or updating
   HKS scripts. Existing scripts using the legacy `WorldChrMan` RVA remain
   compatible through the DLL translation layer.

Run DLL mods offline with anti-cheat disabled.

## Direct input env

`env(IsInputDown, device, code)` reads input directly without an intermediate
DLL, Lua bridge, or SpEffect row. It returns `1` while the input is held and `0`
when it is up, disconnected, or the game is not the foreground process.

- `INPUT_KEYBOARD`: pass a Windows virtual-key code (`0x48` is H).
- `INPUT_XINPUT_BUTTON`: pass a standard `XINPUT_GAMEPAD_*` button mask. A
  combined mask is down only when every button in it is held.
- `INPUT_XINPUT_TRIGGER`: pass `INPUT_XINPUT_TRIGGER_LEFT` or
  `INPUT_XINPUT_TRIGGER_RIGHT`. The trigger threshold is strictly greater than
  `30`, matching KeyboardEx.

XInput reads user index `0`. See `NewHksInfo.lua` for constants and examples.

`env(InputDuration, device, code)` mirrors the comparison style of the native
`ActionDuration` env. It returns held milliseconds, starts at `1` while down,
and resets to `0` on release, focus loss, or controller disconnect:

```lua
env(InputDuration, INPUT_KEYBOARD, 0x48) > 0 -- H is held
env(InputDuration, INPUT_KEYBOARD, 0x48) >= 435 -- held for 0.435 seconds
```
