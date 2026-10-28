package com.guardianlab.chat
import org.junit.Assert.*
import org.junit.Test

class VibePlaybackTest {
 @Test fun photoCountsVisibleTimeAndStopsAtTenSeconds(){val c=VibePlayback(10000);c.update(0,true);assertEquals(.5f,c.update(5000,true));assertFalse(c.finished);assertEquals(1f,c.update(15000,true));assertTrue(c.finished)}
 @Test fun shieldingBackgroundAndReplyIntervalsDoNotConsumeVideo(){val c=VibePlayback(20000);c.update(0,true);c.update(3000,true);c.update(4000,false);c.update(50000,false);c.update(51000,true);assertEquals(3000L,c.elapsedMs);c.update(68000,true);assertTrue(c.finished)}
 @Test fun dragUsesShortDistanceOrFlickAndRejectsAnAccidentalMove(){assertFalse(VibeDismiss.shouldClose(20f,20,800f));assertFalse(VibeDismiss.shouldClose(60f,800,800f));assertTrue(VibeDismiss.shouldClose(150f,800,800f));assertTrue(VibeDismiss.shouldClose(60f,80,800f))}
}
