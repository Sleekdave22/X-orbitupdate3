"""Sign-up capabilities use the normal registration transaction and login path."""
import json
import urllib.error
from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import patch
import test_server


class SignupInvitationHTTP(unittest.TestCase):
    setUp = test_server.ChatTest.setUp
    tearDown = test_server.ChatTest.tearDown
    call = test_server.ChatTest.call
    register = test_server.ChatTest.register

    def own_link(self, user):
        info = self.call('/invitations/mine', token=user['token'])
        return parse_qs(urlparse(info['path']).query)['invite'][0]

    def signup(self, link, nickname='new_member', **extra):
        return self.call('/register', dict(name='New Member', nickname=nickname, birth_date='1995-05-05', sex='undisclosed',
            password='new-member-pass-123', invite_link=link, **extra))

    def test_link_signup_login_permissions_and_no_automatic_contacts(self):
        owner = self.register('Inviter'); link = self.own_link(owner)
        self.assertNotIn(self.server.invite, link)
        self.assertEqual(self.call('/invitations/check?invite=' + link), {'valid': True})
        self.assertIn(b'X ORBIT', self.call('/join?invite=' + link))
        new = self.signup(link)
        session = self.call('/login', {'identity': 'new_member', 'password': 'new-member-pass-123'})
        self.assertEqual(session['id'], new['id'])
        self.assertEqual(self.call('/users', token=new['token'])['users'], [])
        with self.server.db() as d:
            self.assertNotEqual(d.execute('SELECT password_hash FROM users WHERE id=?', (new['id'],)).fetchone()[0], 'new-member-pass-123')
            self.assertFalse(d.execute('SELECT 1 FROM game_admin WHERE uid=?', (new['id'],)).fetchone())
        self.assertEqual(self.call('/invitations/mine', token=owner['token'])['joined'], 1)
        self.assertNotEqual(self.own_link(new), link)

    def test_rotation_invalid_password_and_forgery_cannot_create_accounts(self):
        owner = self.register('Inviter'); old = self.own_link(owner)
        current = self.call('/invitations/reset', {}, owner['token'])
        link = parse_qs(urlparse(current['path']).query)['invite'][0]
        for invalid in (old, link[:-1] + ('x' if link[-1] != 'x' else 'y'), ''):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.signup(invalid, invite=self.server.invite)
            self.assertEqual(error.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/register', {'name': 'Too Short', 'nickname': 'short_pw', 'password': 'short', 'invite_link': link})
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM account_invite_joins').fetchone()[0], 0)

    def test_owner_is_session_scoped_and_duplicate_or_failed_signup_is_atomic(self):
        a, b = self.register('Alice'), self.register('Bob'); link = self.own_link(a)
        for path, body in [('/invitations/mine', None), ('/invitations/reset', {})]:
            with self.assertRaises(urllib.error.HTTPError) as error: self.call(path, body)
            self.assertEqual(error.exception.code, 401)
        own = self.call('/invitations/reset', {'owner': a['id']}, b['token'])
        self.assertTrue(own['path'].startswith('/join?invite=' + b['id'] + '.'))
        self.signup(link, 'atomic_user')
        with self.assertRaises(urllib.error.HTTPError) as error: self.signup(link, 'atomic_user')
        self.assertEqual(error.exception.code, 409)
        with patch('wallet.create_wallet', side_effect=RuntimeError('Synthetic wallet failure')):
            with self.assertRaises(urllib.error.HTTPError): self.signup(link, 'rolled_back')
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM users').fetchone()[0], 3)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM account_invite_joins').fetchone()[0], 1)
            self.assertFalse(d.execute("SELECT 1 FROM users WHERE nickname='rolled_back'").fetchone())


if __name__ == '__main__': unittest.main()
