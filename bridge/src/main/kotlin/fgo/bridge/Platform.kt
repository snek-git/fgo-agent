package fgo.bridge

import io.github.fate_grand_automata.IStorageProvider
import io.github.fate_grand_automata.SupportImageKind
import io.github.fate_grand_automata.scripts.IImageLoader
import io.github.fate_grand_automata.scripts.IScriptMessages
import io.github.fate_grand_automata.scripts.Images
import io.github.fate_grand_automata.scripts.ScriptLog
import io.github.fate_grand_automata.scripts.ScriptNotify
import io.github.fate_grand_automata.scripts.enums.GameServer
import io.github.fate_grand_automata.scripts.enums.GameServers
import io.github.fate_grand_automata.scripts.enums.MaterialEnum
import io.github.fate_grand_automata.scripts.prefs.IPreferences
import io.github.lib_automata.ColorManager
import io.github.lib_automata.HighlightColor
import io.github.lib_automata.OcrService
import io.github.lib_automata.Pattern
import io.github.lib_automata.PlatformImpl
import io.github.lib_automata.PlatformPrefs
import io.github.lib_automata.Region
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.time.Duration

@Singleton
class JvmPlatform @Inject constructor(
    adb: Adb,
    private val preferences: IPreferences
) : PlatformImpl {
    override val windowRegion: Region = adb.screencap().let { (width, height) -> Region(0, 0, width, height) }
    override val canLongSwipe = true
    override val prefs: PlatformPrefs get() = preferences.platformPrefs
    override fun getResizableBlankPattern(): Pattern = CvPattern()
    override fun highlight(region: Region, duration: Duration, color: HighlightColor) {}
}

/** FGA's ImageLoader: per-server template from FGA's assets, falling back to En. */
@Singleton
class AssetImageLoader @Inject constructor(
    private val prefs: IPreferences,
    private val colorManager: ColorManager
) : IImageLoader {
    private val assets = File(System.getProperty("fga.assets") ?: error("-Dfga.assets is not set"))

    private data class Key(val name: String, val server: GameServer?, val isColor: Boolean)

    private val cache = mutableMapOf<Key, Pattern>()

    private fun load(server: GameServer, name: String): Pattern {
        val own = assets.resolve("${server.simple}/$name")
        val file = if (own.exists()) own else assets.resolve("${GameServers.default.simple}/$name")
        return file.inputStream().use { CvPattern(it, colorManager.isColor, "${server.simple}/$name") }
    }

    override fun get(img: Images, gameServer: GameServer?): Pattern = synchronized(cache) {
        cache.getOrPut(Key(img.path, gameServer, colorManager.isColor)) {
            load(gameServer ?: prefs.gameServer, img.path)
        }
    }

    override fun loadSupportPattern(kind: SupportImageKind, name: String): List<Pattern> =
        throw UnsupportedOperationException("support images are not set up in the bridge")

    override fun loadMaterial(material: MaterialEnum): Pattern =
        throw UnsupportedOperationException("material tracking is not set up in the bridge")

    override fun clearImageCache() = synchronized(cache) {
        cache.values.forEach { it.close() }
        cache.clear()
    }

    override fun clearSupportCache() {}
}

/** FGA's script messages go to stderr; stdout carries the bridge protocol. */
@Singleton
class StderrMessages @Inject constructor() : IScriptMessages {
    override fun notify(action: ScriptNotify) = System.err.println("[fga] notify ${action.javaClass.simpleName}")
    override fun log(item: ScriptLog) = System.err.println("[fga] ${describe(item)}")

    private fun describe(item: ScriptLog) = when (item) {
        is ScriptLog.ClickingNPs -> "clicking NPs ${item.nps.toList()}"
        is ScriptLog.ClickingCards -> "clicking cards ${item.cards.toList()}"
        is ScriptLog.ServantEnteredSlot -> "servant ${item.servant} entered slot ${item.slot}"
        is ScriptLog.CardsBelongToServant -> "cards ${item.cards.toList()} belong to ${item.servant}"
        else -> item.javaClass.simpleName
    }
}

/** Only the battle modules run in the bridge; they never touch storage or OCR. */
class NoStorage @Inject constructor() : IStorageProvider {
    override val supportImageTempDir: File get() = throw UnsupportedOperationException()
    override fun writeSupportImage(kind: SupportImageKind, name: String): OutputStream = throw UnsupportedOperationException()
    override fun readSupportImage(kind: SupportImageKind, name: String): List<InputStream> = emptyList()
    override fun list(kind: SupportImageKind): List<String> = emptyList()
    override fun dropScreenshot(patterns: List<Pattern>) {}
    override fun dropBondScreenShot(pattern: Pattern, server: GameServer) {}
    override fun dump(name: String, image: Pattern) {}
    override fun createNoMediaFile() {}
}

class NoOcr @Inject constructor() : OcrService {
    override fun detectText(pattern: Pattern): String = throw UnsupportedOperationException("no OCR in the bridge")
    override fun close() {}
}
