plugins { alias(libs.plugins.android.application) }
android {
 namespace = "com.guardianlab.chat"
 compileSdk { version = release(36) { minorApiLevel = 1 } }
 defaultConfig { applicationId = if(providers.gradleProperty("orbitComparison").orNull == "true") "com.guardianlab.chat.compare" else "com.guardianlab.chat"; minSdk = 29; targetSdk = 36; versionCode = 39; versionName = "0.39-vibe-polish"; buildConfigField("boolean", "COMPARISON_INTERFACE", "true"); buildConfigField("boolean", "BUNDLED_INTERFACE", (providers.gradleProperty("orbitComparison").orNull == "true").toString()); ndk { abiFilters += "arm64-v8a" } }
 buildFeatures { buildConfig = true }
 sourceSets.getByName("main").assets.srcDir(layout.buildDirectory.dir("generated/comparison-assets").get().asFile)
 compileOptions { sourceCompatibility = JavaVersion.VERSION_11; targetCompatibility = JavaVersion.VERSION_11 }
}
dependencies {
 implementation("io.github.webrtc-sdk:android:144.7559.01")
 implementation("com.google.firebase:firebase-messaging:25.1.3")
 implementation("com.caverock:androidsvg-aar:1.4")
 implementation(project(":guardianlab"))
 implementation(project(":guardianlab-ui"))
 implementation("androidx.activity:activity-ktx:1.8.0")
 implementation("androidx.camera:camera-camera2:1.6.1")
 implementation("androidx.camera:camera-lifecycle:1.6.1")
 implementation("com.google.mlkit:face-detection:16.1.7")
 testImplementation("junit:junit:4.13.2")
}

// Package the fork's own interface; API calls still use the configured HTTPS server.
val comparisonAssets = tasks.register<Sync>("packageComparisonInterface") {
 from(rootProject.file("server")) {
  include("media-editor.js", "media-editor.css", "orbit-switcher.js", "market-types.js", "market-chat.js", "module-navigation.js", "vibe-motion.js", "vibe-cache.js", "vibe-share.js", "vibe.html", "vibe.js", "vibe.css", "activity-ui.js", "navigation.css", "navigation-icons/*.svg", "private-results.js", "evidence-camera.js", "camera-sources.js", "market.html", "market.js", "market.css", "gaming.html", "gaming.js", "gaming.css", "orbit-theme.css", "orbit-theme.js", "personalization.js", "personalization.json",
   "studio.js", "result-room.js", "orbit-icon.png", "roboto-0.ttf", "roboto-1.ttf",
   "branding/orbit-wallpaper.png", "branding/orbit-wallpaper-v2.png",
   "branding/settings-dark.png", "branding/settings-light.png", "branding/orbit-icon-light.png", "branding/orbit-icon-plain.png",
   "sponsored-ui.js", "phase-b.js", "scheduling.js", "social.js", "social-spaces.js",
   "live-room-ui.js", "stream-relay-ui.js", "invitations.js", "profile-tabs.css", "form-panels.js", "form-panels.css")
 }
 into(layout.buildDirectory.dir("generated/comparison-assets/comparison-web"))
}
tasks.named("preBuild").configure { dependsOn(comparisonAssets) }
