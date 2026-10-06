package fgo.bridge

import io.github.fate_grand_automata.scripts.enums.BondCEEffectEnum
import io.github.fate_grand_automata.scripts.enums.BraveChainEnum
import io.github.fate_grand_automata.scripts.enums.GameServer
import io.github.fate_grand_automata.scripts.enums.MaterialEnum
import io.github.fate_grand_automata.scripts.enums.RefillResourceEnum
import io.github.fate_grand_automata.scripts.enums.ScriptModeEnum
import io.github.fate_grand_automata.scripts.enums.ShuffleCardsEnum
import io.github.fate_grand_automata.scripts.enums.SupportClass
import io.github.fate_grand_automata.scripts.enums.SupportSelectionModeEnum
import io.github.fate_grand_automata.scripts.models.CardPriorityPerWave
import io.github.fate_grand_automata.scripts.models.ServantPriorityPerWave
import io.github.fate_grand_automata.scripts.models.ServantSpamConfig
import io.github.fate_grand_automata.scripts.prefs.IBattleConfig
import io.github.fate_grand_automata.scripts.prefs.IGesturesPreferences
import io.github.fate_grand_automata.scripts.prefs.IPerServerConfigPrefs
import io.github.fate_grand_automata.scripts.prefs.IPreferences
import io.github.fate_grand_automata.scripts.prefs.IServantEnhancementPreferences
import io.github.fate_grand_automata.scripts.prefs.ISupportPreferences
import io.github.fate_grand_automata.scripts.prefs.ISupportPreferencesCommon
import io.github.lib_automata.PlatformPrefs
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.time.Duration.Companion.milliseconds

// FGA's defaults from prefs/core/PrefsCore.kt. The agent plays turn by turn, so nothing here
// spends resources: no refills, no run limits, story skip on.

class BridgeSupportPrefs : ISupportPreferences {
    override val friendNames = emptyList<String>()
    override val preferredServants = emptyList<String>()
    override val mlb = false
    override val preferredCEs = emptyList<String>()
    override val friendsOnly = false
    override val selectionMode = SupportSelectionModeEnum.Manual
    override val fallbackTo = SupportSelectionModeEnum.Manual
    override val supportClass = SupportClass.None
    override val alsoCheckAll = false
    override val maxAscended = false
    override val skill1Max = false
    override val skill2Max = false
    override val skill3Max = false
    override val grandServant = false
    override val bondCEEffect = BondCEEffectEnum.Ignore
    override val requireBothNormalAndRewardMatch = false
}

class BridgeBattleConfig : IBattleConfig {
    override val id = "bridge"
    override var name = "bridge"
    override var skillCommand = ""
    override var cardPriority: CardPriorityPerWave = CardPriorityPerWave.default
    override val useServantPriority = false
    override val servantPriority: ServantPriorityPerWave = ServantPriorityPerWave.default
    override val rearrangeCards = emptyList<Boolean>()
    override val braveChains = emptyList<BraveChainEnum>()
    override val party = -1
    override val materials = emptySet<MaterialEnum>()
    override val support: ISupportPreferences = BridgeSupportPrefs()
    override val shuffleCards = ShuffleCardsEnum.None
    override val shuffleCardsWave = 3
    override var spam: List<ServantSpamConfig> = (1..6).map { ServantSpamConfig() }
    override val autoChooseTarget = false
    override val server: GameServer? = null
    override val addRaidTurnDelay = false
    override val raidTurnDelaySeconds = 0
    override fun export(): Map<String, *> = emptyMap<String, Any>()
    override fun import(map: Map<String, *>) {}
}

class BridgeServerPrefs(override val server: GameServer) : IPerServerConfigPrefs {
    override var selectedAutoSkillKey = "bridge"
    override var rainbowApple = 0
    override var goldApple = 0
    override var silverApple = 0
    override var blueApple = 0
    override var copperApple = 0
    override var waitForAPRegen = false
    override var selectedApple = RefillResourceEnum.Gold
    override var currentAppleCount = 0
    override val resources = emptyList<RefillResourceEnum>()
    override fun updateResources(resources: Set<RefillResourceEnum>) {}
    override var shouldLimitRuns = false
    override var limitRuns = 1
    override var shouldLimitMats = false
    override var limitMats = 1
    override var shouldLimitCEs = false
    override var limitCEs = 1
}

@Singleton
class BridgePrefs @Inject constructor() : IPreferences {
    override var scriptMode = ScriptModeEnum.Battle
    override var gameServer: GameServer = GameServer.Jp.Original
    private val config = BridgeBattleConfig()
    override val battleConfigs = listOf<IBattleConfig>(config)
    override var showGameServers = listOf(gameServer)
    override var selectedServerConfigPref: IPerServerConfigPrefs = BridgeServerPrefs(gameServer)
    override var selectedBattleConfig: IBattleConfig = config
    override val storySkip = true
    override val withdrawEnabled = false
    override val stopOnCEGet = false
    override val stopOnFirstClearRewards = false
    override val boostItemSelectionMode = -1
    override val useRootForScreenshots = false
    override val recordScreen = false
    override val skillDelay = 500.milliseconds
    override val screenshotDrops = false
    override val screenshotDropsUnmodified = false
    override val screenshotBond = false
    override var hidePlayButton = false
    override val hideSQInAPResources = true
    override var maxGoldEmberStackSize = 1
    override var maxGoldEmberTotalCount = 100
    override var stopAfterThisRun = false
    override val skipServantFaceCardCheck = false
    override val treatSupportLikeOwnServant = false
    override var shouldLimitFP = false
    override var limitFP = 1
    override var receiveEmbersWhenGiftBoxFull = false
    override val stageCounterSimilarity = 0.85
    override val stageCounterNew = false
    override val waitBeforeTurn = 500.milliseconds
    override val waitBeforeCards = 2000.milliseconds

    override val support = object : ISupportPreferencesCommon {
        override val mlbSimilarity = 0.70
        override val swipesPerUpdate = 10
        override val maxUpdates = 5
    }

    override val platformPrefs = object : PlatformPrefs {
        override val debugMode = false
        override val minSimilarity = 0.80
        override val waitMultiplier = 1.0
        override val swipeMultiplier = 1.0
    }

    override val gestures = object : IGesturesPreferences {
        override val clickWaitTime = 300.milliseconds
        override val clickDuration = 50.milliseconds
        override val clickDelay = 10.milliseconds
        override val swipeWaitTime = 700.milliseconds
        override val swipeDuration = 300.milliseconds
    }

    override var ceBombTargetRarity = 1

    override val servant = object : IServantEnhancementPreferences {
        override var shouldRedirectAscension = false
        override val shouldPerformAscension = false
        override var shouldRedirectGrail = false
    }

    override fun getPerServerConfigPref(server: GameServer) = selectedServerConfigPref
    override fun addPerServerConfigPref(server: GameServer) = selectedServerConfigPref
    override fun forBattleConfig(id: String) = config
    override fun addBattleConfig(id: String) = config
    override fun removeBattleConfig(id: String) {}
    override fun isOnboardingRequired() = false
    override fun completedOnboarding() {}
    override fun updateCompletedRuns(runs: Int) {}
    override fun resetCompletedRuns() {}
}
