import unittest,urllib.error
import test_server
class GameplayRoomsTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call
 def test_admin_can_assign_phone_host_without_granting_admin(self):
  admin,phone,stranger=[self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':n}) for n in ['Admin','Phone','Stranger']]
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(admin['id'],))
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_create',{'identity':phone['id'],'broadcaster':'invited'},admin['token'])
  self.call('/gaming/profile',{'tag':'Phone','game_id':'phone-game','adult':True},phone['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_create',{'identity':admin['id'],'broadcaster':'self'},phone['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_create',{'identity':phone['id'],'broadcaster':'arbitrary'},admin['token'])
  room=self.call('/gaming/stream_create',{'identity':phone['id'],'broadcaster':'invited'},admin['token'])
  self.assertEqual(room['broadcaster'],phone['id']);self.assertEqual(room['viewer'],admin['id'])
  summary=self.call('/gaming/summary',token=phone['token']);self.assertFalse(summary['can_admin']);self.assertEqual(summary['stream_rooms'][0]['a'],phone['id'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_begin',{'room':room['id']},admin['token'])
  self.call('/gaming/stream_begin',{'room':room['id']},phone['token'])
  self.call('/gaming/stream_watch',{'room':room['id']},admin['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_watch',{'room':room['id']},stranger['token'])
  self.call('/gaming/stream_end',{'room':room['id']},phone['token'])
  with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM game_stream_rooms').fetchone()[0],0)
