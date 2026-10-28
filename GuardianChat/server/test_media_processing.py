import base64,io,unittest
from fractions import Fraction
from PIL import Image
import av,numpy as np
import media_processing as m

def movie(seconds=3,audio=False,fps=2,pattern=False,rate=48000):
 out=io.BytesIO()
 with av.open(out,'w',format='mp4') as c:
  v=c.add_stream('libx264',rate=fps);v.width=160;v.height=90;v.pix_fmt='yuv420p'
  a=c.add_stream('aac',rate=rate) if audio else None
  if a:a.layout='stereo'
  for n in range(seconds*fps):
   image=Image.new('RGB',(160,90),((n%2)*200,n%255,80))
   if pattern:image.paste('red',(0,0,80,90));image.paste('blue',(80,0,160,90))
   f=av.VideoFrame.from_image(image);f.pts=n;f.time_base=Fraction(1,fps)
   for p in v.encode(f):c.mux(p)
   if a:
    count=rate//fps;t=(np.arange(count)+n*count)/rate;wave=(np.sin(t*440*2*np.pi)*.2).astype(np.float32);samples=np.stack([wave,wave]);f=av.AudioFrame.from_ndarray(samples,format='fltp',layout='stereo');f.sample_rate=rate;f.pts=n*count;f.time_base=Fraction(1,rate)
    for p in a.encode(f):c.mux(p)
  for p in v.encode():c.mux(p)
  if a:
   for p in a.encode():c.mux(p)
 return out.getvalue()

class MediaProcessingTest(unittest.TestCase):
 def test_exact_contiguous_split_boundaries(self):
  for seconds,expected in [(59,[59000]),(60,[60000]),(61,[60000,1000]),(120,[60000,60000]),(155,[60000,60000,35000])]:
   info={'duration_ms':seconds*1000};r=m.recipe(info,{'split':True},'vibe');self.assertEqual([b-a for a,b in r['ranges']],expected)
   self.assertEqual(r['ranges'][0][0],0);self.assertEqual(r['ranges'][-1][1],seconds*1000)
   for left,right in zip(r['ranges'],r['ranges'][1:]):self.assertEqual(left[1],right[0])
 def test_manual_trim_plaza_limit_and_bad_edits(self):
  self.assertEqual(m.recipe({'duration_ms':155000},{'start_ms':10000,'end_ms':65000},'vibe')['ranges'],[[10000,65000]])
  for destination,b in [('plaza',{'split':True}),('plaza',{}),('vibe',{}),('vibe',{'rotation':45}),('vibe',{'start_ms':True}),('vibe',{'end_ms':155001})]:
   with self.assertRaises(ValueError):m.recipe({'duration_ms':155000},b,destination)
 def test_photo_rotation_portrait_and_original_unchanged(self):
  out=io.BytesIO();Image.new('RGB',(100,60),'red').save(out,'PNG');raw=out.getvalue()
  result=m.process(raw,'image/png',{'rotation':90,'crop':'portrait','fit':'fit'},'vibe')['parts'][0]
  with Image.open(io.BytesIO(base64.b64decode(result['data']))) as im:self.assertEqual(im.size,(900,1600))
  self.assertEqual(out.getvalue(),raw);self.assertEqual(result['mime'],'image/jpeg')
 def test_real_video_crop_audio_and_timestamps(self):
  raw=movie(3,True);info=m.probe(raw,'video/mp4');self.assertEqual(info['duration_ms'],3000)
  result=m.process(raw,'video/mp4',{'start_ms':500,'end_ms':2500,'rotation':90,'crop':'portrait','fit':'fill'},'vibe')['parts'][0]
  self.assertEqual(result['duration_ms'],2000)
  with av.open(io.BytesIO(base64.b64decode(result['data']))) as c:
   self.assertEqual((c.streams.video[0].width,c.streams.video[0].height),(720,1280));self.assertEqual(len(c.streams.audio),1)
   video_end=float(c.streams.video[0].duration*c.streams.video[0].time_base);audio_end=float(c.streams.audio[0].duration*c.streams.audio[0].time_base)
   self.assertLess(abs(video_end-2),.1);self.assertLess(abs(audio_end-video_end),.1)
 def test_real_155_second_export(self):
  raw=movie(155);result=m.process(raw,'video/mp4',{'split':True},'vibe')['parts']
  self.assertEqual([p['duration_ms'] for p in result],[60000,60000,35000])
  with av.open(io.BytesIO(raw)) as c:original=[frame.to_image().getpixel((80,45)) for frame in c.decode(video=0)]
  for part in result:
   info=m.probe(base64.b64decode(part['data']),part['mime']);self.assertLessEqual(info['duration_ms'],60000);self.assertEqual(info['duration_ms'],part['duration_ms'])
   with av.open(io.BytesIO(base64.b64decode(part['data']))) as c:frames=[frame.to_image().getpixel((80,45)) for frame in c.decode(video=0)]
   self.assertEqual(len(frames),part['duration_ms']//500)
   for actual,wanted in zip(frames[0],original[part['start_ms']//500]):self.assertLess(abs(actual-wanted),8)
   for actual,wanted in zip(frames[-1],original[part['end_ms']//500-1]):self.assertLess(abs(actual-wanted),8)
 def test_direct_vibe_video_under_exactly_and_over_sixty(self):
  for seconds in (1,60):self.assertEqual(m.validate_vibe_video(movie(seconds))['duration_ms'],seconds*1000)
  with self.assertRaises(ValueError):m.validate_vibe_video(movie(61))
 def test_exact_photo_selection_and_exif_orientation(self):
  image=Image.new('RGB',(400,200),'red');image.paste('blue',(200,0,400,200));out=io.BytesIO();image.save(out,'PNG');original=out.getvalue()
  result=m.process(original,'image/png',{'crop_rect':{'x':.5,'y':0,'w':.5,'h':1}},'vibe')['parts'][0]
  with Image.open(io.BytesIO(base64.b64decode(result['data']))) as selected:
   self.assertEqual(selected.size,(200,200));r,g,b=selected.getpixel((100,100));self.assertGreater(b,220);self.assertLess(r,25)
  exif=Image.Exif();exif[274]=6;rotated=io.BytesIO();image.save(rotated,'JPEG',exif=exif)
  self.assertEqual((m.probe(rotated.getvalue(),'image/jpeg')['width'],m.probe(rotated.getvalue(),'image/jpeg')['height']),(200,400))
  selected=m.process(rotated.getvalue(),'image/jpeg',{'crop_rect':{'x':0,'y':.5,'w':1,'h':.5}},'vibe')['parts'][0]
  with Image.open(io.BytesIO(base64.b64decode(selected['data']))) as frame:
   self.assertEqual(frame.size,(200,200));self.assertGreater(frame.getpixel((100,100))[2],220)
  self.assertEqual(out.getvalue(),original)
 def test_video_crop_trim_high_frame_rate_and_resampled_audio(self):
  raw=movie(2,True,fps=60,pattern=True,rate=44100)
  part=m.process(raw,'video/mp4',{'start_ms':250,'end_ms':1750,'crop_rect':{'x':.5,'y':0,'w':.5,'h':1}},'vibe')['parts'][0]
  with av.open(io.BytesIO(base64.b64decode(part['data']))) as c:
   v=c.streams.video[0];a=c.streams.audio[0];self.assertEqual((v.width,v.height),(80,90));video_end=float(v.duration*v.time_base);audio_end=float(a.duration*a.time_base)
   self.assertLess(abs(video_end-1.5),.05);self.assertLess(abs(video_end-audio_end),.05)
   frames=list(c.decode(v));self.assertAlmostEqual(float(frames[0].time),0,places=3);self.assertLess(float(frames[-1].time),1.5);self.assertGreater(frames[0].to_image().getpixel((40,45))[2],210)
  with av.open(io.BytesIO(base64.b64decode(part['data']))) as c:self.assertGreater(max(float(abs(frame.to_ndarray()).max()) for frame in c.decode(audio=0)),.1)
 def test_transparent_photo_uses_the_preview_background(self):
  out=io.BytesIO();Image.new('RGBA',(100,100),(255,0,0,0)).save(out,'PNG')
  part=m.process(out.getvalue(),'image/png',{},'vibe')['parts'][0]
  with Image.open(io.BytesIO(base64.b64decode(part['data']))) as im:
   for actual,wanted in zip(im.getpixel((50,50)),(9,11,32)):self.assertLess(abs(actual-wanted),3)
 def test_camera_webm_without_duration_header(self):
  out=io.BytesIO()
  with av.open(out,'w',format='webm',options={'live':'1'}) as c:
   stream=c.add_stream('libvpx',rate=10);stream.width=160;stream.height=90;stream.pix_fmt='yuv420p'
   for i in range(20):
    frame=av.VideoFrame.from_image(Image.new('RGB',(160,90),'blue'));frame.pts=i;frame.time_base=Fraction(1,10)
    for packet in stream.encode(frame):c.mux(packet)
   for packet in stream.encode():c.mux(packet)
  raw=out.getvalue()
  with av.open(io.BytesIO(raw)) as c:self.assertIsNone(c.duration)
  self.assertAlmostEqual(m.probe(raw,'video/webm')['duration_ms'],2000,delta=100)
  part=m.process(raw,'video/webm',{'start_ms':500,'end_ms':1500},'vibe')['parts'][0]
  self.assertEqual(part['duration_ms'],1000)
 def test_between_frame_cut_preserves_the_visible_start_and_exact_end(self):
  raw=movie(3,True,fps=30);start=275;end=1725;expected=None
  with av.open(io.BytesIO(raw)) as c:
   for frame in c.decode(video=0):
    if float(frame.time)>start/1000:break
    expected=frame.to_image().getpixel((80,45))
  part=m.process(raw,'video/mp4',{'start_ms':start,'end_ms':end},'vibe')['parts'][0]
  with av.open(io.BytesIO(base64.b64decode(part['data']))) as c:
   video=c.streams.video[0];audio=c.streams.audio[0];self.assertAlmostEqual(float(video.duration*video.time_base),(end-start)/1000,places=3)
   self.assertLess(abs(float(audio.duration*audio.time_base)-(end-start)/1000),.03)
   frames=list(c.decode(video));first=frames[0];self.assertEqual(float(first.time),0);self.assertAlmostEqual(float(frames[1].time),.025,places=3)
   for actual,wanted in zip(first.to_image().getpixel((80,45)),expected):self.assertLess(abs(actual-wanted),6)

if __name__=='__main__':unittest.main()
