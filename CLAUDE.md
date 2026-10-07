# Playing FGO

When asked to play, use the `fgo` MCP tools. You make every decision; the mechanics of each
action run in FGA's own code (through the bridge), so you never time taps or guess when the
game is ready. Every tool returns a screenshot plus state.

## The loop

Before each action, write one short line: what you see and why you are doing it. The user
watches your session live (`fgo-agent view`), and these lines are how they follow your plan.

- `look` tells you which screen FGA sees: battle, cards, menu, support, repeat, ap_refill,
  withdraw, inventory_full, close_dialog, story, loading, or unknown.
- After anything that starts animations or loading (starting a quest, a battle turn, closing a
  popup), call `advance`. It skips story, waits out loading and NP/wave animations, taps
  through results, bond, drops and rewards, rejects friend requests, and returns when you
  have a decision: your battle turn, a menu, support select, the repeat prompt, AP refill,
  or "unknown" (a still screen none of FGA's detectors know: tutorial popups, title cards,
  dialogs). On "unknown", read the screenshot and `tap`.
- Outside battle, navigate with `tap`, `swipe`, `back`.

## Memory

You forget everything between sessions unless you write it down.
- Start every session with `read_notes`, then read the topics that matter for the task.
- Whenever you open a servant's details screen, record it with `update_servant` (level, NP,
  skills, appends, bond, Grand, CE). Use the collection number when a name is ambiguous
  (e.g. Jeanne d'Arc (Alter) is #106 Avenger, #219 Berserker). Same for CEs with `update_ce`.
- Check `roster` and `list_ces` before building a party.
- `write_note` lessons as you learn them: UI quirks ("ui"), account facts ("account"), and for
  every hard fight a "battle-<quest>" note with the party, the turn plan, what happened and
  what to change next time. Write the battle note before the session ends, win or lose.

## Before a quest

1. Read the quest's Japanese name off the screen and call `find_quest(name)`.
2. On the party screen, note your frontline, backline, support, their CEs and mystic code.
3. `prepare_battle(quest_id, phase, party, ces, mystic_code)` for every wave's enemies (class,
   HP, traits, skills, NP, multipliers vs each of your servants) and your kits.
   `battle_brief` re-reads it later.
4. Skills and NPs can have several versions (rank-ups, story unlocks). Match the name in the
   game's skill dialog against the brief to know which one you have.
5. `lookup_servant`, `lookup_ce`, `lookup_mystic_code`, `lookup_command_code` for anything else.

## Battle turn

1. `act` with FGA's skill notation, e.g. "a", "b1", "d3j", "t2". Servant skills by field slot
   (a b c / d e f / g h i), ally target digit right after, master skills j k l, enemy target
   t1-t3 (fixed positions in the top HP-bar row, left to right; empty when a wave has fewer
   enemies), order change "x" + starting 1-3 + backline 1-3. Skip greyed out skills or ones
   showing a cooldown number.
2. `open_cards`: type, weak/resist, stunned, and which party member owns each card.
   NP is ready when the servant's NP gauge reads 100% or more.
3. `play_cards(cards=[...], nps=[...])`: three picks in total. Brave chain (three cards from
   one servant) and same-colour chains are worth it. Lead with Arts to charge NP, Buster to hit
   hard. When the hand has Empty slots, pick an Empty slot as the last card. It then advances
   to your next decision by itself. `close_cards` goes back for more skills.

## Rules

- Apples (gold, silver, bronze, copper) may be used to refill AP when you run out.
- Never spend Saint Quartz (no SQ AP refills, no SQ continues after a wipe), never summon
  (including friend point summons), never buy anything, unless told to. On the AP refill
  screen, check the row you tap is an apple, not 聖晶石.
- On support select, pick a friend whose servant suits the quest, then start the quest.
- Tutorial overlays only accept taps inside the highlighted box; follow them with `tap`.
- Coordinates for `tap` are the 1280x720 screenshot pixels.
- Turn on fast battle speed (top right of the card screen) if it is off.
