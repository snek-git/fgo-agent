# Playing FGO

When asked to play, use the `fgo` MCP tools. Work in a loop: `look`, decide, act, read the
state that comes back. Every tool returns a fresh screenshot plus parsed state, so there is
no need to call `look` after an action.

## Screen states

`look` reports `screen` as one of: battle_command, card_select, quest_menu (map or quest
list), support_select, result, result_bond, result_drops, quest_reward, repeat_prompt,
withdraw_prompt, stamina_refill, story_skippable, black_screen (NP animation or loading),
unknown. "unknown" only means no template matched (title, menus, tutorial popups); read the
screenshot and use `tap`. On black_screen or a moving unknown screen, `wait`.

## Story

On story_skippable, call `skip_story`. Do not read or tap through dialogue.

## Before a quest

1. Read the quest's Japanese name off the screen and call `find_quest(name)`.
2. On the party screen, note your three frontline servants, the backline, the support,
   their CEs and your mystic code.
3. `prepare_battle(quest_id, phase, party, ces, mystic_code)`. It returns every wave's
   enemies (class, HP, traits, skills, NP, damage multipliers vs each of your servants) and
   your kits. Plan the NP turns per wave from it. `battle_brief` re-reads it later.
4. Skills and NPs can have several versions (rank-ups, story unlocks). Match the name in
   the game's skill dialog against the brief to know which one you have.
5. `lookup_servant`, `lookup_ce`, `lookup_mystic_code`, `lookup_command_code` for anything else.

## Battle turn

1. On battle_command: use skills with `use_skill(servant, skill, target)` and
   `use_master_skill`. Pass `target` for skills aimed at one ally. Skip a skill whose icon
   is greyed out or shows a cooldown number.
2. `target_enemy(n)` if you want to focus one enemy.
3. `open_cards` and read `cards` (type, weak/resist, stunned; Empty slots read "unknown").
   NP is ready when the servant's NP gauge reads 100% or more.
4. `play_cards([...])` with three picks. Brave chain (three cards from one servant) and
   same-colour chains are worth it. Lead with Arts to charge NP, Buster to hit hard.
5. The tool waits for the turn to end. On result screens, use `advance_results`.

## Rules

- Never spend Saint Quartz, golden apples, summon, or buy anything unless told to.
- On the support screen, pick a friend whose servant suits the quest, then start the quest.
- If stuck on the same screen after two tries, `wait` a few seconds, then `back`.
- Coordinates for `tap` are the 1280x720 screenshot pixels.
- Turn on fast battle speed (top right of the card screen) if it is off.
