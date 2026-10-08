import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes

// Styled after FGO's own JP menus, like the web board: light sky-blue screens, a pale band with
// a white back button on the left and the screen title on the right, a dark strip of blue square
// tab buttons, white panels with a dark header bar, gold Rank Up / blue Interlude quest plates.
ApplicationWindow {
    id: win
    width: 1280; height: 860
    minimumWidth: 760; minimumHeight: 520
    visible: true
    title: "Chaldea Terminal"

    property string apiBase: ""
    property string startupError: ""
    property var board: null
    property var queue: ({tasks: [], runner: false, agent: false, syncing: false})
    property string filter: "all"
    property var selected: ({})
    property int selectedCount: 0
    property int tab: 0

    readonly property color ink: "#10213f"
    readonly property color ink2: "#2a4472"
    readonly property color muted: "#5d7398"
    readonly property color rim: "#7ec2f2"
    readonly property color rim2: "#b9dcf7"
    readonly property color navy1: "#1a2f57"
    readonly property color navy2: "#2a4a80"
    readonly property color red: "#e5484d"
    readonly property color green: "#2f9a58"
    readonly property string sans: "Noto Sans CJK JP"
    readonly property string serif: "Noto Serif"
    readonly property var tabs: [
        {label: "Interludes & Rank Up", title: "Interludes", en: "INTERLUDE & RANK UP QUESTS"},
        {label: "Ascension & Skills", title: "Ascension", en: "ASCENSION & SKILLS"},
        {label: "Story", title: "Story", en: "MAIN & FREE QUESTS"},
        {label: "Farming", title: "Farming", en: "3-TURN PLANS"},
        {label: "Orders", title: "Orders", en: "AGENT ORDERS"}]

    palette.base: "#ffffff"; palette.text: ink; palette.window: "#eef6ff"; palette.windowText: ink
    palette.button: "#dbe8f5"; palette.buttonText: ink; palette.mid: "#b9dcf7"; palette.light: "#ffffff"
    palette.dark: "#7e9cc4"; palette.highlight: "#2f8fe0"; palette.highlightedText: "#ffffff"; palette.placeholderText: muted

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
        return board.quests.open.filter(function (q) { return filter === "all" || (filter === "fav" ? q.favorite : q.kind === filter) })
    }
    function questTitle(q) {
        const m = q.name.match(/(\d+)\s*$/)
        return q.kind === "strengthening" ? q.servant.name + " · Rank Up" + (m ? " " + m[1] : "") : q.servant.name + " · Interlude"
    }
    function cond(m) {
        return m.replace(/^bond (\d+) \(has (\d+)\)$/, "Bond Lv.$1 (now $2)")
                .replace(/^ascension (\d+) \(has (-?\d+)\)$/, "Ascension $1 (now $2)")
                .replace(/^clear quest (.*)$/, "Clear 「$1」")
    }
    function condGroup(m) {
        return m.indexOf("bond") === 0 ? "Bond" : m.indexOf("ascension") === 0 ? "Ascension" : m.indexOf("clear quest") === 0 ? "Story quest" : "Other"
    }
    function lockedGroups() {
        if (!board) return []
        const groups = {}
        board.quests.locked.filter(function (q) { return filter === "all" || (filter === "fav" ? q.favorite : q.kind === filter) }).forEach(function (q) {
            const keys = []
            q.missing.forEach(function (m) { const k = condGroup(m); if (keys.indexOf(k) < 0) keys.push(k) })
            const key = keys.join(" + ")
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
    function activeOrders() { return queue.tasks.filter(function (t) { return t.status === "queued" || t.status === "running" }).length }
    function tabCount(i) {
        if (!board) return 0
        return [board.quests.open.length, board.upgrades.servants.filter(function (s) { return !s.can_do }).length,
                board.story.reduce(function (n, w) { return n + w.main.length + w.free.length }, 0), board.farms.length, activeOrders()][i]
    }

    Component.onCompleted: {
        if (startupError) { toast.show(startupError); return }
        loadBoard(); loadQueue()
    }
    Timer { interval: 5000; running: !startupError; repeat: true; onTriggered: loadQueue() }
    Timer { interval: 60000; running: !startupError; repeat: true; onTriggered: loadBoard() }

    background: Rectangle {
        gradient: Gradient {
            GradientStop { position: 0; color: "#bfe3ff" }
            GradientStop { position: 0.4; color: "#8ccaf6" }
            GradientStop { position: 1; color: "#5eaee9" }
        }
        Canvas {  // the faint diamond lattice of the game's menu backgrounds
            anchors.fill: parent; opacity: 0.12
            onPaint: {
                const ctx = getContext("2d"); ctx.strokeStyle = "white"; ctx.lineWidth = 1
                for (let x = -height; x < width; x += 34) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + height, height); ctx.stroke()
                                                            ctx.beginPath(); ctx.moveTo(x + height, 0); ctx.lineTo(x, height); ctx.stroke() }
            }
        }
    }

    // ---------- shared pieces ----------
    component SqButton: Button {
        id: sb
        property bool light: false
        property bool danger: false
        font.family: sans; font.pixelSize: 13; font.bold: true
        contentItem: Text { text: sb.text; font: sb.font; color: sb.light ? ink : "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle {
            implicitHeight: 30; implicitWidth: 64; radius: 4; opacity: sb.enabled ? 1 : 0.5
            border.color: sb.light ? "#7e9cc4" : sb.danger ? "#ffd0cc" : "#bfe3ff"
            gradient: Gradient {
                GradientStop { position: 0; color: sb.light ? "#ffffff" : sb.danger ? "#ff7a6e" : "#4aa8f0" }
                GradientStop { position: 1; color: sb.light ? "#dbe8f5" : sb.danger ? "#d23b30" : "#1f72c8" }
            }
        }
    }
    component GoButton: Button {
        id: gb
        font.family: sans; font.pixelSize: 15; font.weight: Font.Black
        contentItem: Text { text: gb.text; font: gb.font; color: ink; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle {
            implicitHeight: 40; implicitWidth: 150; radius: height / 2; opacity: gb.enabled ? 1 : 0.5
            border.color: "#2a8be0"; border.width: 3
            gradient: Gradient { GradientStop { position: 0; color: "white" } GradientStop { position: 1; color: "#e6eef6" } }
            Rectangle { anchors.fill: parent; anchors.margins: -4; radius: height / 2; color: "transparent"; border.color: "#7ec2f2"; border.width: 1 }
        }
    }
    component Panel: Rectangle {
        default property alias body: inner.data
        property string heading: ""
        property string sub: ""
        radius: 6; border.color: "white"; border.width: 2
        gradient: Gradient { GradientStop { position: 0; color: "#f5ffffff" } GradientStop { position: 1; color: "#f0e8f4ff" } }
        implicitHeight: inner.implicitHeight + (heading ? 36 : 0) + 26
        Rectangle { anchors.fill: parent; anchors.margins: -1; radius: 7; color: "transparent"; border.color: rim; z: -1 }
        Rectangle {
            visible: heading !== ""; x: 2; y: 2; width: parent.width - 4; height: 32; radius: 4
            gradient: Gradient { GradientStop { position: 0; color: navy1 } GradientStop { position: 1; color: navy2 } }
            Row { x: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                Text { text: heading; color: "white"; font.family: sans; font.bold: true; font.pixelSize: 14 }
                Text { text: sub.toUpperCase(); color: "#9fd0ff"; font.family: sans; font.pixelSize: 10; font.letterSpacing: 4; anchors.verticalCenter: parent.verticalCenter } }
        }
        Column { id: inner; x: 14; y: (heading ? 36 : 0) + 12; width: parent.width - 28; spacing: 8 }
    }
    component Face: Item {
        property var s
        property bool dim: false
        width: 60; height: 60
        Rectangle { anchors.fill: parent; radius: 4; color: "#dfe9f5"; border.color: "white"; border.width: 2
            Image { anchors.fill: parent; anchors.margins: 2; source: s ? s.face : ""; asynchronous: true; fillMode: Image.PreserveAspectCrop; opacity: dim ? 0.55 : 1 } }
        Image { x: -6; y: -6; width: 24; height: 24; source: s ? s.class_icon : ""; asynchronous: true }
        Text { visible: s && s.favorite; text: "★"; color: "#ffc928"; font.pixelSize: 17; x: parent.width - 11; y: parent.height - 16; style: Text.Outline; styleColor: "#7a5200" }
    }
    component ApBar: Item {
        property int ap: 0
        property bool interlude: false
        width: apRow.implicitWidth + 26; height: 24
        Shape {
            anchors.fill: parent
            ShapePath {
                strokeWidth: 0
                fillGradient: LinearGradient { x1: 0; x2: width; y1: 0; y2: 0
                    GradientStop { position: 0; color: interlude ? "#1f3a66" : "#3a3326" } GradientStop { position: 1; color: interlude ? "#34588e" : "#5b5140" } }
                startX: 0; startY: 0
                PathLine { x: width; y: 0 } PathLine { x: width - 10; y: height } PathLine { x: 0; y: height } PathLine { x: 0; y: 0 }
            }
        }
        Row { id: apRow; x: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 5
            Text { text: "AP"; color: "#ffffffd9"; font.family: sans; font.pixelSize: 11; anchors.baseline: apNum.baseline }
            Text { id: apNum; text: ap; color: "white"; font.family: serif; font.italic: true; font.bold: true; font.pixelSize: 17 } }
    }
    component QuestPlate: Rectangle {
        id: qp
        property var q
        property bool locked: false
        property bool sel: !locked && !!selected[q.quest_id]
        readonly property bool interlude: q.kind === "interlude"
        height: 88; radius: 6; border.color: interlude ? "#eef7ff" : "#fff6dc"; border.width: 2
        opacity: locked ? 0.8 : 1
        gradient: Gradient { orientation: Gradient.Horizontal
            GradientStop { position: 0; color: locked ? "#eef1f5" : interlude ? "#f2f9ff" : "#fff1c7" }
            GradientStop { position: 0.7; color: locked ? "#cfd6e0" : interlude ? "#a9d4f8" : "#d9b467" }
            GradientStop { position: 1; color: locked ? "#b9c2cf" : interlude ? "#6aa9e6" : "#b8893a" } }
        Rectangle { anchors.fill: parent; anchors.margins: qp.sel ? -3 : -1; radius: 8; color: "transparent"; z: -1
                    border.color: qp.sel ? "#2a8be0" : interlude ? "#3f7fc6" : "#b8893a"; border.width: qp.sel ? 3 : 1 }
        Face { s: q.servant; dim: locked; x: 10; anchors.verticalCenter: parent.verticalCenter }
        Column {
            x: 84; width: parent.width - 96; anchors.verticalCenter: parent.verticalCenter; spacing: 1
            Text { text: questTitle(q); color: ink; font.family: sans; font.weight: Font.Black; font.pixelSize: 15; width: parent.width; elide: Text.ElideRight }
            Text { text: interlude ? "INTERLUDE" : "STRENGTHEN QUEST"; color: "#9910213f"; font.family: sans; font.pixelSize: 9; font.letterSpacing: 4 }
            Row { visible: !locked; spacing: 8; topPadding: 2
                ApBar { ap: q.ap || 0; interlude: qp.interlude }
                Text { text: q.phases + " part" + (q.phases > 1 ? "s" : ""); color: "#b310213f"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter } }
            Rectangle { visible: locked; radius: 3; color: "#cc783c14"; width: condText.implicitWidth + 16; height: 20
                Text { id: condText; anchors.centerIn: parent; color: "white"; font.bold: true; font.pixelSize: 12
                       text: locked ? "Needs " + q.missing.map(cond).join(", ") : "" } }
            Text { text: q.name; color: "#a610213f"; font.pixelSize: 11; width: parent.width; elide: Text.ElideRight }
        }
        Rectangle { visible: qp.sel; width: 22; height: 22; radius: 11; color: "#2a8be0"; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
                    Text { anchors.centerIn: parent; text: "✓"; color: "white"; font.bold: true } }
        MouseArea { anchors.fill: parent; enabled: !locked; cursorShape: Qt.PointingHandCursor; onClicked: toggle(q) }
    }

    // ---------- header: band + tab strip ----------
    header: Column {
        Rectangle {
            width: win.width; height: 64
            gradient: Gradient { GradientStop { position: 0; color: "#f278bef5" } GradientStop { position: 1; color: "#d9a0d4fa" } }
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 14
                Rectangle {  // the game's white back button, here: open the live viewer
                    width: backRow.implicitWidth + 30; height: 40; radius: 6; border.color: "#2b3f63"; border.width: 2
                    gradient: Gradient { GradientStop { position: 0; color: "white" } GradientStop { position: 1; color: "#e3e8ee" } }
                    Row { id: backRow; anchors.centerIn: parent; spacing: 12
                        Rectangle { width: 13; height: 13; rotation: 45; color: "#2b3f63"; border.color: "white"; border.width: 2; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Live"; color: ink; font.family: sans; font.weight: Font.Black; font.pixelSize: 16 } }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(apiBase + "/") }
                }
                Row { spacing: 6
                    Text { text: "Lv."; color: ink2; font.family: sans; font.bold: true; anchors.baseline: lvNum.baseline }
                    Text { id: lvNum; text: board ? board.resources.level : ""; color: ink; font.family: serif; font.italic: true; font.bold: true; font.pixelSize: 26 }
                    Text { text: board ? ("AP " + board.resources.ap_max + " · Cost " + board.resources.cost_max) : ""; color: ink2; font.family: sans; font.bold: true; anchors.baseline: lvNum.baseline } }
                Repeater {
                    model: board ? [["gold", board.resources.apples.gold], ["silver", board.resources.apples.silver],
                                    ["bronze", board.resources.apples.bronze], ["saint_quartz", board.resources.saint_quartz],
                                    ["qp", (board.resources.qp / 1e9).toFixed(2) + "B"]] : []
                    Rectangle {
                        radius: 13; height: 26; width: pillRow.implicitWidth + 14; color: "#c710213f"
                        Row { id: pillRow; anchors.verticalCenter: parent.verticalCenter; x: 2; spacing: 4
                            Image { width: 22; height: 22; source: board.resources.icons[modelData[0]]; asynchronous: true }
                            Text { text: typeof modelData[1] === "number" ? fmt(modelData[1]) : modelData[1]; color: "white"; font.family: sans; font.bold: true; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter } }
                    }
                }
                Text { color: ink2; font.pixelSize: 12; font.family: sans
                       text: board ? ("synced " + Math.round((Date.now() / 1000 - board.synced_at) / 3600) + " h ago") : "" }
                SqButton { light: true; text: queue.syncing ? "Syncing…" : "Sync"; enabled: !queue.runner && !queue.agent && !queue.syncing
                           onClicked: api("POST", "/api/sync", null, function (q) { queue = q; toast.show("syncing: FGO restarts once") }) }
                Item { Layout.fillWidth: true }
                Column {
                    Text { anchors.right: parent.right; text: tabs[tab].title; color: "white"; font.family: serif; font.italic: true; font.weight: Font.Black; font.pixelSize: 30
                           style: Text.Outline; styleColor: "#3c78bf" }
                    Text { anchors.right: parent.right; text: tabs[tab].en; color: "#e6ffffff"; font.family: sans; font.pixelSize: 10; font.letterSpacing: 5 } }
            }
        }
        Rectangle {
            width: win.width; height: 46
            gradient: Gradient { GradientStop { position: 0; color: navy1 } GradientStop { position: 1; color: "#24406f" } }
            Row {
                x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                Repeater {
                    model: tabs
                    Rectangle {
                        height: 32; width: tabLabel.implicitWidth + 32; radius: 4
                        border.color: tab === index ? "white" : "#9fd7ff"
                        gradient: Gradient { GradientStop { position: 0; color: tab === index ? "white" : "#3d9cec" } GradientStop { position: 1; color: tab === index ? "#cfe9ff" : "#1f6fc6" } }
                        Text { id: tabLabel; anchors.centerIn: parent; text: modelData.label; color: tab === index ? ink : "white"; font.family: sans; font.bold: true; font.pixelSize: 13 }
                        Rectangle {
                            visible: tabCount(index) > 0; x: parent.width - width + 6; y: -7; height: 20; width: Math.max(20, cnt.implicitWidth + 10); radius: 10
                            color: "#e8582d"; border.color: "white"; border.width: 2
                            Text { id: cnt; anchors.centerIn: parent; text: tabCount(index); color: "white"; font.pixelSize: 11; font.bold: true } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tab = index }
                    }
                }
            }
        }
    }

    // ---------- pages ----------
    StackLayout {
        anchors.fill: parent; anchors.margins: 16; anchors.bottomMargin: selectedCount ? 66 : 16
        currentIndex: tab

        // Interludes & Rank Up
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column {
                width: parent.width; spacing: 14
                Row { spacing: 6
                    Repeater { model: [["all", "All"], ["fav", "★ Favourites"], ["interlude", "Interludes"], ["strengthening", "Rank Up"]]
                        SqButton { light: filter !== modelData[0]; text: modelData[1]; onClicked: filter = modelData[0] } } }
                Panel {
                    width: parent.width; heading: "Open"; sub: "Available"
                    Text { text: "Click quests to select them, then send the agent."; color: muted; font.pixelSize: 12 }
                    Flow { width: parent.width; spacing: 10
                        Repeater { model: openQuests()
                            QuestPlate { q: modelData
                                readonly property int cols: Math.max(1, Math.floor((parent.width + 10) / 370))
                                width: Math.floor((parent.width - (cols - 1) * 10) / cols) } } }
                }
                Panel {
                    width: parent.width; heading: "Locked"; sub: "Requirements"
                    Repeater { model: lockedGroups()
                        Column { width: parent.width; spacing: 6
                            property bool open: false
                            Text { text: (open ? "▾  " : "▸  ") + "Needs " + modelData.key + "  (" + modelData.quests.length + ")"; color: ink2; font.family: sans; font.bold: true
                                   MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.parent.open = !parent.parent.open } }
                            Flow { width: parent.width; spacing: 10; visible: parent.open
                                Repeater { model: parent.parent.open ? modelData.quests : []
                                    QuestPlate { q: modelData; locked: true
                                        readonly property int cols: Math.max(1, Math.floor((parent.width + 10) / 370))
                                        width: Math.floor((parent.width - (cols - 1) * 10) / cols) } } } } }
                }
            }
        }

        // Ascension & skills
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column {
                width: parent.width; spacing: 14
                Panel {
                    width: parent.width; heading: "Materials short"; sub: "For your plan"
                    Text { text: board ? ("QP needed " + fmt(board.upgrades.qp.need) + " of " + fmt(board.upgrades.qp.have) + " owned.") : ""; color: muted; font.pixelSize: 12 }
                    Flow { width: parent.width; spacing: 8
                        Repeater { model: board ? board.upgrades.missing : []
                            Rectangle {
                                readonly property int cols: Math.max(1, Math.floor((parent.width + 8) / 250))
                                width: Math.floor((parent.width - (cols - 1) * 8) / cols); height: 52; radius: 5; border.color: rim2
                                gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "white" } GradientStop { position: 1; color: "#e2f0fd" } }
                                Image { x: 6; anchors.verticalCenter: parent.verticalCenter; width: 40; height: 40; source: modelData.icon; asynchronous: true }
                                Column { x: 54; width: parent.width - 130; anchors.verticalCenter: parent.verticalCenter
                                    Text { text: modelData.name; color: ink; font.bold: true; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
                                    Row { spacing: 4
                                        Text { text: "-" + fmt(modelData.missing); color: red; font.family: serif; font.italic: true; font.bold: true; font.pixelSize: 16 }
                                        Text { text: fmt(modelData.have) + "/" + fmt(modelData.need); color: muted; font.pixelSize: 11; anchors.baseline: parent.children[0].baseline } } }
                                SqButton { text: "Farm"; anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                           onClicked: farmDialog.ask(modelData.name, modelData.missing) }
                            } } }
                }
                Panel {
                    width: parent.width; heading: "Servants"; sub: "Chaldea plan"
                    Repeater { model: board ? board.upgrades.servants : []
                        Row { width: parent.width; spacing: 12
                            Face { s: modelData }
                            Column { width: parent.width - 72; spacing: 3
                                Row { spacing: 8
                                    Text { text: modelData.name; color: ink; font.family: sans; font.weight: Font.Black; font.pixelSize: 15 }
                                    Rectangle { radius: 3; height: 18; width: readyText.implicitWidth + 14; color: modelData.can_do ? green : "#c0473f"; anchors.verticalCenter: parent.verticalCenter
                                        Text { id: readyText; anchors.centerIn: parent; text: modelData.can_do ? "Ready" : "Short"; color: "white"; font.bold: true; font.pixelSize: 11 } } }
                                Text { color: muted; font.pixelSize: 12
                                       text: "Ascension " + modelData.current.ascension + " → " + modelData.target.ascension
                                             + "   Skills " + modelData.current.skills.join("/") + " → " + modelData.target.skills.join("/")
                                             + "   Appends " + modelData.current.appends.join("/") + " → " + modelData.target.appends.join("/")
                                             + "   QP " + fmt(modelData.qp) }
                                Flow { width: parent.width; spacing: 6
                                    Repeater { model: modelData.materials
                                        Item { width: 46; height: 46
                                            Image { anchors.fill: parent; source: modelData.icon; asynchronous: true }
                                            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; radius: 3; height: 14; width: mt.implicitWidth + 6
                                                        color: modelData.have >= modelData.need ? "#d910213f" : "#e6c83232"
                                                Text { id: mt; anchors.centerIn: parent; text: fmt(modelData.have) + "/" + fmt(modelData.need); color: "white"; font.pixelSize: 9; font.bold: true } } } } }
                            } } }
                }
            }
        }

        // Story
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column { width: parent.width; spacing: 14
                Repeater { model: board ? board.story : []
                    Panel { width: parent.width
                        RowLayout { width: parent.width; spacing: 14
                            Image { source: modelData.banner || ""; Layout.preferredHeight: 56; Layout.preferredWidth: modelData.banner ? 170 : 0; fillMode: Image.PreserveAspectFit; asynchronous: true }
                            Column { Layout.fillWidth: true
                                Text { text: modelData.name; color: ink; font.family: sans; font.weight: Font.Black; font.pixelSize: 15; width: parent.width; elide: Text.ElideRight }
                                Text { color: muted; font.pixelSize: 12
                                       text: modelData.main.length + " main  ·  " + modelData.free.length + " free" + (modelData.free.length ? "  ·  first clears give Saint Quartz" : "") } }
                            GoButton { text: "Send the agent"
                                onClicked: api("POST", "/api/queue", {kind: "story", title: "Clear " + modelData.name, apples: 10,
                                    payload: {war: modelData.war, war_name: modelData.name,
                                              quests: modelData.main.concat(modelData.free).map(function (q) { return {quest_id: q.quest_id, name: q.name} })}},
                                    function () { toast.show("story order added"); loadQueue() }) }
                        } } } }
        }

        // Farming
        ScrollView {
            contentWidth: availableWidth; clip: true
            Panel { width: parent.width; heading: "Farming plans"; sub: "Saved"
                Text { visible: board && board.farms.length === 0; color: muted
                       text: "No plans yet: press Farm on a short material and the agent explores one." }
                Repeater { model: board ? board.farms : []
                    Column { width: parent.width; spacing: 3
                        Row { spacing: 8
                            Text { text: modelData.quest_name; color: ink; font.weight: Font.Black; font.family: sans }
                            Rectangle { radius: 3; height: 18; width: tt.implicitWidth + 14; color: modelData.three_turn ? green : "#c0473f"
                                Text { id: tt; anchors.centerIn: parent; text: modelData.turns + " turns"; color: "white"; font.bold: true; font.pixelSize: 11 } } }
                        Text { color: muted; font.pixelSize: 12; text: "for " + (modelData.target_item || "?") + "  ·  support " + modelData.support + "  ·  MC " + (modelData.mystic_code || "-") }
                        Text { color: muted; font.pixelSize: 12; text: modelData.party.join(" / ") + "   FGA " + modelData.skill_command }
                    } } }
        }

        // Orders
        ScrollView {
            contentWidth: availableWidth; clip: true
            Column { width: parent.width; spacing: 14
                Panel { width: parent.width; heading: "Orders"; sub: "For the agent"
                    Row { spacing: 10
                        GoButton { text: "Run orders"; enabled: !queue.runner && !queue.agent && !queue.syncing && activeOrders() > 0
                                   onClicked: api("POST", "/api/queue/run", null, function (q) { queue = q; toast.show("the agent is on it") }) }
                        SqButton { danger: true; text: "Stop"; enabled: queue.runner; anchors.verticalCenter: parent.verticalCenter
                                   onClicked: api("POST", "/api/queue/stop", null, function (q) { queue = q }) }
                        Text { anchors.verticalCenter: parent.verticalCenter; color: muted; font.pixelSize: 12
                               text: queue.runner ? "the agent is working through the orders" : queue.agent ? "a separate agent run is playing" : queue.syncing ? "syncing your account" : "idle" } }
                    Text { visible: queue.tasks.length === 0; text: "No orders yet."; color: muted }
                    Repeater { model: queue.tasks.slice().reverse()
                        RowLayout { width: parent.width; spacing: 10
                            Rectangle { radius: 10; height: 20; width: stText.implicitWidth + 16
                                color: modelData.status === "running" ? "#2f8fe0" : modelData.status === "done" ? green : modelData.status === "queued" ? "#7d93b5" : "#c0473f"
                                Text { id: stText; anchors.centerIn: parent; text: modelData.status; color: "white"; font.bold: true; font.pixelSize: 11 } }
                            Column { Layout.fillWidth: true
                                Text { text: modelData.title; color: ink; font.bold: true; width: parent.width; elide: Text.ElideRight }
                                Text { color: muted; font.pixelSize: 12
                                       text: modelData.kind + (modelData.apples !== null && modelData.apples !== undefined ? "  ·  ≤" + modelData.apples + " apples" : "")
                                             + (modelData.cost ? "  ·  $" + modelData.cost.toFixed(2) : "") } }
                            SqButton { light: true; text: "✕"; implicitWidth: 34; visible: modelData.status !== "running"
                                       onClicked: api("DELETE", "/api/queue/" + modelData.id, null, function (q) { queue = q }) } } } }
                Panel { width: parent.width; heading: "Custom order"
                    TextArea { id: custom; width: parent.width; height: 70; placeholderText: "Anything else, in plain words: e.g. clear today's daily quests"
                               background: Rectangle { color: "white"; border.color: rim; radius: 4 } }
                    Row { spacing: 8
                        Text { text: "Apple budget"; color: muted; anchors.verticalCenter: parent.verticalCenter }
                        SpinBox { id: customApples; from: 0; to: 200; value: 5 }
                        SqButton { text: "Add"; anchors.verticalCenter: parent.verticalCenter; onClicked: {
                            if (!custom.text.trim()) return
                            api("POST", "/api/queue", {kind: "custom", title: custom.text.trim().slice(0, 80), payload: {text: custom.text.trim()}, apples: customApples.value},
                                function () { custom.text = ""; loadQueue() }) } } } }
            }
        }
    }

    // ---------- selection bar, dialog, toast ----------
    Rectangle {
        visible: selectedCount > 0
        anchors.bottom: parent.bottom; width: parent.width; height: 58
        gradient: Gradient { GradientStop { position: 0; color: "#24406f" } GradientStop { position: 1; color: navy1 } }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            Text { text: selectedCount + " quest" + (selectedCount === 1 ? "" : "s") + " selected"; color: "white"; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "Apple budget"; color: "#bcdcff"; anchors.verticalCenter: parent.verticalCenter }
            SpinBox { id: barApples; from: 0; to: 200; value: 10 }
            SqButton { light: true; text: "Clear"; anchors.verticalCenter: parent.verticalCenter; onClicked: { selected = {}; selectedCount = 0 } }
            GoButton { text: "Send the agent"; onClicked: {
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
        Column { spacing: 10
            Row { spacing: 8; Text { text: "How many"; color: ink; anchors.verticalCenter: parent.verticalCenter } SpinBox { id: farmCount; from: 1; to: 9999; editable: true } }
            Row { spacing: 8; Text { text: "Apple budget"; color: ink; anchors.verticalCenter: parent.verticalCenter } SpinBox { id: farmApples; from: 0; to: 500; value: 20; editable: true } }
            Text { width: 300; wrapMode: Text.Wrap; color: muted; font.pixelSize: 12
                   text: "The agent finds a 3-turn plan with up to 3 exploratory runs, saves it, then FGA farms with it." }
        }
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: api("POST", "/api/queue", {kind: "farm", title: "Farm " + farmCount.value + " " + item, apples: farmApples.value,
                                              payload: {item: item, count: farmCount.value}}, function () { toast.show("farm order added"); loadQueue() })
    }

    Rectangle {
        id: toast
        function show(text) { msg.text = text; visible = true; hide.restart() }
        visible: false; z: 10; radius: 6; color: "white"; border.color: rim
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 16; anchors.bottomMargin: 76
        width: Math.min(msg.implicitWidth + 28, win.width - 32); height: msg.implicitHeight + 20
        Text { id: msg; anchors.centerIn: parent; width: parent.width - 28; color: ink; wrapMode: Text.Wrap }
        Timer { id: hide; interval: 5000; onTriggered: toast.visible = false }
    }
}
