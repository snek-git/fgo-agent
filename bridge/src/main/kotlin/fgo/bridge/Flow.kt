package fgo.bridge

import io.github.fate_grand_automata.scripts.IFgoAutomataApi
import io.github.fate_grand_automata.scripts.Images
import io.github.fate_grand_automata.scripts.entrypoints.isInSupport
import io.github.fate_grand_automata.scripts.entrypoints.isInventoryFull
import io.github.fate_grand_automata.scripts.enums.GameServer
import io.github.fate_grand_automata.scripts.enums.GameServers
import io.github.fate_grand_automata.scripts.models.AutoSkillAction
import io.github.fate_grand_automata.scripts.models.AutoSkillCommand
import io.github.fate_grand_automata.scripts.models.CommandCard
import io.github.fate_grand_automata.scripts.models.FieldSlot
import io.github.fate_grand_automata.scripts.models.ParsedCard
import io.github.lib_automata.Pattern
import kotlin.time.Duration.Companion.seconds
import kotlin.time.TimeSource

/**
 * Turn-by-turn play on top of FGA's modules. The agent decides what to do; FGA's code decides
 * when the game is ready, how each action is performed, and how to get through the screens in
 * between turns. The screen detectors are FGA's AutoBattle.loop() detectors, in the same order.
 */
class Flow(private val component: BridgeComponent) : IFgoAutomataApi by component.api() {
    private val battle = component.battle()
    private val caster = component.caster()
    private val servantTracker = component.servantTracker()
    private val stageTracker = component.stageTracker()
    private val state = component.state()
    private val connectionRetry = component.connectionRetry()
    private val withdraw = component.withdraw()

    /** Mirrors AutoBattle.isInBattle: gates the death-animation and between-waves checks. */
    private var isInBattle = false

    /** False after cards are played, until the next turn's bookkeeping has run. */
    private var turnStarted = false

    /** True once a battle ended (results seen), so the next battle starts a fresh run. */
    private var runEnded = false

    /** FGA knows the card screen by flow, not by a detector; so does the bridge. */
    private var cardsOpen = false

    private class Screen(val name: String, val check: () -> Boolean, val handle: (() -> Unit)?)

    // Not FGA's: its loop just keeps polling through loading screens, but advance() has to tell
    // a loading screen apart from a still screen that waits for the agent. Cut from JP screens.
    private val loadingTexts = listOf("loading.png", "connecting.png").map { name ->
        Flow::class.java.getResourceAsStream("/$name")!!.use { CvPattern(it, isColor = false, tag = name) }
    }
    private val loadingRegion = io.github.lib_automata.Region(1760, 1280, 800, 160)

    // Same order as AutoBattle.loop(); a null handler means the agent decides.
    private val screens = listOf(
        Screen("connection_retry", { connectionRetry.needsToRetry() }, { connectionRetry.retry() }),
        Screen("loading", { loadingTexts in loadingRegion }, { }),
        Screen("battle", { battle.isIdle() }, null),
        Screen("menu", { images[Images.Menu] in locations.menuScreenRegion }, null),
        Screen("result_bond", { images[Images.Bond] in locations.resultBondRegion }, ::result),
        Screen("result", ::isInResult, ::result),
        Screen("result_drops", { images[Images.MatRewards] in locations.resultMatRewardsRegion }, {
            locations.resultMatRewardsRegion.click()
        }),
        Screen("quest_reward", { images[Images.QuestReward] in locations.resultQuestRewardRegion }, {
            locations.resultClick.click()
        }),
        Screen("support", { isInSupport() }, null),
        Screen("repeat", { findRepeatButton() != null }, null),
        // FGA's ordeal-call and interlude-end checks only look for a 閉じる button; FGA can act on
        // them because it only meets them right after a quest. Here any such dialog matches, so
        // the agent reads it and decides.
        Screen("close_dialog", {
            images[Images.Close] in locations.ordealCallOutOfPodsRegion ||
                images[Images.Close] in locations.interludeEndScreenClose
        }, null),
        Screen("withdraw", { withdraw.needsToWithdraw() }, null),
        Screen("story", { locations.menuStorySkipRegion.exists(images[Images.StorySkip], similarity = 0.7) }, ::skipStory),
        Screen("friend_request", { images[Images.SupportExtra] in locations.resultFriendRequestRegion }, {
            locations.resultFriendRequestRejectClick.click()
        }),
        Screen("bond10_reward", {
            locations.resultCeRewardRegion.exists(images[Images.Bond10Reward], similarity = 0.75)
        }, { locations.scriptArea.center.click() }),
        Screen("ce_reward", { images[Images.CEDetails] in locations.resultCeRewardDetailsRegion }, {
            locations.resultCeRewardCloseClick.click()
        }),
        Screen("death_animation", ::isDeathAnimation, { locations.battle.battleSafeMiddleOfScreenClick.click() }),
        Screen("rank_up", { images[Images.RankUp] in locations.rankUpRegion }, { locations.middleOfScreenClick.click() }),
        Screen("between_waves", { isInBattle && locations.npStartedRegion.isBlack() }, {
            locations.battle.battleSafeMiddleOfScreenClick.click()
        }),
        Screen("ap_refill", { images[Images.Stamina] in locations.staminaScreenRegion }, null),
        Screen("inventory_full", { isInventoryFull() }, null),
    )

    private fun isInResult() = listOf(
        images[Images.Result] to locations.resultScreenRegion,
        images[Images.MasterLevelUp] to locations.resultMasterLvlUpRegion,
        images[Images.MasterExp] to locations.resultMasterExpRegion
    ).any { (image, region) -> image in region }

    private fun isDeathAnimation() =
        isInBattle && FieldSlot.list
            .map { locations.battle.servantPresentRegion(it) }
            .count { it.exists(images[Images.ServantExist], similarity = 0.70) } in 1..2

    private fun findRepeatButton() =
        locations.continueRegion.find(images[Images.Repeat])
            ?: if (prefs.gameServer is GameServer.Jp)
                locations.continueRegion.find(images[Images.Repeat, GameServers.default])
            else null

    private fun result() {
        isInBattle = false
        runEnded = true
        locations.resultClick.click(15)
    }

    private fun skipStory() {
        locations.menuStorySkipClick.click()
        0.5.seconds.wait()
        locations.menuStorySkipYesClick.click()
    }

    /**
     * Which screen is up, without acting on it. FGA's checks for passing moments (death and wave
     * animations, reward popups, rank-up) only make sense inside its own loop: on a status or
     * details screen they match by accident, so look() never reports them.
     */
    fun screen(): String {
        syncCardsOpen()
        return if (cardsOpen) "cards" else useSameSnapIn {
            screens.firstOrNull { it.name !in loopOnly && it.check() }?.name ?: "unknown"
        }.also(::noteScreen)
    }

    /**
     * Like AutoBattle.menu()/repeatQuest(): these screens only show outside a battle, so the next
     * battle starts a new run (also covers losses, which skip results). Every screen check runs
     * this, because the agent often reaches them with taps instead of advance().
     */
    private fun noteScreen(name: String) {
        if (name in setOf("menu", "support", "repeat")) {
            isInBattle = false
            runEnded = runEnded || state.stage != -1
        }
    }

    private val loopOnly = setOf(
        "death_animation", "between_waves", "bond10_reward", "ce_reward", "rank_up", "friend_request"
    )

    /**
     * The card screen is known by flow, so a tap that closes it (or a parallel call racing
     * open_cards) leaves the flag stale. The command screen showing means it is closed.
     */
    private fun syncCardsOpen() {
        if (cardsOpen && battle.isIdle()) cardsOpen = false
    }

    /** The agent can reach a battle through look() as well as advance(), so act/cards set up the turn too. */
    private fun requireCommandScreen() {
        syncCardsOpen()
        require(!cardsOpen) { "the card screen is open: play_cards or close_cards first" }
        require(battle.isIdle()) { "not on the battle command screen" }
        startTurn()
    }

    /**
     * Run FGA's loop, handling the in-between screens, until the agent has something to decide.
     * Returns the decision screen; "unknown" when nothing matches and the picture has settled.
     */
    fun advance(timeoutSeconds: Int): String {
        val deadline = TimeSource.Monotonic.markNow() + timeoutSeconds.seconds
        var previous: Pattern? = null
        var stillFor = 0
        var unmatchedSince = TimeSource.Monotonic.markNow()
        // Same handled screen over and over means the handler's tap isn't landing (a tutorial
        // overlay, an unexpected dialog). FGA would loop forever; hand it to the agent instead.
        var lastHandled: String? = null
        var handledInARow = 0
        try {
            while (deadline.hasNotPassedNow()) {
                val match = useSameSnapIn { screens.firstOrNull { it.check() } }
                if (match != null) {
                    stillFor = 0
                    unmatchedSince = TimeSource.Monotonic.markNow()
                }
                when {
                    // Black (fades, wave changes) and white (NP flashes) are transitions,
                    // never something to decide on
                    match == null && (locations.scriptArea.isBlack() || locations.scriptArea.isWhite()) -> {
                        stillFor = 0
                        unmatchedSince = TimeSource.Monotonic.markNow()
                    }
                    match == null -> {
                        val now = locations.scriptArea.getPattern("settle")
                        stillFor = if (previous?.findMatches(now, 0.98)?.any() == true) stillFor + 1 else 0
                        previous?.close()
                        previous = now
                        // Out of battle: ~2s without change is a screen waiting for input, and
                        // menus can loop animations forever, so give up after 8s regardless.
                        // In battle an unknown screen is almost always an NP animation, which can
                        // hold still for seconds, so only a long stillness counts there.
                        val settled = stillFor >= if (isInBattle) 20 else 3
                        val idleTooLong = !isInBattle && unmatchedSince.elapsedNow() > 8.seconds
                        if (settled || idleTooLong) return "unknown"
                    }
                    match.handle != null -> {
                        if (match.name != "loading") {
                            handledInARow = if (match.name == lastHandled) handledInARow + 1 else 1
                            lastHandled = match.name
                            if (handledInARow > 8) return match.name
                        }
                        match.handle.invoke()
                    }
                    else -> {
                        if (match.name == "battle") startTurn() else noteScreen(match.name)
                        return match.name
                    }
                }
                0.5.seconds.wait()
            }
            return "timeout"
        } finally {
            previous?.close()
        }
    }

    /** Battle.performBattle()'s turn-start steps: wave tracking, turn count, servant tracking. */
    private fun startTurn() {
        if (turnStarted) return
        if (runEnded) {
            battle.resetState()
            runEnded = false
        }
        isInBattle = true
        prefs.waitBeforeTurn.wait()
        useSameSnapIn {
            stageTracker.checkCurrentStage()
            state.nextTurn()
        }
        servantTracker.beginTurn()
        turnStarted = true
    }

    /** FGA's AutoBattle just drove the game on its own component: nothing here is current. */
    fun afterFarm() {
        isInBattle = false
        cardsOpen = false
        turnStarted = false
        runEnded = true
    }

    fun battleInfo() = mapOf(
        "wave" to state.stage + 1,
        "turn_in_wave" to state.turn + 1,  // FGA counts turns per wave
        "servants" to servantTracker.deployed.entries.associate { (field, team) -> field.position to team.position }
    )

    /**
     * One turn's actions in FGA's skill-command notation, run through FGA's Caster
     * (same dispatch as AutoSkill.act). NPs and wave/turn separators are not allowed here.
     */
    /**
     * Returns whether the command screen came back afterwards. It does not when a dialog stayed
     * open: the ally picker of a skill given no target, or the info window of a skill on
     * cooldown whose close tap missed. Both break the next card or skill step.
     */
    fun act(command: String): Boolean {
        val stages = AutoSkillCommand.parse(command).stages
        require(stages.size == 1 && stages[0].size == 1) { "one turn at a time: no ',' or '#'" }
        requireCommandScreen()
        for (action in stages[0][0]) {
            when (action) {
                is AutoSkillAction.Atk -> require(action.nps.isEmpty() && action.cardsBeforeNP == 0) {
                    "NPs are picked with play, not act"
                }
                is AutoSkillAction.ServantSkill -> caster.castServantSkill(action.skill, action.targets)
                is AutoSkillAction.MasterSkill -> caster.castMasterSkill(action.skill, action.target)
                is AutoSkillAction.CommandSpell -> caster.castCommandSpell(action.skill, action.target)
                is AutoSkillAction.TargetEnemy -> caster.selectEnemyTarget(action.enemy)
                is AutoSkillAction.OrderChange -> caster.orderChange(action)
            }
        }
        return locations.battle.screenCheckRegion.exists(images[Images.BattleScreen], 4.seconds)
    }

    /** Battle.clickAttack(): open the cards and parse them with FGA's CardParser. */
    fun cards(): List<ParsedCard> {
        requireCommandScreen()
        return battle.clickAttack().also { cardsOpen = true }
    }

    /** Leave the card screen (AttackScreenLocations.backClick). */
    fun back() {
        syncCardsOpen()
        require(cardsOpen) { "the card screen is not open" }
        locations.attack.backClick.click()
        locations.battle.screenCheckRegion.exists(images[Images.BattleScreen], 5.seconds)
        cardsOpen = false
    }

    /** Card.clickCommandCards() with the agent's picks instead of card priority. */
    fun play(nps: List<Int>, faces: List<Int>, cardsBeforeNp: Int) {
        syncCardsOpen()
        require(cardsOpen) { "open the cards first" }
        require(nps.size + faces.size in 1..3) { "pick 1 to 3 cards in total" }
        require(cardsBeforeNp in 0..faces.size) { "cards_before_np is more than the face cards picked" }
        val face = faces.map { CommandCard.Face.list[it - 1] }
        face.take(cardsBeforeNp).forEach { caster.use(it) }
        nps.forEach { caster.use(CommandCard.NP.list[it - 1]) }
        face.drop(cardsBeforeNp).forEach { caster.use(it) }
        cardsOpen = false
        turnStarted = false
        0.5.seconds.wait()
    }
}
