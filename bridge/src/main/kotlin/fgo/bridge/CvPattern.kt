package fgo.bridge

import io.github.lib_automata.Match
import io.github.lib_automata.Pattern
import io.github.lib_automata.Region
import io.github.lib_automata.Size
import org.opencv.core.Core
import org.opencv.core.Mat
import org.opencv.core.MatOfByte
import org.opencv.core.MatOfPoint
import org.opencv.core.Point
import org.opencv.core.Rect
import org.opencv.core.Scalar
import org.opencv.imgcodecs.Imgcodecs
import org.opencv.imgproc.Imgproc
import java.io.InputStream
import java.io.OutputStream
import kotlin.math.roundToInt
import org.opencv.core.Size as CvSize

inline fun <T : Mat, R> T.use(block: (T) -> R) =
    try {
        block(this)
    } finally {
        release()
    }

/** Desktop port of FGA's DroidCvPattern (app/imaging). Same OpenCV calls, no Android types. */
class CvPattern(
    var mat: Mat = Mat(),
    private val ownsMat: Boolean = true,
    override var tag: String = ""
) : Pattern {
    private companion object {
        fun makeMat(stream: InputStream, isColor: Boolean): Mat =
            MatOfByte(*stream.readBytes()).use {
                Imgcodecs.imdecode(it, if (isColor) Imgcodecs.IMREAD_COLOR else Imgcodecs.IMREAD_GRAYSCALE)
            }
    }

    constructor(stream: InputStream, isColor: Boolean, tag: String = "") : this(makeMat(stream, isColor), tag = tag)

    override fun toString() = tag.ifBlank { super.toString() }

    override fun close() {
        if (ownsMat) mat.release()
    }

    private fun resize(source: Mat, target: Mat, size: Size) {
        Imgproc.resize(
            source, target,
            CvSize(size.width.toDouble(), size.height.toDouble()),
            0.0, 0.0, Imgproc.INTER_AREA
        )
    }

    override fun resize(size: Size): Pattern =
        CvPattern(Mat().apply { resize(mat, this, size) }, tag = tag)

    override fun resize(target: Pattern, size: Size) {
        if (target is CvPattern) resize(mat, target.mat, size)
        target.tag = tag
    }

    private fun match(template: Pattern): Mat? {
        if (template !is CvPattern || template.width > width || template.height > height) return null
        val result = Mat()
        Imgproc.matchTemplate(mat, template.mat, result, Imgproc.TM_CCOEFF_NORMED)
        return result
    }

    override fun findMatches(template: Pattern, similarity: Double) = sequence {
        val result = match(template) ?: return@sequence
        result.use {
            while (true) {
                val minMax = Core.minMaxLoc(it)
                if (minMax.maxVal < similarity) break
                val loc = minMax.maxLoc
                yield(Match(Region(loc.x.roundToInt(), loc.y.roundToInt(), template.width, template.height), minMax.maxVal))
                // Flood fill so points next to a strong match don't match again
                it.floodFill(loc, 0.3, 0.0)
            }
        }
    }

    override val width get() = mat.width()
    override val height get() = mat.height()

    override fun crop(region: Region): Pattern {
        val clipped = Region(0, 0, width, height).clip(region)
        return CvPattern(Mat(mat, Rect(clipped.x, clipped.y, clipped.width, clipped.height)), tag = tag)
    }

    override fun save(stream: OutputStream) {
        MatOfByte().use {
            Imgcodecs.imencode(".png", mat, it)
            stream.write(it.toArray())
        }
    }

    override fun copy() = CvPattern(mat.clone(), tag = tag)

    override fun threshold(value: Double): Pattern {
        val result = Mat()
        Imgproc.threshold(mat, result, value * 255, 255.0, Imgproc.THRESH_BINARY)
        return CvPattern(result, tag = "$tag[threshold=$value]")
    }

    override fun isWhite() = Core.minMaxLoc(mat).minVal >= 200

    override fun isBlack() = Core.minMaxLoc(mat).maxVal <= 55

    override fun floodFill(x: Double, y: Double, maxDiff: Double, newValue: Double): Pattern {
        mat.floodFill(Point(x, y), maxDiff, newValue)
        return this
    }

    override fun fillText(): Pattern {
        val mask = Mat.zeros(CvSize(width + 2.0, height + 2.0), mat.type())
        for (point in pointsInHoles(mat)) {
            Imgproc.floodFill(
                mat, mask, point, Scalar(255.0), Rect(), Scalar(0.0), Scalar(0.0),
                4 + (255 shl 8) + Imgproc.FLOODFILL_MASK_ONLY
            )
        }
        Core.bitwise_not(mask, mask)
        return CvPattern(mask)
    }

    private fun Mat.floodFill(start: Point, maxDiff: Double, newValue: Double) {
        Mat().use { mask ->
            Imgproc.floodFill(
                this, mask, start, Scalar(newValue), Rect(),
                Scalar(maxDiff), Scalar(maxDiff), Imgproc.FLOODFILL_FIXED_RANGE
            )
        }
    }

    private fun pointsInHoles(img: Mat): List<Point> {
        val work = Mat()
        Core.bitwise_not(img, work)
        val contours = mutableListOf<MatOfPoint>()
        val hierarchy = Mat()
        Imgproc.findContours(work, contours, hierarchy, Imgproc.RETR_TREE, Imgproc.CHAIN_APPROX_SIMPLE)
        return contours.withIndex().mapNotNull { (index, contour) ->
            val parent = hierarchy[0, index][3].toInt()
            // top level holes have a parent but no grandparent
            if (parent >= 0 && hierarchy[0, parent][3] < 0) {
                val top = contour.toList().minBy { it.y }
                Point(top.x, top.y + 1.0)
            } else null
        }
    }
}
