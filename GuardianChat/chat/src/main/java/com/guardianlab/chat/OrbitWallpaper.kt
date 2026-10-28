package com.guardianlab.chat

import android.graphics.*
import android.graphics.drawable.Drawable

/** Shared original artwork, centre-cropped without stretching for each appearance. */
internal class OrbitWallpaper(private val dark:Bitmap,private val light:Bitmap,private val tint:(Boolean)->IntArray?={null},private val soften:Boolean=false,private val bright:()->Boolean):Drawable(){
 private val paint=Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
 private val tintPaint=Paint(Paint.ANTI_ALIAS_FLAG)
 override fun draw(canvas:Canvas){
  val isBright=bright();val colors=tint(isBright)
  val layer=if(colors!=null)canvas.saveLayer(RectF(bounds),null) else canvas.save()
  canvas.drawColor(OrbitPalette.color(OrbitPalette.BG,OrbitPalette.LIGHT_BG,isBright))
  if(bounds.isEmpty){canvas.restoreToCount(layer);return}
  val bitmap=if(isBright)light else dark
  val scale=maxOf(bounds.width().toFloat()/bitmap.width,bounds.height().toFloat()/bitmap.height)
  val width=bitmap.width*scale;val height=bitmap.height*scale
  val left=bounds.exactCenterX()-width/2;val top=bounds.exactCenterY()-height/2
  val save=canvas.save();canvas.clipRect(bounds)
  canvas.drawBitmap(bitmap,null,RectF(left,top,left+width,top+height),paint)
  if(soften){
   tintPaint.blendMode=BlendMode.SRC_OVER
   val veil=if(isBright)intArrayOf(Color.argb(128,216,116,248),Color.argb(128,29,111,255),Color.argb(128,1,211,237)) else intArrayOf(Color.argb(89,99,0,198),Color.argb(89,0,31,89),Color.argb(89,0,0,13))
   tintPaint.shader=LinearGradient(0f,bounds.top.toFloat(),0f,bounds.bottom.toFloat(),veil,floatArrayOf(0f,.56f,1f),Shader.TileMode.CLAMP)
   canvas.drawRect(bounds,tintPaint)
  }
  colors?.let {
   tintPaint.shader=LinearGradient(0f,bounds.top.toFloat(),0f,bounds.bottom.toFloat(),colors,floatArrayOf(0f,.56f,1f),Shader.TileMode.CLAMP)
   tintPaint.blendMode=BlendMode.COLOR
   canvas.drawRect(bounds,tintPaint)
  }
  canvas.restoreToCount(save)
  canvas.restoreToCount(layer)
 }

 override fun setAlpha(alpha:Int){paint.alpha=alpha;invalidateSelf()}
 override fun setColorFilter(filter:ColorFilter?){paint.colorFilter=filter;invalidateSelf()}
 @Deprecated("Required by Drawable") override fun getOpacity()=PixelFormat.OPAQUE
}
