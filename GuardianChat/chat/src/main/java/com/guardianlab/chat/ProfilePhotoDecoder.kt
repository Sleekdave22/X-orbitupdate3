package com.guardianlab.chat

import android.graphics.Bitmap
import android.graphics.ImageDecoder
import java.nio.ByteBuffer

/** BitmapFactory ignores EXIF on existing avatars; ImageDecoder matches browser orientation. */
internal object ProfilePhotoDecoder {
 fun decode(bytes:ByteArray,maxEdge:Int=1024):Bitmap=ImageDecoder.decodeBitmap(ImageDecoder.createSource(ByteBuffer.wrap(bytes))){decoder,info,_->
  decoder.allocator=ImageDecoder.ALLOCATOR_SOFTWARE
  val edge=maxOf(info.size.width,info.size.height)
  if(edge>maxEdge)decoder.setTargetSize(maxOf(1,info.size.width*maxEdge/edge),maxOf(1,info.size.height*maxEdge/edge))
 }
}
