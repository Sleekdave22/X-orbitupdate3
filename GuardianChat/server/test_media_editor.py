import base64,time,urllib.error,unittest
from unittest.mock import patch
from test_vibes_activity import VibeTest
from test_media_processing import movie
import media_editor

class MediaEditorTest(unittest.TestCase):
 setUp=VibeTest.setUp;tearDown=VibeTest.tearDown;call=VibeTest.call;register=VibeTest.register;photo=VibeTest.photo
 def upload(self,u,**extra):return self.call('/media-editor/upload',{'client_id':'original-retry-key','destination':'vibe','mime':'image/png','media':self.photo(),**extra},u['token'])
 def wait(self,u,ident):
  for _ in range(400):
   r=self.call('/media-editor/job?id='+ident,token=u['token'])
   if r['state'] not in ('queued','processing'):return r
   time.sleep(.05)
  self.fail('Editor job did not finish')
 def test_original_privacy_retry_export_and_cleanup(self):
  a=self.register('Author');b=self.register('Other');x=self.upload(a);self.assertEqual(x['id'],self.upload(a)['id'])
  original=self.call('/media-editor/original?id='+x['id'],token=a['token']);self.assertEqual(original['data'],self.photo())
  for target in (b,{'token':''}):
   with self.assertRaises(urllib.error.HTTPError):self.call('/media-editor/original?id='+x['id'],token=target['token'])
  body={'asset':x['id'],'client_id':'render-retry-key','edits':{'rotation':90}}
  job=self.call('/media-editor/process',body,a['token']);self.assertEqual(job['id'],self.call('/media-editor/process',body,a['token'])['id'])
  result=self.wait(a,job['id']);self.assertEqual(result['state'],'ready',result);part=result['parts'][0]
  self.assertEqual(self.call('/media-editor/media?id='+part['id'],token=a['token'])['mime'],'image/jpeg')
  with self.assertRaises(urllib.error.HTTPError):self.call('/media-editor/media?id='+part['id'],token=b['token'])
  with self.server.db() as d:d.execute('UPDATE media_editor_assets SET expires=1 WHERE id=?',(x['id'],))
  with self.assertRaises(urllib.error.HTTPError):self.call('/media-editor/media?id='+part['id'],token=a['token'])
  with self.server.db() as d:media_editor.purge(d);self.assertEqual(d.execute('SELECT COUNT(*) FROM media_editor_assets').fetchone()[0],0);self.assertEqual(d.execute('SELECT COUNT(*) FROM media_editor_renders').fetchone()[0],0)
 def test_recipe_retry_cannot_replace_original_or_destination(self):
  a=self.register('Author');x=self.upload(a)
  with self.assertRaises(urllib.error.HTTPError):self.upload(a,destination='plaza')
  with patch('media_editor.launch_worker'):
   body={'asset':x['id'],'client_id':'render-retry-key','edits':{'rotation':90}};job=self.call('/media-editor/process',body,a['token'])
   with self.assertRaises(urllib.error.HTTPError):self.call('/media-editor/process',body|{'edits':{'rotation':180}},a['token'])
   self.call('/media-editor/cancel',{'id':job['id']},a['token']);self.assertEqual(self.call('/media-editor/job?id='+job['id'],token=a['token'])['state'],'cancelled')
  with self.server.db() as d:self.assertIsNotNone(d.execute('SELECT data FROM media_editor_assets WHERE id=?',(x['id'],)).fetchone(),'Cancel preserves original')
 def test_private_jobs_and_cancel_are_account_scoped(self):
  a=self.register('Author');b=self.register('Other');x=self.upload(a)
  with patch('media_editor.launch_worker'):
   job=self.call('/media-editor/process',{'asset':x['id'],'client_id':'render-retry-key','edits':{}},a['token'])
   for path,body in [('/media-editor/job?id='+job['id'],None),('/media-editor/cancel',{'id':job['id']}),('/media-editor/process',{'asset':x['id'],'client_id':'other-render-key','edits':{}})]:
    with self.assertRaises(urllib.error.HTTPError):self.call(path,body,b['token'])
 def test_real_long_video_exports_ordered_segments(self):
  a=self.register('Author');b=self.register('Viewer');x=self.upload(a,mime='video/mp4',media=base64.b64encode(movie(61,True)).decode())
  job=self.call('/media-editor/process',{'asset':x['id'],'client_id':'split-render-key','edits':{'split':True}},a['token']);result=self.wait(a,job['id'])
  self.assertEqual(result['state'],'ready',result);self.assertEqual([r['duration_ms'] for r in result['parts']],[60000,1000]);self.assertEqual([r['position'] for r in result['parts']],[0,1])
  for i,part in enumerate(result['parts']):
   body={'media_id':part['id'],'client_id':'edited-vibe-'+str(i),'visibility':'private','audience':[b['id']]}
   published=self.call('/vibe/publish',body,a['token']);self.assertEqual(self.call('/vibe/publish',body,a['token'])['id'],published['id'])
   media=self.call('/vibe/media?id='+published['id']+'&protected=1',token=b['token']);self.assertEqual(media['duration_ms'],part['duration_ms']);self.assertEqual(media['start_ms'],part['start_ms'])
  self.assertEqual(len(self.call('/vibe/feed?visibility=private',token=b['token'])['groups'][0]['items']),2)
 def test_render_cannot_cross_destination(self):
  a=self.register('Author');x=self.upload(a,destination='plaza');job=self.call('/media-editor/process',{'asset':x['id'],'client_id':'plaza-render-key','edits':{}},a['token']);result=self.wait(a,job['id'])
  self.assertEqual(result['state'],'ready',result)
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/publish',{'media_id':result['parts'][0]['id'],'client_id':'wrong-destination','visibility':'public'},a['token'])
 def test_large_input_background_pipe_boundary_completes(self):
  a=self.register('Author');raw=movie(155,True);self.assertGreater(len(base64.b64encode(raw)),65536)
  x=self.upload(a,mime='video/mp4',media=base64.b64encode(raw).decode());job=self.call('/media-editor/process',{'asset':x['id'],'client_id':'large-input-key','edits':{'split':True}},a['token']);result=self.wait(a,job['id'])
  self.assertEqual(result['state'],'ready',result);self.assertEqual([p['duration_ms'] for p in result['parts']],[60000,60000,35000])

if __name__=='__main__':unittest.main()
