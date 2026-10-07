# Playing FGO

When asked to play, use the `fgo` MCP tools. You make every decision; the mechanics of each
action run in FGA's own code (through the bridge), so you never time taps or guess when the
game is ready. Every tool returns a screenshot plus state.

## The loop

Before each action, write one short line: what you see and why you are doing it. The user
watches your session live (`fgo-agent view`), and these lines are how they follow your plan.

- Right at the start, `set_goal` with the task and your next step; update it whenever the
  plan changes. Every result echoes it back as `goal`.
- `look` tells you which screen FGA sees: battle, cards, menu, support, repeat, ap_refill,
  withdraw, inventory_full, close_dialog, story, loading, or unknown.
- After anything that starts animations or loading (starting a quest, a battle turn, closing a
  popup), call `advance`. It skips story, waits out loading and NP/wave animations, taps
  through results, bond, drops and rewards, rejects friend requests, and returns when you
  have a decision: your battle turn, a menu, support select, the repeat prompt, AP refill,
  or "unknown" (a still screen none of FGA's detectors know: tutorial popups, title cards,
  dialogs, status screens). On "unknown", read the screenshot and `tap`.
- Outside battle, navigate with `tap`, `swipe`, `back`. A long-press is a `swipe` with the same
  start and end point and ms=1500 (opens servant details and battle status).
- A `warning` in a result means the screen stopped changing: do not repeat the same action.

## Memory

You forget everything between sessions unless you write it down.
- Start every session with `read_notes`, then read the topics that matter for the task.
- The roster only knows what you record, so record every one of the user's servants you see,
  every time: on the party screen, in battle status and on any details screen. Call
  `update_servant` with every field the screen shows (level, NP, skills, appends, bond, Grand,
  CE, ATK Fou, NP version name) and fix fields that changed. Supports are not the user's: skip
  them. Use the collection number when a name is ambiguous (e.g. Jeanne d'Arc (Alter) is #106
  Avenger, #219 Berserker). Same for CEs with `update_ce` (level, MLB).
- Before a fight, check `roster` for each party member. A member with no entry or missing
  fields: long-press it on the party screen and record it before you start.
- Check `roster` and `list_ces` before building a party.
- `write_note` lessons as you learn them: UI quirks ("ui"), account facts ("account"), and for
  every hard fight a "battle-<quest>" note with the party, the turn plan, what happened and
  what to change next time. Write the battle note before the session ends, win or lose.
- Keep facts and guesses apart. Mark a line "fact:" only when you saw it on screen or in game
  data, with the date; anything inferred is "tip:". When the screen contradicts a note, the
  screen wins: fix the note right away. A wrong note followed for hours is the classic way
  game agents fail.

## Before a quest

1. Read the quest's Japanese name off the screen and call `find_quest(name)`. It folds Ⅰ/I and
   full/half width, so type what you see.
2. On the party screen, note your frontline, backline, support, their CEs and mystic code.
3. `prepare_battle(quest_id, phase, party, ces, mystic_code)` for every wave's enemies (class,
   HP, traits, skills, NP, multipliers vs each of your servants) and your kits.
   `battle_brief` re-reads it later. Quest hint popups (攻略のヒント) hold the boss's mechanics;
   read them fully.
4. Skills and NPs can have several versions (rank-ups, story unlocks). Match the name in the
   game's skill dialog against the brief to know which one you have.
5. `lookup_servant`, `lookup_ce`, `lookup_mystic_code`, `lookup_command_code` for anything else.

## Planning damage

- Plan per HP bar: spend only what the current bar needs and keep cooldowns and defensive
  skills for the bars after it. Overkill on bar 1 is how a run dies on bar 2.
- `estimate_np_damage` before committing skills: sum every active buff yourself (skills, CE,
  passives, mystic code, support), give the enemy's HP, and see whether one NP is enough.
- It ignores Grand and class score bonuses and some passives, so calibrate: after the first NP
  of a fight, compare the real HP drop with the estimate and scale later estimates by that
  ratio. Put the ratio in the battle note.
- Bar breaks can bring buff block, NP drain and a new form: re-read the boss's status first.

## Battle turn

1. `act` with FGA's skill notation, e.g. "a", "b1", "d3j", "t2". Servant skills by field slot
   (a b c / d e f / g h i), ally target digit right after, master skills j k l, enemy target
   t1-t3 (fixed positions in the top HP-bar row, left to right; empty when a wave has fewer
   enemies), order change "x" + starting 1-3 + backline 1-3. Skip greyed out skills or ones
   showing a cooldown number.
2. `open_cards`: type, weak/resist, stunned, and which party member owns each card. The owner
   field is unreliable for support servants: check card faces on the screenshot before
   building a brave chain.
3. `play_cards(cards=[...], nps=[...])`: three picks in total. Lead with Arts to charge NP,
   Buster to hit hard. Brave and colour chains add damage only to face cards, not NPs. Grand
   servants' passive invincibility triggers only when the cards do not form a chain, so on a
   turn where the boss can kill, a chain can cost a servant. When the hand has Empty slots,
   pick an Empty slot as the last card. It then advances to your next decision by itself.
   `close_cards` goes back for more skills.

## Rules

- Apples (gold, silver, bronze, copper) may be used to refill AP when you run out.
- Never spend Saint Quartz (no SQ AP refills, no SQ continues after a wipe), never summon
  (including friend point summons), never buy anything, unless told to. On the AP refill
  screen, check the row you tap is an apple, not 聖晶石.
- Command spells (令呪, the "o" notation) are a last resort for saving a run that is about to
  be lost, never part of the plan. A clear that needed them is not a success: say so in the
  report and the battle note, and plan the next attempt to win without them.
- On support select, pick a friend whose servant suits the quest, then start the quest.
- Tutorial overlays only accept taps inside the highlighted box; follow them with `tap`.
- Coordinates for `tap` are the 1280x720 screenshot pixels.
- Turn on fast battle speed (top right of the card screen) if it is off.
- A data update can hit right after a battle and send the game to the title screen: tap the
  center to continue, never 引き継ぎ or データクリア.
