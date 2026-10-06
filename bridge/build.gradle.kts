// Runs FGA's own automation modules (libautomata + scripts) on the desktop JVM over adb.
// FGA's sources are compiled straight from the vendor/FGA submodule, so its logic is used as-is.
plugins {
    kotlin("jvm") version "2.4.10"
    kotlin("plugin.serialization") version "2.4.10"
    id("com.google.devtools.ksp") version "2.3.11"
    application
}

val fga = rootDir.resolve("../vendor/FGA")

kotlin {
    jvmToolchain(21)
    sourceSets.main {
        kotlin.srcDir(fga.resolve("libautomata/src/main/java"))
        kotlin.srcDir(fga.resolve("scripts/src/main/java"))
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.11.0")
    implementation("com.google.dagger:dagger:2.60.1")
    implementation("com.google.dagger:hilt-core:2.60.1")
    ksp("com.google.dagger:dagger-compiler:2.60.1")
    implementation("org.openpnp:opencv:4.9.0-0")
}

application {
    mainClass.set("fgo.bridge.MainKt")
    applicationDefaultJvmArgs = listOf("-Dfga.assets=${fga.resolve("app/src/main/assets").absolutePath}")
}
