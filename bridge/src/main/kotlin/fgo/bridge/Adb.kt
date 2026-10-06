package fgo.bridge

import io.github.fate_grand_automata.scripts.prefs.IGesturesPreferences
import io.github.lib_automata.ColorManager
import io.github.lib_automata.GestureService
import io.github.lib_automata.Location
import io.github.lib_automata.Pattern
import io.github.lib_automata.ScreenshotService
import io.github.lib_automata.Waiter
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.imgproc.Imgproc
import java.io.BufferedReader
import java.io.Writer
import java.nio.ByteBuffer
import java.nio.ByteOrder
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class Adb @Inject constructor() : AutoCloseable {
    val serial: String = System.getenv("FGO_SERIAL") ?: "127.0.0.1:5555"

    // One long-lived shell for input commands: no adb process spawn per tap.
    private val shell = ProcessBuilder("adb", "-s", serial, "shell").redirectErrorStream(true).start()
    private val shellIn: Writer = shell.outputStream.bufferedWriter()
    private val shellOut: BufferedReader = shell.inputStream.bufferedReader()
    private var marker = 0

    /** Run a command in the persistent shell and wait for it to finish. */
    @Synchronized
    fun run(command: String) {
        val done = "__fga_done_${marker++}__"
        shellIn.write("$command; echo $done\n")
        shellIn.flush()
        while (true) {
            val line = shellOut.readLine() ?: error("adb shell closed")
            if (line.trim() == done) return
        }
    }

    /** Raw RGBA framebuffer (no PNG encode on the device). */
    fun screencap(): Triple<Int, Int, ByteArray> {
        val process = ProcessBuilder("adb", "-s", serial, "exec-out", "screencap").start()
        val raw = process.inputStream.readBytes()
        check(process.waitFor() == 0 && raw.size > 16) { "screencap failed" }
        val header = ByteBuffer.wrap(raw, 0, 8).order(ByteOrder.LITTLE_ENDIAN)
        val width = header.int
        val height = header.int
        val offset = raw.size - width * height * 4
        return Triple(width, height, raw.copyOfRange(offset, raw.size))
    }

    override fun close() {
        shellIn.write("exit\n")
        shellIn.flush()
        shell.destroy()
    }
}

/** FGA's ScreenshotService over adb screencap. Grayscale unless a script asked for color. */
class AdbScreenshotService @Inject constructor(
    private val adb: Adb,
    private val colorManager: ColorManager
) : ScreenshotService {
    private val rgba = Mat()
    private val gray = CvPattern(Mat(), ownsMat = true)
    private val color = CvPattern(Mat(), ownsMat = true)

    override fun takeScreenshot(): Pattern {
        val (width, height, bytes) = adb.screencap()
        rgba.create(height, width, CvType.CV_8UC4)
        rgba.put(0, 0, bytes)
        return if (colorManager.isColor) {
            Imgproc.cvtColor(rgba, color.mat, Imgproc.COLOR_RGBA2BGR)
            color
        } else {
            Imgproc.cvtColor(rgba, gray.mat, Imgproc.COLOR_RGBA2GRAY)
            gray
        }
    }

    override fun startRecording(): AutoCloseable? = null

    override fun close() {
        rgba.release()
        gray.close()
        color.close()
    }
}

/** FGA's GestureService over adb input. Waits match FGA's AccessibilityGestures. */
class AdbGestures @Inject constructor(
    private val adb: Adb,
    private val gestures: IGesturesPreferences,
    private val wait: Waiter
) : GestureService {
    override fun click(location: Location, times: Int) {
        repeat(times) { adb.run("input tap ${location.x} ${location.y}") }
        wait(gestures.clickWaitTime)
    }

    override fun swipe(start: Location, end: Location) {
        adb.run("input swipe ${start.x} ${start.y} ${end.x} ${end.y} ${gestures.swipeDuration.inWholeMilliseconds}")
        wait(gestures.swipeWaitTime)
    }

    override fun close() {}
}
