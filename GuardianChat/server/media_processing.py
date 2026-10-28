"""Destination-specific edits; independent of result-evidence verification."""
import base64, io, math, os, tempfile
from pathlib import Path
from fractions import Fraction
from PIL import Image, ImageOps

MAX_BYTES=20*1024*1024
MAX_PIXELS=3840*2160
VIDEO_SECONDS=60
PLAZA_VIDEO_SECONDS=int(os.environ.get('ORBIT_PLAZA_VIDEO_SECONDS','60'))
if not 1<=PLAZA_VIDEO_SECONDS<=600:raise ValueError('ORBIT_PLAZA_VIDEO_SECONDS must be 1–600; the approved default is 60')

def probe(raw,mime):
 if not raw or len(raw)>MAX_BYTES:raise ValueError('Choose a file up to 20 MB')
 if mime.startswith('image/'):
  with Image.open(io.BytesIO(raw)) as im:
   if im.format not in ('JPEG','PNG','WEBP') or im.width*im.height>24_000_000 or getattr(im,'n_frames',1)!=1:raise ValueError('Use a still JPG, PNG or WebP photo up to 24 megapixels')
   width,height=im.size
   if im.getexif().get(274) in (5,6,7,8):width,height=height,width
   fmt=im.format
  with Image.open(io.BytesIO(raw)) as checked:checked.verify()
  return {'mime':'image/'+('jpeg' if fmt=='JPEG' else fmt.lower()),'width':width,'height':height,'duration_ms':0}
 if not mime.startswith('video/'):raise ValueError('Choose a photo or video')
 import av
 with av.open(io.BytesIO(raw)) as c:
  if len(c.streams.video)!=1 or len(c.streams.audio)>1:raise ValueError('Choose a video with one video track and at most one audio track')
  s=c.streams.video[0]
  if s.width*s.height>MAX_PIXELS or not s.width or not s.height:raise ValueError('Use a video up to 4K')
  seconds=float(s.duration*s.time_base) if s.duration is not None else (float(c.duration)/av.time_base if c.duration else 0)
  frames=c.decode(s);first=next(frames,None)
  if first is None:raise ValueError('This video has no displayable frame')
  if not math.isfinite(seconds) or seconds<=0:
   origin=float((s.start_time or 0)*s.time_base);last=float(first.time or 0)-origin;count=1
   for frame in frames:
    count+=1
    if count>120000 or frame.time is None:raise ValueError('This video is too complex for the current editor')
    at=float(frame.time)-origin
    if at<last:raise ValueError('This video has invalid timing')
    last=at
   seconds=last+1/float(s.average_rate or s.guessed_rate or 30)
   if not math.isfinite(seconds) or seconds<=0:raise ValueError('This video has no reliable duration')
  rotation=first.rotation;width,height=s.width,s.height
  if abs(rotation)%180==90:width,height=height,width
  return {'mime':'video/mp4' if 'mov' in c.format.name or 'mp4' in c.format.name else 'video/webm','width':width,'height':height,'duration_ms':round(seconds*1000),'audio':bool(c.streams.audio),'source_rotation':rotation}

def recipe(info,b,destination):
 if destination not in ('vibe','plaza'):raise ValueError('Choose Vibe or Plaza')
 rotation=b.get('rotation',0);crop=b.get('crop','original');fit=b.get('fit','fit')
 if type(rotation)!=int or rotation not in (0,90,180,270) or crop not in ('original','portrait') or fit not in ('fit','fill'):raise ValueError('Choose a valid rotation, crop and fit')
 rect=b.get('crop_rect')
 if rect is not None:
  if not isinstance(rect,dict) or set(rect)!=set(('x','y','w','h')) or any(type(v) not in (int,float) or not math.isfinite(v) for v in rect.values()):raise ValueError('Choose a valid crop frame')
  if rect['x']<0 or rect['y']<0 or rect['w']<=0 or rect['h']<=0 or rect['x']+rect['w']>1.000001 or rect['y']+rect['h']>1.000001:raise ValueError('Keep the crop inside the picture')
 duration=info['duration_ms'];start=b.get('start_ms',0);end=b.get('end_ms',duration)
 if type(start)!=int or type(end)!=int or start<0 or end<start or end>duration or duration and end-start<100:raise ValueError('Choose valid start and end times')
 split=b.get('split',False)
 if type(split)!=bool or split and destination!='vibe':raise ValueError('Automatic splitting is only available for Vibes')
 maximum=VIDEO_SECONDS if destination=='vibe' else PLAZA_VIDEO_SECONDS
 if duration and end-start>maximum*1000 and not split:raise ValueError('Trim this video to '+str(maximum)+' seconds'+(' or split it into Vibes' if destination=='vibe' else ''))
 ranges=[]
 if duration:
  at=start
  while at<end:ranges.append([at,min(at+VIDEO_SECONDS*1000,end) if split else end]);at=ranges[-1][1]
 else:ranges=[[0,0]]
 if len(ranges)>30:raise ValueError('Choose a shorter section: one edit can create up to 30 Vibes')
 return {'rotation':rotation,'source_rotation':info.get('source_rotation',0),'crop':crop,'fit':fit,'crop_rect':rect,'ranges':ranges,'destination':destination}

def validate_vibe_video(raw):
 import av
 info=probe(raw,'video/mp4')
 if info['duration_ms']>60000:raise ValueError('A video Vibe can be up to 60 seconds; split it in the editor')
 with av.open(io.BytesIO(raw)) as source:
  stream=source.streams.video[0];stream.codec_context.thread_count=2;origin=float((stream.start_time or 0)*stream.time_base);last=-1;count=0
  for frame in source.decode(stream):
   count+=1
   if count>7200 or frame.time is None:raise ValueError('Unsupported video timing')
   at=float(frame.time)-origin
   if at<last or at>=60.001:raise ValueError('A video Vibe must use normal timestamps and stay within 60 seconds')
   last=at
  if not count:raise ValueError('This video contains no decodable frames')
 return info

def transform(im,r,video=False):
 im=ImageOps.exif_transpose(im)
 if 'A' in im.getbands() or 'transparency' in im.info:
  image=im.convert('RGBA');background=Image.new('RGBA',im.size,'#090b20');im=Image.alpha_composite(background,image).convert('RGB')
 else:im=im.convert('RGB')
 if r['rotation']:im=im.rotate(-r['rotation'],expand=True)
 if r.get('crop_rect'):
  rect=r['crop_rect'];w,h=im.size;box=(round(rect['x']*w),round(rect['y']*h),round((rect['x']+rect['w'])*w),round((rect['y']+rect['h'])*h))
  if box[2]<=box[0] or box[3]<=box[1]:raise ValueError('Choose a larger crop area')
  im=im.crop(box)
 if r['crop']=='portrait':
  size=(720,1280) if video else (900,1600)
  if r['fit']=='fill':im=ImageOps.fit(im,size,method=Image.Resampling.LANCZOS)
  else:im=ImageOps.pad(im,size,method=Image.Resampling.LANCZOS,color='#090b20')
 else:
  im.thumbnail((1280,1280) if video else (1600,1600),Image.Resampling.LANCZOS)
  if video:im=im.resize((max(2,im.width//2*2),max(2,im.height//2*2)))
 return im

def photo(raw,r):
 with Image.open(io.BytesIO(raw)) as im:edited=transform(im,r)
 out=io.BytesIO();edited.save(out,'JPEG',quality=88);thumb=edited.copy();thumb.thumbnail((240,240));poster=io.BytesIO();thumb.save(poster,'JPEG',quality=75)
 return {'data':base64.b64encode(out.getvalue()).decode(),'mime':'image/jpeg','poster':base64.b64encode(poster.getvalue()).decode(),'duration_ms':0}

def clip(raw,r,start_ms,end_ms):
 import av,numpy as np
 with tempfile.TemporaryDirectory(prefix='orbit-media-') as scratch:
  output=Path(scratch)/'edited.mp4'
  return _clip_to_file(av,np,raw,r,start_ms,end_ms,output)

def _clip_to_file(av,np,raw,r,start_ms,end_ms,output):
 start=start_ms/1000;end=end_ms/1000;poster=None;frames=0
 with av.open(io.BytesIO(raw)) as source, av.open(str(output),'w',format='mp4',options={'movflags':'faststart'}) as target:
  stream=source.streams.video[0];origin=float((stream.start_time or 0)*stream.time_base);stream.codec_context.thread_count=2
  source_rate=float(stream.average_rate or 30);fps=min(30,max(1,round(source_rate)))
  video=target.add_stream('libx264',rate=fps);video.pix_fmt='yuv420p';video.options={'preset':'veryfast','crf':'25'};video.time_base=Fraction(1,90000);video.codec_context.time_base=Fraction(1,90000);video.codec_context.thread_count=2;video.codec_context.max_b_frames=0
  size=transform(Image.new('RGB',(stream.width,stream.height)).rotate(r.get('source_rotation',0),expand=True),r,True).size;video.width,video.height=size
  audio=target.add_stream('aac',rate=48000) if source.streams.audio else None
  if audio:audio.layout='stereo';audio.bit_rate=96000
  resampler=av.AudioResampler(format='fltp',layout='stereo',rate=48000) if audio else None
  previous=-1;last_audio=-1;scanned=0;before_start=None
  def mux_video(packets):
   for packet in packets:
    if packet.pts is not None:
     remaining=round((end-start)/packet.time_base)-packet.pts
     if remaining<=0:continue
     packet.duration=min(packet.duration or max(1,round(1/fps/packet.time_base)),remaining)
    target.mux(packet)
  def emit_video(frame,timestamp):
   nonlocal previous,frames,poster
   pts=max(0,round((timestamp-start)*90000))
   if pts<=previous or source_rate>fps+.01 and previous>=0 and pts-previous<90000/fps-1:return
   image=transform(frame.to_image().rotate(r.get('source_rotation',0),expand=True),r,True)
   if not frames:
    thumb=image.copy();thumb.thumbnail((240,240));p=io.BytesIO();thumb.save(p,'JPEG',quality=75);poster=base64.b64encode(p.getvalue()).decode()
   edited=av.VideoFrame.from_image(image);edited.pts=pts;edited.time_base=Fraction(1,90000)
   mux_video(video.encode(edited));previous=pts;frames+=1
  def emit_audio(sample,fallback):
   nonlocal last_audio
   t=float(sample.time)-origin if sample.time is not None else fallback
   lo=max(0,math.ceil((start-t)*48000));hi=min(sample.samples,math.ceil((end-t)*48000))
   if hi<=lo:return
   samples=np.ascontiguousarray(sample.to_ndarray()[:,lo:hi]);edited=av.AudioFrame.from_ndarray(samples,format='fltp',layout='stereo');edited.sample_rate=48000;edited.time_base=Fraction(1,48000);edited.pts=max(0,round((t-start)*48000)+lo)
   if edited.pts<last_audio:return
   last_audio=edited.pts+edited.samples
   for encoded in audio.encode(edited):target.mux(encoded)
  for packet in source.demux(*list(source.streams.video),*list(source.streams.audio)):
   for frame in packet.decode():
    scanned+=1
    if scanned>120000:raise ValueError('This video is too complex for the current editor; choose a smaller source')
    if frame.time is None:raise ValueError('This video has invalid timestamps')
    timestamp=float(frame.time)-origin
    if isinstance(frame,av.VideoFrame):
     if timestamp<start-0.000001:before_start=frame;continue
     if not frames and before_start is not None and timestamp>start+.000001:emit_video(before_start,start)
     if timestamp<end-0.000001:emit_video(frame,timestamp)
    elif audio:
     for sample in resampler.resample(frame):emit_audio(sample,timestamp)
  if not frames and before_start is not None:emit_video(before_start,start)
  if not frames:raise ValueError('No video frames in the chosen section')
  mux_video(video.encode())
  if audio:
   for sample in resampler.resample(None):emit_audio(sample,end)
   for encoded in audio.encode():target.mux(encoded)
 data=output.read_bytes()
 if len(data)>MAX_BYTES:raise ValueError('Edited video exceeds 20 MB; choose a shorter section')
 return {'data':base64.b64encode(data).decode(),'mime':'video/mp4','poster':poster,'duration_ms':end_ms-start_ms}

def process(raw,mime,b,destination):
 info=probe(raw,mime);r=recipe(info,b,destination);parts=[];total=0
 for start,end in r['ranges']:
  part=clip(raw,r,start,end) if info['duration_ms'] else photo(raw,r)
  total+=len(part['data'])
  if total>56*1024*1024:raise ValueError('This edit produces too much media; trim the source or publish fewer segments')
  parts.append(part|{'start_ms':start,'end_ms':end,'position':len(parts)})
 return {'parts':parts,'recipe':r}
