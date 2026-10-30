import json,time,unittest,urllib.error
import test_server
import friend_match as fm

T=['funny','calm','adventurous','curious','creative','ambitious','caring','honest']

class RuleTest(unittest.TestCase):
    def test_three_of_three_and_one_of_two(self):
        high=['funny','calm','honest'];cons=['gamer','sporty']
        self.assertTrue(fm.is_match({'funny','calm','honest','gamer'},high,cons))
        self.assertTrue(fm.is_match({'funny','calm','honest','gamer','sporty'},high,cons))
        self.assertFalse(fm.is_match({'funny','calm','honest'},high,cons))        # no considerable
        self.assertFalse(fm.is_match({'funny','calm','gamer','sporty'},high,cons))  # only 2 of 3 important
        self.assertFalse(fm.is_match(set(),high,cons))
    def test_catalog_is_consistent(self):
        self.assertEqual(len(fm.TRAIT_KEYS),len(fm.TRAITS))
        self.assertGreaterEqual(len(fm.TRAITS),20)

class FriendTest(unittest.TestCase):
    setUp=test_server.ChatTest.setUp
    tearDown=test_server.ChatTest.tearDown
    call=test_server.ChatTest.call
    def register(self,name):return self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':name})
    def code(self,path,body=None,token=''):
        try:self.call(path,body,token or '');return 200
        except urllib.error.HTTPError as e:return e.code
    def person(self,name,traits,available=True,**settings):
        u=self.register(name)
        if traits:self.call('/friends/traits',{'traits':traits},u['token'])
        if available:self.call('/friends/settings',dict(available=True,**settings),u['token'])
        return u
    def send(self,u,high=('funny','calm','honest'),cons=('gamer','sporty'),intent='casual',note=''):
        return self.call('/friends/broadcast',{'high':list(high),'considerable':list(cons),'intent':intent,'note':note},u['token'])
    def inbox(self,u):return self.call('/friends/inbox',token=u['token'])['requests']
    GOOD=['funny','calm','honest','gamer','music_lover']

    def test_only_available_people_with_matching_traits_receive_requests(self):
        s=self.person('Sender',None,available=False)
        match=self.person('Match',self.GOOD)
        off=self.person('Off',self.GOOD,available=False)
        weak=self.person('Weak',['funny','calm','gamer','sporty','music_lover'])          # missing 'honest'
        noneed=self.person('NoConsiderable',['funny','calm','honest','music_lover','foodie'])
        self.send(s)
        self.assertEqual(len(self.inbox(match)),1)
        for u in (off,weak,noneed):self.assertEqual(self.inbox(u),[])

    def test_request_shows_sender_intent_and_matched_traits_only(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD+['bookworm'])
        self.send(s,intent='deep',note='Book chats')
        r=self.inbox(m)[0]
        self.assertEqual(r['from']['name'],'Sender');self.assertEqual(r['intent_label'],'Deep conversations');self.assertEqual(r['note'],'Book chats')
        self.assertEqual({t['id'] for t in r['matched']},{'funny','calm','honest','gamer'})   # not music_lover/bookworm
        self.assertNotIn('bookworm',json.dumps(r))

    def test_sender_cannot_see_who_or_how_many(self):
        s=self.person('Sender',None,available=False);self.person('A',self.GOOD);self.person('B',self.GOOD)
        out=self.send(s)
        self.assertEqual(set(out),{'id','remaining_today'})
        mine=self.call('/friends/mine',token=s['token'])
        self.assertEqual(mine['broadcasts'][0]['accepted'],[])
        self.assertNotIn('sent',json.dumps(mine))

    def test_accept_creates_a_mutual_contact_only(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD)
        self.send(s);rid=self.inbox(m)[0]['id']
        self.assertEqual(self.call('/friends/respond',{'id':rid,'action':'accept'},m['token'])['status'],'accepted')
        self.assertIn(m['id'],[u['id'] for u in self.call('/users',token=s['token'])['users']])
        self.assertIn(s['id'],[u['id'] for u in self.call('/users',token=m['token'])['users']])
        self.assertEqual(self.call('/messages?peer=%s'%s['id'],token=m['token']).get('messages',[]),[])  # no forced chat
        mine=self.call('/friends/mine',token=s['token'])['broadcasts'][0]['accepted']
        self.assertEqual([a['name'] for a in mine],['Match'])
        self.assertEqual(self.code('/friends/respond',{'id':rid,'action':'accept'},m['token']),400)  # one answer only

    def test_decline_and_block_stop_further_requests(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD)
        self.send(s);self.call('/friends/respond',{'id':self.inbox(m)[0]['id'],'action':'decline'},m['token'])
        self.send(s,high=('funny','calm','honest'),cons=('gamer','sporty'),intent='deep')
        self.assertEqual(self.inbox(m),[])                        # cooldown after decline
        s2=self.person('Pest',None,available=False);self.send(s2);rid=self.inbox(m)[0]['id']
        self.call('/friends/respond',{'id':rid,'action':'block'},m['token'])
        with self.server.db() as d:d.execute('DELETE FROM friend_requests WHERE sender=?',(s2['id'],))
        self.send(s2);self.assertEqual(self.inbox(m),[])

    def test_existing_contacts_and_repeat_senders_are_skipped(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD)
        self.call('/contacts',{'code':m['id']},s['token']);self.send(s);self.assertEqual(self.inbox(m),[])
        s2=self.person('Again',None,available=False);self.send(s2);self.send(s2);self.assertEqual(len(self.inbox(m)),1)

    def test_daily_broadcast_limit(self):
        s=self.person('Sender',None,available=False)
        for _ in range(fm.BROADCASTS_PER_DAY):self.send(s)
        self.assertEqual(self.code('/friends/broadcast',{'high':['funny','calm','honest'],'considerable':['gamer','sporty'],'intent':'casual'},s['token']),403)

    def test_broadcast_shape_is_strict(self):
        s=self.person('Sender',None,available=False)
        bad=[dict(high=['funny','calm'],considerable=['gamer','sporty','foodie']),dict(high=['funny','calm','honest'],considerable=['gamer']),
             dict(high=['funny','calm','honest'],considerable=['funny','sporty']),dict(high=['funny','calm','nope'],considerable=['gamer','sporty']),
             dict(high=['funny','funny','honest'],considerable=['gamer','sporty'])]
        for b in bad:self.assertEqual(self.code('/friends/broadcast',dict(b,intent='casual'),s['token']),400,b)
        self.assertEqual(self.code('/friends/broadcast',{'high':['funny','calm','honest'],'considerable':['gamer','sporty'],'intent':'bad'},s['token']),400)
        self.assertEqual(self.code('/friends/broadcast',{'high':['funny','calm','honest'],'considerable':['gamer','sporty'],'intent':'casual','note':'x'*81},s['token']),400)

    def test_availability_needs_enough_traits(self):
        u=self.register('Few');self.call('/friends/traits',{'traits':['funny','calm']},u['token'])
        self.assertEqual(self.code('/friends/settings',{'available':True},u['token']),400)
        self.assertEqual(self.code('/friends/traits',{'traits':['funny','bogus']},u['token']),400)
        self.assertEqual(self.code('/friends/traits',{'traits':[k for k,_ in fm.TRAITS][:fm.MY_TRAITS_MAX+1]},u['token']),400)
        self.call('/friends/traits',{'traits':self.GOOD},u['token']);self.call('/friends/settings',{'available':True},u['token'])
        self.assertEqual(self.code('/friends/traits',{'traits':['funny']},u['token']),400)   # cannot drop below minimum while available
        self.call('/friends/settings',{'available':False},u['token']);self.call('/friends/traits',{'traits':['funny']},u['token'])

    def test_switching_off_hides_but_pending_can_still_be_answered(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD)
        self.send(s);rid=self.inbox(m)[0]['id']
        self.call('/friends/settings',{'available':False},m['token'])
        self.assertEqual(self.call('/friends/respond',{'id':rid,'action':'accept'},m['token'])['status'],'accepted')
        s2=self.person('Later',None,available=False);self.send(s2);self.assertEqual(self.inbox(m),[])

    def test_traits_are_private(self):
        m=self.person('Match',self.GOOD);o=self.register('Other')
        self.assertEqual(self.call('/friends/info',token=o['token'])['mine'],[])
        for path in ('/friends/inbox','/friends/mine','/users','/navigation/state'):
            self.assertNotIn('music_lover',json.dumps(self.call(path,token=o['token'])))
        self.assertEqual(self.call('/friends/info',token=m['token'])['mine'],sorted(self.GOOD))

    def test_badge_counts_and_clears(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD)
        self.send(s)
        self.assertEqual(self.call('/navigation/state',token=m['token'])['friend_requests'],1)
        rid=self.inbox(m)[0]['id']
        self.assertEqual(self.call('/navigation/state',token=m['token'])['friend_requests'],0)   # opening the inbox clears it
        self.call('/friends/respond',{'id':rid,'action':'accept'},m['token'])
        self.assertEqual(self.call('/navigation/state',token=s['token'])['friend_requests'],1)   # sender hears about the acceptance
        self.call('/friends/mine',token=s['token'])
        self.assertEqual(self.call('/navigation/state',token=s['token'])['friend_requests'],0)

    def test_notification_preferences_time_the_badge_not_the_inbox(self):
        base=1_700_000_000   # a fixed instant
        off=dict(notify='off',quiet_start=None,quiet_end=None,tz_offset=0)
        self.assertIsNone(fm._visible_at(off,base))
        inst=dict(notify='instant',quiet_start=None,quiet_end=None,tz_offset=0)
        self.assertEqual(fm._visible_at(inst,base),base)
        daily=dict(notify='daily',quiet_start=None,quiet_end=None,tz_offset=0)
        at=fm._visible_at(daily,base)
        self.assertGreater(at,base);self.assertLessEqual(at-base,86400);self.assertEqual((at%86400)//3600,fm.DAILY_SUMMARY_HOUR)
        quiet=dict(notify='instant',quiet_start=22,quiet_end=7,tz_offset=0)
        night=base-base%86400+23*3600
        self.assertEqual((fm._visible_at(quiet,night)%86400)//3600,7);self.assertGreater(fm._visible_at(quiet,night),night)
        day=base-base%86400+12*3600;self.assertEqual(fm._visible_at(quiet,day),day)
        west=dict(notify='daily',quiet_start=None,quiet_end=None,tz_offset=-300)   # UTC-5
        local=(fm._visible_at(west,base)-300*60)%86400    # = utc + offset(-300min)... shifted back
        self.assertEqual((((fm._visible_at(west,base)+west['tz_offset']*60)%86400)//3600),fm.DAILY_SUMMARY_HOUR)
    def test_daily_summary_delays_badge_but_request_is_in_inbox(self):
        s=self.person('Sender',None,available=False);m=self.person('Match',self.GOOD,notify='daily')
        self.send(s)
        self.assertEqual(self.call('/navigation/state',token=m['token'])['friend_requests'],0)
        self.assertEqual(len(self.inbox(m)),1)

    def test_needs_sign_in(self):
        for path in ('/friends/info','/friends/inbox','/friends/mine'):self.assertEqual(self.code(path),401)
        self.assertEqual(self.code('/friends/settings',{'available':True}),401)

if __name__=='__main__':unittest.main()
