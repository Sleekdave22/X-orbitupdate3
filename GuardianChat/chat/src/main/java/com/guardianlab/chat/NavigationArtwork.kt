package com.guardianlab.chat

import android.content.Context
import android.graphics.Picture
import android.graphics.drawable.PictureDrawable
import android.view.View
import android.widget.ImageView
import com.caverock.androidsvg.SVG

/** Render the supplied SVGs once, without creating a browser renderer per icon. */
internal class NavigationArtwork(private val context:Context) {
 private val pictures=mutableMapOf<String,Picture>()
 fun view(name:String)=ImageView(context).apply {
  require(name in setOf("vibe-icon","chat-icon","call-icon","profile-icon","orbit-market-icon"))
  val picture=pictures.getOrPut(name){SVG.getFromAsset(context.assets,"navigation-icons/$name.svg").renderToPicture()}
  setImageDrawable(PictureDrawable(picture))
  setLayerType(View.LAYER_TYPE_SOFTWARE,null)
  scaleType=ImageView.ScaleType.FIT_CENTER
  isFocusable=false
  importantForAccessibility=View.IMPORTANT_FOR_ACCESSIBILITY_NO
 }
}
