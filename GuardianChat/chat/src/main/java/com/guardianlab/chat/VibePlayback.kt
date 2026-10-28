package com.guardianlab.chat

/** Counts only intervals whose endpoints both show authorized, visible content. */
internal class VibePlayback(val limitMs:Long) {
 private var previous:Long?=null
 private var visibleBefore=false
 var elapsedMs=0L;private set
 fun update(now:Long,visible:Boolean):Float {
  previous?.let {if(visible&&visibleBefore)elapsedMs=(elapsedMs+(now-it).coerceAtLeast(0)).coerceAtMost(limitMs)}
  previous=now;visibleBefore=visible
  return elapsedMs.toFloat()/limitMs
 }
 val finished get()=elapsedMs>=limitMs
}
internal object VibeDismiss {
 fun shouldClose(distance:Float,elapsedMs:Long,height:Float):Boolean =
  distance>=minOf(140f,height*.18f)||distance>45f&&distance/elapsedMs.coerceAtLeast(1)>.55f
}
