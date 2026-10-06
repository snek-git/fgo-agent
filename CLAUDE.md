# Playing FGO

When asked to play, use the `fgo` MCP tools. Work in a loop: `look`, decide, act, read the
state that comes back. Every tool returns a fresh screenshot plus parsed state, so there is
no need to call `look` after an action.

## Screen states

`look` reports `screen` as one of: battle_command, card_select, quest_menu, support_select,
result, result_bond, quest_reward, repeat_prompt, withdraw_prompt, stamina_refill,
story_skippable, black_screen (NP animation or loading), unknown. "unknown" only means no template matched (title
screen, story, menus, home); read the screenshot and use `tap`.

## Before a quest

1. Read the quest's Japanese name off the screen and call `find_quest(name)`.
2. On the party screen, note your three frontline servants, the backline, and the support.
3. `prepare_battle(quest_id, phase, party)`. It returns every wave's enemies (class, HP,
   traits, skills, NP, damage multipliers vs each of your servants) and your servants' kits.
   Plan the NP turns per wave from it. `battle_brief` re-reads it later.
4. `lookup_servant(name)` for any servant you are unsure about, ally or enemy.

## Battle turn

1. On battle_command: use skills with `use_skill(servant, skill, target)` and
   `use_master_skill`. Skip a skill whose icon is greyed out or shows a cooldown number.
2. `target_enemy(n)` if you want to focus one enemy.
3. `open_cards` and read `cards` (type, weak/resist, stunned). NP is ready when the
   servant's NP gauge under their portrait reads 100% or more.
4. `play_cards([...])` with three picks. Brave chain (three cards from one servant) and
   same-colour chains are worth it. Lead with Arts to charge NP, Buster to hit hard.
5. The tool waits for the turn to end. If it stops on result screens, use `advance_results`.

## Rules

- Never spend Saint Quartz, golden apples, summon, or buy anything unless told to.
- On the support screen, pick a friend whose servant suits the quest, then start the quest.
- If stuck on the same screen after two tries, `wait` a few seconds, then `back`.
- Coordinates for `tap` are the 1280x720 screenshot pixels.
