package fgo.bridge

import dagger.Binds
import dagger.Component
import dagger.Module
import dagger.Provides
import io.github.fate_grand_automata.IStorageProvider
import io.github.fate_grand_automata.scripts.FgoAutomataApi
import io.github.fate_grand_automata.scripts.FgoGameAreaManager
import io.github.fate_grand_automata.scripts.IFgoAutomataApi
import io.github.fate_grand_automata.scripts.IImageLoader
import io.github.fate_grand_automata.scripts.IScriptMessages
import io.github.fate_grand_automata.scripts.locations.IScriptAreaTransforms
import io.github.fate_grand_automata.scripts.locations.ScriptAreaTransforms
import io.github.fate_grand_automata.scripts.models.AutoSkillCommand
import io.github.fate_grand_automata.scripts.models.CardPriorityPerWave
import io.github.fate_grand_automata.scripts.models.ServantPriorityPerWave
import io.github.fate_grand_automata.scripts.models.SpamConfigPerTeamSlot
import io.github.fate_grand_automata.scripts.models.battle.BattleState
import io.github.fate_grand_automata.scripts.modules.Battle
import io.github.fate_grand_automata.scripts.modules.Caster
import io.github.fate_grand_automata.scripts.modules.ConnectionRetry
import io.github.fate_grand_automata.scripts.modules.RealSupportScreen
import io.github.fate_grand_automata.scripts.modules.ServantTracker
import io.github.fate_grand_automata.scripts.modules.StageTracker
import io.github.fate_grand_automata.scripts.modules.SupportScreen
import io.github.fate_grand_automata.scripts.modules.Withdraw
import io.github.fate_grand_automata.scripts.prefs.IBattleConfig
import io.github.fate_grand_automata.scripts.prefs.IGesturesPreferences
import io.github.fate_grand_automata.scripts.prefs.IPreferences
import io.github.fate_grand_automata.scripts.prefs.ISupportPreferences
import io.github.fate_grand_automata.scripts.prefs.ISupportPreferencesCommon
import io.github.lib_automata.AutomataApi
import io.github.lib_automata.Clicker
import io.github.lib_automata.ExitManager
import io.github.lib_automata.GameAreaManager
import io.github.lib_automata.GestureService
import io.github.lib_automata.Highlighter
import io.github.lib_automata.ImageMatcher
import io.github.lib_automata.OcrService
import io.github.lib_automata.PlatformImpl
import io.github.lib_automata.RealClicker
import io.github.lib_automata.RealHighlighter
import io.github.lib_automata.RealImageMatcher
import io.github.lib_automata.RealScale
import io.github.lib_automata.RealSwiper
import io.github.lib_automata.RealTransformer
import io.github.lib_automata.RealWaiter
import io.github.lib_automata.Scale
import io.github.lib_automata.ScreenshotService
import io.github.lib_automata.StandardAutomataApi
import io.github.lib_automata.Swiper
import io.github.lib_automata.Transformer
import io.github.lib_automata.Waiter
import io.github.lib_automata.dagger.ScriptScope
import javax.inject.Singleton

// Mirrors FGA's app/di/script/{LibAutomataModule,ScriptsModule,PreferencesModule} and
// app/di/app/AppBindsModule, with the Android services swapped for adb ones.

@Module
abstract class LibAutomataModule {
    companion object {
        @ScriptScope
        @Provides
        fun exitManager() = ExitManager()
    }

    @ScriptScope @Binds abstract fun swiper(swiper: RealSwiper): Swiper
    @ScriptScope @Binds abstract fun waiter(waiter: RealWaiter): Waiter
    @ScriptScope @Binds abstract fun highlighter(highlighter: RealHighlighter): Highlighter
    @ScriptScope @Binds abstract fun clicker(clicker: RealClicker): Clicker
    @ScriptScope @Binds abstract fun scale(scale: RealScale): Scale
    @ScriptScope @Binds abstract fun transformer(transformer: RealTransformer): Transformer
    @ScriptScope @Binds abstract fun imageMatcher(imageMatcher: RealImageMatcher): ImageMatcher
    @ScriptScope @Binds abstract fun api(api: StandardAutomataApi): AutomataApi
}

@Module
abstract class ScriptsModule {
    companion object {
        @ScriptScope
        @Provides
        fun gameAreaManager(platform: PlatformImpl): GameAreaManager =
            FgoGameAreaManager(
                gameSizeWithBorders = platform.windowRegion.size,
                offset = { platform.windowRegion.location }
            )
    }

    @ScriptScope @Binds abstract fun api(api: FgoAutomataApi): IFgoAutomataApi
    @ScriptScope @Binds abstract fun gestures(gestures: AdbGestures): GestureService
    @ScriptScope @Binds abstract fun screenshots(service: AdbScreenshotService): ScreenshotService
    @ScriptScope @Binds abstract fun areaTransforms(transforms: ScriptAreaTransforms): IScriptAreaTransforms
    @ScriptScope @Binds abstract fun supportScreen(screen: RealSupportScreen): SupportScreen
    @ScriptScope @Binds abstract fun ocr(ocr: NoOcr): OcrService
}

@Module
abstract class PlatformModule {
    @Binds abstract fun prefs(prefs: BridgePrefs): IPreferences
    @Binds abstract fun platform(platform: JvmPlatform): PlatformImpl
    @Binds abstract fun images(loader: AssetImageLoader): IImageLoader
    @Binds abstract fun messages(messages: StderrMessages): IScriptMessages
    @Binds abstract fun storage(storage: NoStorage): IStorageProvider
}

@Module
class PreferencesModule {
    @ScriptScope @Provides fun battleConfig(prefs: IPreferences): IBattleConfig = prefs.selectedBattleConfig
    @ScriptScope @Provides fun supportPrefs(config: IBattleConfig): ISupportPreferences = config.support
    @ScriptScope @Provides fun commonSupportPrefs(prefs: IPreferences): ISupportPreferencesCommon = prefs.support
    @ScriptScope @Provides fun gestures(prefs: IPreferences): IGesturesPreferences = prefs.gestures
    @ScriptScope @Provides fun spamConfig(config: IBattleConfig) = SpamConfigPerTeamSlot(config.spam)
    @ScriptScope @Provides fun skillCommand(config: IBattleConfig): AutoSkillCommand = AutoSkillCommand.parse(config.skillCommand)
    @ScriptScope @Provides fun cardPriority(config: IBattleConfig): CardPriorityPerWave = config.cardPriority
    @ScriptScope @Provides fun servantPriority(config: IBattleConfig): ServantPriorityPerWave? =
        if (config.useServantPriority) config.servantPriority else null
}

@Singleton
@ScriptScope
@Component(modules = [LibAutomataModule::class, ScriptsModule::class, PlatformModule::class, PreferencesModule::class])
interface BridgeComponent {
    fun adb(): Adb
    fun api(): IFgoAutomataApi
    fun battle(): Battle
    fun caster(): Caster
    fun servantTracker(): ServantTracker
    fun stageTracker(): StageTracker
    fun state(): BattleState
    fun connectionRetry(): ConnectionRetry
    fun withdraw(): Withdraw
    fun screenshots(): ScreenshotService
}
