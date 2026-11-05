plugins {
    id("com.android.application") version "8.7.3"
    id("org.jetbrains.kotlin.android") version "2.0.21"
}
// Keep the existing Python identity authoritative; no separate companion release version.
val flochatVersion = Regex("""(?m)^__version__ = "([^"]+)"$""")
    .find(file("../../src/flochat/__init__.py").readText())?.groupValues?.get(1)
    ?: error("FloChat source version is missing")
android {
    namespace = "ai.flochat.companion"
    compileSdk = 35
    defaultConfig {
        applicationId = "ai.flochat.companion"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = flochatVersion
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
