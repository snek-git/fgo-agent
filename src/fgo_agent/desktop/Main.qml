import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    width: 1280; height: 860
    minimumWidth: 720; minimumHeight: 520
    visible: true
    title: "Chaldea Terminal"
    color: bg
    // Controls (spin boxes, text areas, dialogs) take these instead of the light defaults
    palette.base: "#0a1124"; palette.text: txt; palette.window: "#121d3d"; palette.windowText: txt
    palette.button: "#1a2a56"; palette.buttonText: gold; palette.mid: "#1a2a56"; palette.light: "#26386e"
    palette.dark: "#0e1630"; palette.highlight: gold2; palette.highlightedText: "#1b1406"
    palette.placeholderText: dim

    property string apiBase: ""
    property string startupError: ""
    property var board: null
    property var queue: ({tasks: [], runner: false, agent: false, syncing: false})
    property string filter: "all"
    property var selected: ({})
    property int selectedCount: 0
    property int tab: 0

    readonly property color bg: "#070b18"
    readonly property color bg2: "#0e1630"
    readonly property color panel: "#cc121d3d"
    readonly property color panel2: "#b31a2a56"
    readonly property color line: "#73c9a24b"
    readonly property color gold: "#e3c172"
    readonly property color gold2: "#b98a32"
    readonly property color txt: "#e9ecf5"
    readonly property color dim: "#96a3c4"
    readonly property color blue: "#59c8ff"
    readonly property color red: "#ff6b7a"
    readonly property color green: "#6ee7a8"
    readonly property string serif: cinzel.status === FontLoader.Ready ? cinzel.font.family : "Noto Serif"
    readonly property string sans: "Noto Sans CJK JP"

    FontLoader { id: cinzel; source: "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf" }

    function api(method, path, body, done) {
        const xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            let data = null
            try { data = JSON.parse(xhr.responseText) } catch (e) {}
            if (xhr.status >= 200 && xhr.status < 300) { if (done) done(data) }
            else toast.show((data && data.error) || ("request failed: " + xhr.status))
        }
        xhr.open(method, apiBase + path)
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send(body ? JSON.stringify(body) : null)
    }
    function loadBoard() { api("GET", "/api/board", null, function (b) { board = b }) }
    function loadQueue() { api("GET", "/api/queue", null, function (q) { queue = q }) }
    function fmt(n) { return Number(n).toLocaleString(Qt.locale("en_US"), "f", 0) }
    function openQuests() {
        if (!board) return []
        return board.quests.open.filter(function (q) {
            return filter === "all" || (filter === "fav" ? q.favorite : q.kind === filter)
        })
    }
    function lockedGroups() {
        if (!board) return []
        const groups = {}
        board.quests.locked.forEach(function (q) {
            const key = q.missing.map(function (m) {
                return m.replace(/\d+ \(has \d+\)/, "").replace(/clear quest .*/, "story quest").trim()
            }).join(" + ")
            ;(groups[key] = groups[key] || []).push(q)
        })
        return Object.keys(groups).map(function (k) { return {key: k, quests: groups[k]} })
                     .sort(function (a, b) { return b.quests.length - a.quests.length })
    }
    function toggle(q) {
        const s = Object.assign({}, selected)
        if (s[q.quest_id]) delete s[q.quest_id]; else s[q.quest_id] = q
        selected = s
        selectedCount = Object.keys(s).length
    }
    function activeOrders() {
        return queue.tasks.filter(function (t) { return t.status === "queued" || t.status === "running" }).length
    }

    Component.onCompleted: {
        if (startupError) { toast.show(startupError); return }
        loadBoard(); loadQueue()
    }
    Timer { interval: 5000; running: !startupError; repeat: true; onTriggered: loadQueue() }
    Timer { interval: 60000; running: !startupError; repeat: true; onTriggered: loadBoard() }

    background: Rectangle {
        gradient: Gradient {
            GradientStop { position: 0; color: bg2 }
            GradientStop { position: 1; color: bg }
        }
        Rectangle {  // the faint glow of a summoning circle behind everything
            width: parent.width * 0.9; height: width; radius: width / 2
            anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.55
            color: "transparent"; border.color: "#0affffff"; border.width: 1
            Rectangle { anchors.centerIn: parent; width: parent.width * 0.78; height: width; radius: width / 2
                        color: "transparent"; border.color: "#08e3c172"; border.width: 1 }
        }
    }

    // ---------- shared pieces ----------
    component GoldButton: Button {
        id: b
        property bool ghost: false
        font.family: serif; font.pixelSize: 12; font.weight: Font.DemiBold; font.letterSpacing: 1
        contentItem: Text { text: b.text; font: b.font; color: b.ghost ? gold : "#1b1406"
                            opacity: b.enabled ? 1 : 0.45; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle {
            radius: 4; implicitHeight: 30; implicitWidth: 70
            border.color: b.ghost ? line : "#6b4d17"; border.width: 1
            opacity: b.enabled ? 1 : 0.45
            gradient: b.ghost ? null : goldGrad
            color: b.ghost ? (b.hovered ? "#22e3c172" : "transparent") : gold
        }
    }
    Gradient { id: goldGrad; GradientStop { position: 0; color: "#f3dc9b" } GradientStop { position: 0.45; color: gold } GradientStop { position: 1; color: gold2 } }

    component Panel: Rectangle {
        default property alias body: inner.data
        property string heading: ""
        property string sub: ""
        color: panel; radius: 6; border.color: line; border.width: 1
        implicitHeight: inner.implicitHeight + head.height + 32
        Rectangle { width: 10; height: 2; color: gold; x: -1; y: -1 } Rectangle { width: 2; height: 10; color: gold; x: -1; y: -1 }
        Rectangle { width: 10; height: 2; color: gold; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: -1 }
        Rectangle { width: 2; height: 10; color: gold; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: -1 }
        Row {
            id: head; x: 16; y: 12; spacing: 10; height: heading ? 22 : 0; visible: heading !== ""
            Text { text: heading; color: gold; font.family: serif; font.pixelSize: 15; font.bold: true; font.letterSpacing: 1 }
            Text { text: sub; color: dim; font.family: sans; font.pixelSize: 12; anchors.baseline: parent.children[0].baseline }
        }
        Column { id: inner; x: 16; y: head.height + 20; width: parent.width - 32; spacing: 8 }
    }

    component Face: Item {
        property var s
        width: 58; height: 58
        Rectangle { anchors.fill: parent; radius: 4; color: "#0a1022"
                    border.width: 2; border.color: !s ? gold2 : s.rarity >= 4 ? gold2 : s.rarity === 3 ? "#c7d2e6" : "#c98a5a"
            Image { anchors.fill: parent; anchors.margins: 2; source: s ? s.face : ""; asynchronous: true; fillMode: Image.PreserveAspectCrop } }
        Image { x: -6; y: -6; width: 24; height: 24; source: s ? s.class_icon : ""; asynchronous: true }
        Text { visible: s && s.favorite; text: "★"; color: gold; font.pixelSize: 16; x: parent.width - 10; y: -8; style: Text.Outline; styleColor: "black" }
    }

    component Tag: Rectangle {
        property string label
        property color tint: blue
        radius: 3; color: "transparent"; border.color: tint; border.width: 1
        implicitWidth: t.implicitWidth + 12; implicitHeight: 16
        Text { id: t; anchors.centerIn: parent; text: label.toUpperCase(); color: tint; font.family: serif; font.pixelSize: 9; font.bold: true; font.letterSpacing: 1 }
    }

    // ---------- header ----------
    header: Rectangle {
        color: "#f2070b18"; height: 104
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: line }
        RowLayout {
            x: 18; y: 12; width: parent.width - 36; spacing: 14
            Rectangle {
                width: 42; height: 42; radius: 21; border.color: gold; border.width: 2
                gradient: Gradient { GradientStop { position: 0; color: "#1a2a56" } GradientStop { position: 1; color: "#0b1330" } }
                Text { anchors.centerIn: parent; text: "C"; color: gold; font.family: serif; font.pixelSize: 18; font.bold: true }
            }
            Column {
                Text { text: "CHALDEA TERMINAL"; color: gold; font.family: serif; font.pixelSize: 20; font.bold: true; font.letterSpacing: 2 }
                Text { color: dim; font.family: sans; font.pixelSize: 11; font.letterSpacing: 1
                       text: board ? ("MASTER LV." + board.resources.level + "  ·  AP " + board.resources.ap_max + "  ·  COST " + board.resources.cost_max) : "loading" }
            }
            Item { Layout.fillWidth: true }
            Repeater {
                model: board ? [["gold", board.resources.apples.gold], ["silver", board.resources.apples.silver],
                                ["bronze", board.resources.apples.bronze], ["saint_quartz", board.resources.saint_quartz],
                                ["qp", (board.resources.qp / 1e8).toFixed(1) + " 億"]] : []
                Rectangle {
                    radius: 13; height: 28; width: chipRow.implicitWidth + 16; color: panel2; border.color: "#4dc9a24b"
                    Row { id: chipRow; anchors.centerIn: parent; spacing: 6
                        Image { width: 22; height: 22; source: board.resources.icons[modelData[0]]; asynchronous: true }
                        Text { text: typeof modelData[1] === "number" ? fmt(modelData[1]) : modelData[1]; color: txt; font.family: sans; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter } }
                }
            }
            Text { color: dim; font.pixelSize: 12; font.family: sans
                   text: board ? ("synced " + Math.round((Date.now() / 1000 - board.synced_at) / 3600) + " h ago") : "" }
            GoldButton { ghost: true; text: queue.syncing ? "SYNCING" : "SYNC"; enabled: !queue.runner && !queue.agent && !queue.syncing
                         onClicked: api("POST", "/api/sync", null, function (q) { queue = q; toast.show("syncing: FGO restarts once") }) }
            GoldButton { ghost: true; text: "LIVE"; onClicked: Qt.openUrlExternally(apiBase + "/") }
        }
        Row {
            x: 18; anchors.bottom: parent.bottom; spacing: 2
            Repeater {
                model: [["Interludes & Strengthening", board ? board.quests.open.length : ""],
                        ["Ascension & Skills", board ? board.upgrades.servants.length : ""],
                        ["Story & Free Quests", board ? board.story.reduce(function (n, w) { return n + w.main.length + w.free.length }, 0) : ""],
                        ["Farming", board ? board.farms.length || "" : ""], ["Orders", activeOrders() || ""]]
                Rectangle {
                    height: 36; width: tabText.implicitWidth + 32; radius: 6
                    color: tab === index ? panel : "transparent"; border.color: tab === index ? line : "transparent"
                    Text { id: tabText; anchors.centerIn: parent; textFormat: Text.RichText
                           text: modelData[0].toUpperCase() + (modelData[1] !== "" ? "  <font color='#59c8ff'>" + modelData[1] + "</font>" : "")
                           color: tab === index ? gold : dim; font.family: serif; font.pixelSize: 13; font.letterSpacing: 1 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tab = index }
                }
            }
        }
    }

    // ---------- pages ----------
    StackLayout {
        anchors.fill: parent; anchors.margins: 18; anchors.bottomMargin: selectedCount ? 64 : 18
        currentIndex: tab

        // Interludes & strengthening
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column {
                width: parent.width; spacing: 14
                Row {
                    spacing: 6
                    Repeater {
                        model: [["all", "All open"], ["fav", "★ Favourites"], ["interlude", "Interludes"], ["strengthening", "Strengthening"]]
                        GoldButton { ghost: filter !== modelData[0]; text: modelData[1].toUpperCase(); onClicked: filter = modelData[0] }
                    }
                }
                Panel {
                    width: parent.width; heading: "Open now"; sub: "click to select, then send the agent"
                    Flow {
                        width: parent.width; spacing: 10
                        Repeater {
                            model: openQuests()
                            Rectangle {
                                property bool sel: !!selected[modelData.quest_id]
                                readonly property int cols: Math.max(1, Math.floor((parent.width + 10) / 290))
                                width: Math.floor((parent.width - (cols - 1) * 10) / cols)
                                height: 76; radius: 6; border.width: sel ? 2 : 1
                                border.color: sel ? gold : (hover.containsMouse ? "#99e3c172" : "#2e59c8ff")
                                gradient: Gradient { orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: "#b31f3468" } GradientStop { position: 1; color: "#cc0e1630" } }
                                Face { s: modelData.servant; x: 9; anchors.verticalCenter: parent.verticalCenter }
                                Column {
                                    x: 78; width: parent.width - 88; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                                    Text { text: modelData.servant.name; color: txt; font.family: sans; font.bold: true; width: parent.width; elide: Text.ElideRight }
                                    Text { text: modelData.name; color: gold; font.family: sans; font.pixelSize: 13; width: parent.width; elide: Text.ElideRight }
                                    Row { spacing: 8
                                        Tag { label: modelData.kind; tint: modelData.kind === "interlude" ? "#b9a0ff" : blue }
                                        Text { text: (modelData.ap || "?") + " AP  ·  " + modelData.phases + " phase" + (modelData.phases > 1 ? "s" : ""); color: dim; font.pixelSize: 12 } }
                                }
                                MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: toggle(modelData) }
                            }
                        }
                    }
                }
                Panel {
                    width: parent.width; heading: "Locked"; sub: "what each one still needs"
                    Repeater {
                        model: lockedGroups()
                        Column {
                            width: parent.width; spacing: 4
                            property bool open: false
                            Text { text: (open ? "▾ " : "▸ ") + "needs " + modelData.key + " (" + modelData.quests.length + ")"; color: dim; font.family: sans
                                   MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.parent.open = !parent.parent.open } }
                            Repeater {
                                model: parent.open ? modelData.quests : []
                                Row { spacing: 10; Face { s: modelData.servant; scale: 0.8 }
                                    Column { anchors.verticalCenter: parent.verticalCenter
                                        Text { text: modelData.servant.name + "  ·  " + modelData.name; color: txt; font.family: sans; font.pixelSize: 13 }
                                        Text { text: modelData.missing.join(", "); color: red; font.pixelSize: 12 } } }
                            }
                        }
                    }
                }
            }
        }

        // Ascension & skills
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column {
                width: parent.width; spacing: 14
                Panel {
                    width: parent.width; heading: "Materials short"
                    sub: board ? ("QP needed " + fmt(board.upgrades.qp.need) + " of " + fmt(board.upgrades.qp.have)) : ""
                    Flow {
                        width: parent.width; spacing: 8
                        Repeater {
                            model: board ? board.upgrades.missing : []
                            Rectangle {
                                width: 214; height: 50; radius: 6; color: panel2
                                Image { x: 8; anchors.verticalCenter: parent.verticalCenter; width: 36; height: 36; source: modelData.icon; asynchronous: true }
                                Column { x: 52; width: 96; anchors.verticalCenter: parent.verticalCenter
                                    Text { text: modelData.name; color: txt; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
                                    Text { text: "-" + fmt(modelData.missing); color: red; font.family: serif; font.bold: true; font.pixelSize: 16 } }
                                GoldButton { text: "FARM"; anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                             implicitWidth: 52; onClicked: farmDialog.ask(modelData.name, modelData.missing) }
                            }
                        }
                    }
                }
                Panel {
                    width: parent.width; heading: "Servants"; sub: "targets from your Chaldea plan"
                    Repeater {
                        model: board ? board.upgrades.servants : []
                        Row {
                            width: parent.width; spacing: 12
                            Face { s: modelData }
                            Column {
                                width: parent.width - 70; spacing: 4
                                Row { spacing: 8
                                    Text { text: modelData.name; color: txt; font.family: sans; font.bold: true }
                                    Tag { label: modelData.can_do ? "ready" : "short"; tint: modelData.can_do ? green : red } }
                                Text { color: dim; font.pixelSize: 12; font.family: serif
                                       text: "Ascension " + modelData.current.ascension + " → " + modelData.target.ascension
                                             + "   Skills " + modelData.current.skills.join("/") + " → " + modelData.target.skills.join("/")
                                             + "   Appends " + modelData.current.appends.join("/") + " → " + modelData.target.appends.join("/")
                                             + "   QP " + fmt(modelData.qp) }
                                Flow { width: parent.width; spacing: 6
                                    Repeater { model: modelData.materials
                                        Column { width: 46
                                            Image { width: 40; height: 40; source: modelData.icon; asynchronous: true; anchors.horizontalCenter: parent.horizontalCenter }
                                            Text { text: fmt(modelData.have) + "/" + fmt(modelData.need); color: modelData.have >= modelData.need ? green : red
                                                   font.pixelSize: 10; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter } } } }
                            }
                        }
                    }
                }
            }
        }

        // Story & free quests
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column {
                width: parent.width; spacing: 14
                Repeater {
                    model: board ? board.story : []
                    Panel {
                        width: parent.width
                        RowLayout {
                            width: parent.width; spacing: 12
                            Image { source: modelData.banner || ""; Layout.preferredHeight: 54; Layout.preferredWidth: modelData.banner ? 160 : 0; fillMode: Image.PreserveAspectFit; asynchronous: true }
                            Column { Layout.fillWidth: true
                                Text { text: modelData.name; color: gold; font.family: serif; font.pixelSize: 15; font.bold: true; width: parent.width; elide: Text.ElideRight }
                                Text { color: dim; font.pixelSize: 12
                                       text: modelData.main.length + " story quests  ·  " + modelData.free.length + " free quests" + (modelData.free.length ? " (Saint Quartz on first clear)" : "") } }
                            GoldButton { text: "SEND THE AGENT"; implicitWidth: 130
                                onClicked: api("POST", "/api/queue", {kind: "story", title: "Clear " + modelData.name, apples: 10,
                                    payload: {war: modelData.war, war_name: modelData.name,
                                              quests: modelData.main.concat(modelData.free).map(function (q) { return {quest_id: q.quest_id, name: q.name} })}},
                                    function () { toast.show("story order added"); loadQueue() }) }
                        }
                    }
                }
            }
        }

        // Farming
        ScrollView {
            contentWidth: availableWidth; clip: true
            Panel {
                width: parent.width; heading: "Farming plans"; sub: "found by the agent's exploratory runs, aiming for 3 turns"
                Text { visible: board && board.farms.length === 0; color: dim; font.italic: true
                       text: "no plans yet: press Farm on a short material and the agent explores one" }
                Repeater {
                    model: board ? board.farms : []
                    Column { width: parent.width; spacing: 3
                        Row { spacing: 8
                            Text { text: modelData.quest_name; color: txt; font.bold: true; font.family: sans }
                            Tag { label: modelData.three_turn ? "3-turn verified" : modelData.turns + " turns"; tint: modelData.three_turn ? green : red } }
                        Text { color: dim; font.pixelSize: 12; text: "for " + (modelData.target_item || "?") + "  ·  support " + modelData.support + "  ·  MC " + (modelData.mystic_code || "-") }
                        Text { color: dim; font.pixelSize: 12; text: "party " + modelData.party.join(", ") + "   command " + modelData.skill_command }
                    }
                }
            }
        }

        // Orders
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column {
                width: parent.width; spacing: 14
                Panel {
                    width: parent.width; heading: "Orders for the agent"
                    sub: queue.runner ? "the agent is working through the orders" : queue.agent ? "a separate agent run is playing" : queue.syncing ? "syncing your account" : "idle"
                    Row { spacing: 8
                        GoldButton { text: "RUN ORDERS"; enabled: !queue.runner && !queue.agent && !queue.syncing && activeOrders() > 0
                                     onClicked: api("POST", "/api/queue/run", null, function (q) { queue = q; toast.show("the agent is on it") }) }
                        GoldButton { text: "STOP"; ghost: true; enabled: queue.runner; onClicked: api("POST", "/api/queue/stop", null, function (q) { queue = q }) } }
                    Text { visible: queue.tasks.length === 0; text: "no orders yet"; color: dim; font.italic: true }
                    Repeater {
                        model: queue.tasks.slice().reverse()
                        RowLayout { width: parent.width; spacing: 10
                            Tag { label: modelData.status; tint: modelData.status === "running" ? blue : modelData.status === "done" ? green
                                                                 : modelData.status === "queued" ? dim : red }
                            Column { Layout.fillWidth: true
                                Text { text: modelData.title; color: txt; font.family: sans; width: parent.width; elide: Text.ElideRight }
                                Text { color: dim; font.pixelSize: 12
                                       text: modelData.kind + (modelData.apples !== null && modelData.apples !== undefined ? "  ·  ≤" + modelData.apples + " apples" : "")
                                             + (modelData.cost ? "  ·  $" + modelData.cost.toFixed(2) : "") } }
                            GoldButton { ghost: true; text: "✕"; implicitWidth: 34; visible: modelData.status !== "running"
                                         onClicked: api("DELETE", "/api/queue/" + modelData.id, null, function (q) { queue = q }) }
                        }
                    }
                }
                Panel {
                    width: parent.width; heading: "Custom order"
                    TextArea { id: custom; width: parent.width; height: 70; color: txt; placeholderText: "Anything else, in plain words"
                               placeholderTextColor: dim; background: Rectangle { color: "#0a1124"; border.color: line; radius: 4 } }
                    Row { spacing: 8
                        Text { text: "apple budget"; color: dim; anchors.verticalCenter: parent.verticalCenter }
                        SpinBox { id: customApples; from: 0; to: 200; value: 5 }
                        GoldButton { text: "ADD ORDER"; onClicked: {
                            if (!custom.text.trim()) return
                            api("POST", "/api/queue", {kind: "custom", title: custom.text.trim().slice(0, 80), payload: {text: custom.text.trim()}, apples: customApples.value},
                                function () { custom.text = ""; loadQueue() }) } } }
                }
            }
        }
    }

    // ---------- selection bar, dialogs, toast ----------
    Rectangle {
        visible: selectedCount > 0
        anchors.bottom: parent.bottom; width: parent.width; height: 56; color: "#f2070b18"
        Rectangle { width: parent.width; height: 1; color: line }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 18; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            Text { text: selectedCount + " quest" + (selectedCount === 1 ? "" : "s") + " selected"; color: txt; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "apple budget"; color: dim; anchors.verticalCenter: parent.verticalCenter }
            SpinBox { id: barApples; from: 0; to: 200; value: 10 }
            GoldButton { ghost: true; text: "CLEAR"; onClicked: { selected = {}; selectedCount = 0 } }
            GoldButton { text: "SEND THE AGENT"; implicitWidth: 130; onClicked: {
                const qs = Object.keys(selected).map(function (k) { return selected[k] })
                const names = qs.slice(0, 3).map(function (q) { return q.servant.name }).join(", ") + (qs.length > 3 ? "…" : "")
                api("POST", "/api/queue", {kind: "quests", title: "Clear " + qs.length + " quests: " + names, apples: barApples.value,
                    payload: {quests: qs.map(function (q) { return {quest_id: q.quest_id, name: q.name, who: q.servant.name + "'s " + q.kind} })}},
                    function () { selected = {}; selectedCount = 0; toast.show("order added: see Orders"); loadQueue() }) } }
        }
    }

    Dialog {
        id: farmDialog
        property string item: ""
        function ask(name, n) { item = name; farmCount.value = n; open() }
        anchors.centerIn: parent; modal: true; title: "Farm " + item
        background: Rectangle { color: panel; border.color: gold; radius: 6 }
        Column { spacing: 10
            Row { spacing: 8; Text { text: "how many"; color: txt; anchors.verticalCenter: parent.verticalCenter } SpinBox { id: farmCount; from: 1; to: 9999; editable: true } }
            Row { spacing: 8; Text { text: "apple budget"; color: txt; anchors.verticalCenter: parent.verticalCenter } SpinBox { id: farmApples; from: 0; to: 500; value: 20; editable: true } }
            Text { width: 300; wrapMode: Text.Wrap; color: dim; font.pixelSize: 12
                   text: "The agent finds a 3-turn plan with up to 3 exploratory runs, saves it, then farms with it." }
        }
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: api("POST", "/api/queue", {kind: "farm", title: "Farm " + farmCount.value + " " + item, apples: farmApples.value,
                                              payload: {item: item, count: farmCount.value}}, function () { toast.show("farm order added"); loadQueue() })
    }

    Rectangle {
        id: toast
        function show(text) { msg.text = text; visible = true; hide.restart() }
        visible: false; z: 10; radius: 6; color: panel; border.color: gold
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 18; anchors.bottomMargin: 76
        width: Math.min(msg.implicitWidth + 28, win.width - 36); height: msg.implicitHeight + 20
        Text { id: msg; anchors.centerIn: parent; width: parent.width - 28; color: txt; wrapMode: Text.Wrap }
        Timer { id: hide; interval: 5000; onTriggered: toast.visible = false }
    }
}
