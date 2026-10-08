package fgo.bridge

import io.github.fate_grand_automata.scripts.entrypoints.AutoBattle
import io.github.fate_grand_automata.scripts.models.AutoSkillCommand
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject

/**
 * JSON lines on stdin/stdout. Each request is {"cmd": ..., ...}; each reply is
 * {"ok": true, ...} or {"ok": false, "error": ...}. FGA's own logs go to stderr.
 */
fun main() {
    nu.pattern.OpenCV.loadLocally()
    val component = DaggerBridgeComponent.create()
    val flow = Flow(component)
    val out = System.out

    reply(out, buildJsonObject { put("ok", true); put("ready", true) })
    while (true) {
        val line = readlnOrNull() ?: break
        if (line.isBlank()) continue
        val response = try {
            handle(flow, Json.parseToJsonElement(line).jsonObject)
        } catch (e: Exception) {
            buildJsonObject {
                put("ok", false)
                put("error", "${e.javaClass.simpleName}: ${e.message}")
            }
        }
        reply(out, response)
        if (response["quit"] != null) break
    }
    component.screenshots().close()
    component.adb().close()
}

private fun reply(out: java.io.PrintStream, json: JsonObject) {
    out.println(json.toString())
    out.flush()
}

private fun JsonObject.ints(key: String) = this[key]?.jsonArray?.map { it.jsonPrimitive.int } ?: emptyList()

private fun handle(flow: Flow, request: JsonObject): JsonObject = buildJsonObject {
    put("ok", true)
    when (val cmd = request["cmd"]?.jsonPrimitive?.content) {
        "screen" -> put("screen", flow.screen())
        "advance" -> {
            val screen = flow.advance(request["timeout"]?.jsonPrimitive?.int ?: 120)
            put("screen", screen)
            if (screen == "battle") put("battle", toJson(flow.battleInfo()))
        }
        "act" -> flow.act(request["command"]!!.jsonPrimitive.content)
        "cards" -> putJsonArray("cards") {
            for (card in flow.cards()) {
                add(buildJsonObject {
                    put("card", card.card.index)
                    put("type", card.type.name.lowercase())
                    put("affinity", card.affinity.name.lowercase())
                    put("stunned", card.isStunned)
                    put("servant", card.servant.position)
                    put("field_slot", card.fieldSlot?.position)
                })
            }
        }
        "back" -> flow.back()
        "play" -> flow.play(request.ints("nps"), request.ints("cards"), request["cards_before_np"]?.jsonPrimitive?.int ?: 0)
        "battle" -> put("battle", toJson(flow.battleInfo()))
        "farm" -> farm(flow, request["command"]!!.jsonPrimitive.content, this)
        "quit" -> put("quit", true)
        else -> error("unknown cmd $cmd")
    }
}

/**
 * FGA's own battle loop (AutoBattle) with a saved plan: it plays every turn from the skill
 * command with its card priority, taps through results and Repeat, and stops at the next
 * support select (support selection is Manual: the agent picks), at an empty AP bar (no refill
 * resources are configured, so FGA never spends apples or Saint Quartz), or on any other stop.
 * A fresh component per call, so the command is parsed anew and FGA's battle state starts clean.
 */
private fun farm(flow: Flow, command: String, out: kotlinx.serialization.json.JsonObjectBuilder) {
    AutoSkillCommand.parse(command)  // a bad command fails here, before anything taps
    FarmCommand.skillCommand = command
    val component = DaggerBridgeComponent.create()
    try {
        component.autoBattle().script()
    } catch (e: AutoBattle.ExitException) {
        out.put("exit", e.reason::class.simpleName)
        e.reason.cause?.let { out.put("error", "${it.javaClass.simpleName}: ${it.message}") }
        out.put("runs", e.state.timesRan)
        if (e.state.timesRan > 0) {
            out.put("min_turns", e.state.minTurnsPerRun)
            out.put("max_turns", e.state.maxTurnsPerRun)
        }
    } finally {
        component.screenshots().close()
        component.adb().close()
        flow.afterFarm()
    }
}

private fun toJson(value: Any?): JsonElement = when (value) {
    null -> JsonNull
    is Number -> JsonPrimitive(value)
    is String -> JsonPrimitive(value)
    is Boolean -> JsonPrimitive(value)
    is Map<*, *> -> JsonObject(value.entries.associate { (k, v) -> k.toString() to toJson(v) })
    else -> JsonPrimitive(value.toString())
}
