package com.guardianlab.chat

import java.net.URI

/** A fixed static-file allowlist. Account, message, media and competition APIs never match. */
internal class ComparisonAssetPolicy(base: String) {
 private val origin = URI(base)
 private val files = setOf("media-editor.js", "media-editor.css", "orbit-switcher.js", "market-types.js", "market-chat.js", "module-navigation.js", "vibe-motion.js", "vibe-share.js", "vibe.html", "vibe.js", "vibe.css", "activity-ui.js", "navigation.css", "navigation-icons/vibe-icon.svg", "navigation-icons/chat-icon.svg", "navigation-icons/call-icon.svg", "navigation-icons/profile-icon.svg", "navigation-icons/orbit-market-icon.svg", "private-results.js", "evidence-camera.js", "camera-sources.js", "market.html", "market.js", "market.css", "gaming.html", "gaming.js", "gaming.css", "orbit-theme.css",
  "studio.js", "result-room.js", "orbit-icon.png", "roboto-0.ttf", "roboto-1.ttf", "orbit-theme.js", "sponsored-ui.js", "phase-b.js", "scheduling.js", "social.js", "social-spaces.js",
  "live-room-ui.js", "stream-relay-ui.js", "invitations.js", "profile-tabs.css", "form-panels.js", "form-panels.css",
  "branding/orbit-wallpaper.png", "branding/orbit-wallpaper-v2.png",
  "branding/settings-dark.png", "branding/settings-light.png", "branding/orbit-icon-light.png", "branding/orbit-icon-plain.png")
 private fun port(uri: URI) = if (uri.port == -1) 443 else uri.port
 fun asset(method: String, address: String): String? = try {
  val uri = URI(address)
  val filename = uri.rawPath.removePrefix("/")
  if (method != "GET" || origin.scheme != "https" || uri.scheme != "https" ||
   uri.host?.equals(origin.host, ignoreCase = true) != true || port(uri) != port(origin) ||
   uri.rawUserInfo != null || uri.rawFragment != null || uri.rawPath != "/$filename" || filename !in files) null
  else "comparison-web/$filename"
 } catch (_: Exception) { null }
}
