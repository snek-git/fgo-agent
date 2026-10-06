# fgo-agent

A harness that lets an AI agent (Claude Code, through MCP) play Fate/Grand Order JP on Linux.

- **Emulator**: [redroid](https://github.com/remote-android/redroid-doc) Android 13 in Docker,
  with Google's libndk ARM translation from a ChromeOS R136 build
  ([prebuilts](https://github.com/supremegamers/vendor_google_proprietary_ndk_translation-prebuilt)).
  The older 0.2.3 build crashes on Unity 6 (`SEVL`). [MindTheGapps](https://github.com/s1204IT/MindTheGappsBuilder)
  for Play Services: without it Firebase never starts and FGO's data download dies with a
  duplicate-key error. `su` removed and release-keys build props.
  GPU is the Radeon iGPU (`renderD129`): the image's Mesa 24.0 can't drive the RDNA 4 card.
- **Vision**: 720p templates and screen coordinates from
  [FGA](https://github.com/Fate-Grand-Automata/FGA) (MIT, see `src/fgo_agent/assets/FGA-LICENSE`).
  The container runs at exactly 1280x720 so FGA's numbers map 1:1 (halved).
- **Agent tools**: `look`, `tap`, `swipe`, `back`, `wait`, `launch_fgo`, `use_skill`,
  `use_master_skill`, `target_enemy`, `open_cards`, `play_cards`, `close_cards`,
  `advance_results`. Each returns parsed state plus a screenshot.
- **Game data**: [Atlas Academy](https://api.atlasacademy.io) JP data with English names, cached
  in `~/.cache/fgo-agent`. `lookup_servant`, `find_quest` (by Japanese quest name),
  `prepare_battle` (all waves' enemies with class/attribute multipliers vs your party, plus
  your party's skills and NPs), `battle_brief`.

## Setup

```sh
scripts/setup-emu.sh                    # build image, boot container
scripts/install-apk.sh ~/Downloads/fgo.xapk
scrcpy -s 127.0.0.1:5555                # watch or play by hand
```

## Play

Run `claude` in this directory. `.mcp.json` registers the `fgo` server and `CLAUDE.md` is the
playbook. Then: "launch fgo and clear the daily quest".

## Debug

```sh
uv run fgo-agent observe    # parsed state as JSON
uv run fgo-agent shot a.png # screenshot
uv run fgo-agent bench      # capture + parse timing (~45 ms)
```
