#!/usr/bin/env bash
# Build the Kotlin bridge that runs FGA's battle modules over adb.
set -euo pipefail
cd "$(dirname "$0")/.."

git submodule update --init vendor/FGA

# Gradle itself needs a JDK it supports; the bridge compiles with a JDK 21 toolchain.
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-amazon-corretto}"
cd bridge
./gradlew installDist --console=plain
echo "built: bridge/build/install/fga-bridge/bin/fga-bridge"
