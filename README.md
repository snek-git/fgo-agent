# fgo-agent

A harness that lets an AI agent (Claude Code, through MCP) play Fate/Grand Order JP on Linux.

- **Emulator**: [redroid](https://github.com/remote-android/redroid-doc) Android 13 in Docker,
  with Google's libndk ARM translation from a ChromeOS R136 build
  ([prebuilts](https://github.com/supremegamers/vendor_google_proprietary_ndk_translation-prebuilt)).
  The older 0.2.3 build crashes on Unity 6 (`SEVL`). [MindTheGapps](https://github.com/s1204IT/MindTheGappsBuilder)
  for Play Services: without it Firebase never starts and FGO's data download dies with a
  duplicate-key error. `su` removed and release-keys build props.
  GPU is the Radeon iGPU (`renderD129`): the image's Mesa 24.0 can't drive the RDNA 4 card.
- **Bridge** (`bridge/`, Kotlin): runs [FGA](https://github.com/Fate-Grand-Automata/FGA)'s own
  `libautomata` and `scripts` modules (git submodule `vendor/FGA`, MIT) on the desktop JVM, with
  adb screenshots/taps and desktop OpenCV in place of FGA's Android services. The agent decides
  each turn; FGA's code does the mechanics: its screen detectors, `Caster` (skills, targets,
  waits), card parsing with face-card servant matching, wave tracking, and the AutoBattle loop's
  handling of results, drops, bond, story skip and wave transitions. JSON lines over stdio.
- **MCP server** (`src/fgo_agent`): `look`, `advance`, `act` (FGA skill notation), `open_cards`,
  `play_cards`, `close_cards`, `tap`, `swipe`, `back`, `wait`, `launch_fgo`.
- **Game data**: [Atlas Academy](https://api.atlasacademy.io) JP data with English names, cached
  in `~/.cache/fgo-agent`: `lookup_servant`, `lookup_ce`, `lookup_mystic_code`,
  `lookup_command_code`, `find_quest` (by Japanese quest name), `prepare_battle` (every wave's
  enemies with class/attribute multipliers vs your party, plus your kits), `battle_brief`.

## Setup

```sh
scripts/setup-emu.sh                    # build image, boot container
scripts/build-bridge.sh                 # FGA submodule + Kotlin bridge (JDK 21)
scripts/install-apk.sh ~/Downloads/fgo.xapk
scrcpy -s 127.0.0.1:5555 --audio-codec=aac   # watch or play by hand (no opus encoder in the image)
```

## Play

```sh
scripts/play.sh "clear today's daily quests"      # live in your terminal, Esc to interrupt
scripts/play.sh -b "farm bones until AP is gone"  # headless, logs to logs/
uv run fgo-agent watch                            # follow the latest headless log
```

Either way the session gets only the `fgo` tools (no shell, files or web). `CLAUDE.md` is the
playbook.

## Debug

```sh
uv run fgo-agent screen     # FGA's reading of the current screen
uv run fgo-agent shot a.png # screenshot
uv run fgo-agent bench      # detection timing through the bridge (~42 ms)
```
