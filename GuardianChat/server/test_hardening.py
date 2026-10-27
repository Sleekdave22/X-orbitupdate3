import unittest, urllib.error, time
import test_server

class HardeningTest(unittest.TestCase):
    setUp = test_server.ChatTest.setUp
    tearDown = test_server.ChatTest.tearDown
    call = test_server.ChatTest.call
    register = test_server.ChatTest.register

    def status(self, path, body):
        try:
            self.call(path, body)
            return 200
        except urllib.error.HTTPError as e:
            return e.code

    def test_invitation_code_guessing_is_throttled(self):
        codes = [self.status('/register', {'invite': 'wrong-%d' % i, 'name': 'X'}) for i in range(10)]
        self.assertNotIn(429, codes[:8])
        self.assertTrue(all(c != 201 for c in codes))
        self.assertEqual(codes[-1], 429)
        # the correct code is also refused while throttled, so guessing cannot be confirmed
        self.assertEqual(self.status('/register', {'invite': self.server.invite, 'name': 'Late'}), 429)

    def test_signed_in_posts_have_a_per_account_ceiling(self):
        a = self.register('Chatty')
        for _ in range(600):
            self.assertTrue(self.server.allow_request(a['id']))
        self.assertFalse(self.server.allow_request(a['id']))
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call('/contacts', {'code': 'nobody'}, a['token'])
        self.assertEqual(ctx.exception.code, 429)
        # another account is unaffected
        b = self.register('Calm')
        self.assertTrue(self.server.allow_request(b['id']))

    def test_ceiling_window_resets_and_memory_is_bounded(self):
        for i in range(5200):
            self.server.allow_request('u%d' % i)
        self.assertLessEqual(len(self.server.api_hits), 5200)
        self.server.api_hits['u1'] = (time.time() - 61, 999)
        self.assertTrue(self.server.allow_request('u1'))
        for i in range(2100):
            self.server.login_attempts['ip%d' % i] = (1, time.time() - 5)
        self.server.note_failure('fresh')
        self.assertLess(len(self.server.login_attempts), 100)

if __name__ == '__main__':
    unittest.main()
