import unittest, urllib.error, time
import test_market_pilot, market_demand

class DemandTest(unittest.TestCase):
    setUp = test_market_pilot.MarketPilotTest.setUp
    tearDown = test_market_pilot.MarketPilotTest.tearDown
    call = test_market_pilot.MarketPilotTest.call
    register = test_market_pilot.MarketPilotTest.register
    shop = test_market_pilot.MarketPilotTest.shop
    body = test_market_pilot.MarketPilotTest.body
    save = test_market_pilot.MarketPilotTest.save

    def ask(self, u, title, cat='electronics', desc='', **kw):
        return self.call('/market/demand_create', {'category': cat, 'title': title, 'description': desc, **kw}, u['token'])

    def admin(self):
        u = self.register('Moderator')
        with self.server.db() as d:
            d.execute('INSERT INTO game_admin VALUES(?)', (u['id'],))
        return u

    def test_differently_worded_requests_group_and_distinct_users_count(self):
        us = [self.register('B%d' % i) for i in range(4)]
        g1 = self.ask(us[0], 'I want to buy a Samsung phone')['group']
        g2 = self.ask(us[1], 'Looking for Samsung handsets', desc='cheap')['group']
        g3 = self.ask(us[2], 'samsung mobile phones please')['group']
        self.assertEqual({g1['id'], g2['id'], g3['id']}, {g1['id']})
        self.assertEqual(g3['requesters'], 3)
        other = self.ask(us[3], 'Laptop charger')['group']
        self.assertNotEqual(other['id'], g1['id'])
        # other category never joins
        self.assertNotEqual(self.ask(us[3], 'Samsung phone', cat='computers')['group']['id'], g1['id'])

    def test_same_user_cannot_inflate_and_retry_is_idempotent(self):
        a = self.register('Solo')
        g = self.ask(a, 'Samsung phone', client_id='k1')['group']
        again = self.ask(a, 'Samsung phone', client_id='k1')
        self.assertTrue(again['duplicate'])
        again = self.ask(a, 'samsung phones', client_id='k2')
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['group']['requesters'], 1)
        self.assertEqual(self.call('/market/demand_hot', token=a['token'])['groups'], [])

    def test_daily_request_cap(self):
        a = self.register('Spammer')
        for i, w in enumerate(['phone', 'laptop', 'camera', 'bicycle', 'sofa']):
            self.ask(a, 'Wanted ' + w + ' number%d' % i, cat='other')
        with self.assertRaises(urllib.error.HTTPError):
            self.ask(a, 'One more thing zebra', cat='other')

    def test_hot_threshold_notifies_opted_in_sellers_once_and_caps_per_day(self):
        s = self.shop()
        self.save(s, self.body())  # electronics listing makes the seller relevant
        quiet = self.register('QuietSeller')
        self.call('/market/register', {'shop_name': 'Quiet Store'}, quiet['token'])
        self.save(quiet, self.body() | {'title': 'Another phone'})
        self.call('/market/demand_alerts', {'alerts': True}, s['token'])   # only s opted in
        for i in range(4):
            self.ask(self.register('Buyer%d' % i), 'Samsung phone for sale %d' % i if False else 'Samsung phone')
        self.assertEqual(self.call('/market/demand_hot', token=s['token'])['groups'], [])
        fifth = self.ask(self.register('Buyer4'), 'samsung mobile')['group']
        self.assertTrue(fifth['hot'])
        mine = [n for n in self.call('/market/activity', token=s['token'])['notifications'] if 'demand' in n['target']]
        self.assertEqual(len(mine), 1)
        self.assertEqual([n for n in self.call('/market/activity', token=quiet['token'])['notifications'] if 'demand' in n['target']], [])
        # sixth requester does not re-notify
        self.ask(self.register('Buyer5'), 'Samsung phone')
        mine = [n for n in self.call('/market/activity', token=s['token'])['notifications'] if 'demand' in n['target']]
        self.assertEqual(len(mine), 1)
        # Plaza lists the hot demand
        self.assertEqual(len(self.call('/market/demand_hot', token=s['token'])['groups']), 1)

    def test_default_two_per_day_cap(self):
        s = self.shop()
        self.save(s, self.body())
        self.call('/market/demand_alerts', {'alerts': True}, s['token'])
        topics = ['Samsung phone', 'iPhone charger cable', 'Bluetooth speaker', 'Gaming headset']
        for t in topics:
            for i in range(5):
                self.ask(self.register('B%s%d' % (t[:3], i)), t)
        got = [n for n in self.call('/market/activity', token=s['token'])['notifications'] if 'demand' in n['target']]
        self.assertEqual(len(got), 2)

    def test_listing_appears_buyers_notified_once(self):
        buyer = self.register('Hopeful')
        self.ask(buyer, 'Samsung Galaxy phone')
        s = self.shop()
        self.save(s, self.body())
        with self.server.db() as d:
            d.execute("DELETE FROM demand_state")
        market_demand.sweep(self.server)
        with self.server.db() as d:
            d.execute("DELETE FROM demand_state")
        market_demand.sweep(self.server)
        n = [x for x in self.call('/market/activity', token=buyer['token'])['notifications'] if 'demand' in x['target']]
        self.assertEqual(len(n), 1)

    def test_admin_threshold_and_permissions_audited(self):
        a = self.register('Plain'); m = self.admin()
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/market/demand_admin', token=a['token'])
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/market/admin_demand_config', {'hot_threshold': 3, 'daily_push_cap': 2, 'reason': 'x'}, a['token'])
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/market/admin_demand_config', {'hot_threshold': 99, 'daily_push_cap': 2, 'reason': 'x'}, m['token'])
        self.call('/market/admin_demand_config', {'hot_threshold': 3, 'daily_push_cap': 1, 'reason': 'Lower pilot threshold'}, m['token'])
        self.assertEqual(self.call('/market/demand_admin', token=m['token'])['config'], {'hot_threshold': 3, 'daily_push_cap': 1})
        for i in range(3):
            last = self.ask(self.register('T%d' % i), 'Gaming headset')['group']
        self.assertTrue(last['hot'])
        actions = {r['action'] for r in self.call('/market/admin', token=m['token'])['audit']}
        self.assertIn('admin_demand_config', actions)

    def test_close_and_blocked_users(self):
        a = self.register('Closer')
        r = self.ask(a, 'Samsung phone')
        mine = self.call('/market/demand_mine', token=a['token'])['requests']
        self.assertEqual(len(mine), 1)
        self.call('/market/demand_close', {'id': mine[0]['id']}, a['token'])
        self.assertEqual(self.call('/market/demand_mine', token=a['token'])['requests'], [])
        b = self.register('Other')
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/market/demand_close', {'id': mine[0]['id']}, b['token'])

    def test_text_normalisation(self):
        with self.server.db() as d:
            self.assertEqual(market_demand.normalise(d, 'I want to buy cheap Handsets'), ['phone'])
            self.assertGreater(market_demand.score(['samsung', 'phone'], ['samsung', 'phone', 'used']), 0.5)
            self.assertLess(market_demand.score(['samsung', 'phone'], ['laptop', 'charger']), 0.2)

if __name__ == '__main__':
    unittest.main()
