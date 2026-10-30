import datetime,unittest,urllib.error
import test_server
import account_age

class AgeRulesTest(unittest.TestCase):
    today=datetime.date(2026,10,29)
    def test_birthday_boundaries(self):
        self.assertEqual(account_age.age_of('2008-10-29',self.today),18)
        self.assertEqual(account_age.age_of('2008-10-30',self.today),17)
        self.assertEqual(account_age.age_of('2000-02-29',datetime.date(2026,2,28)),25)
    def test_bands_and_adult_line(self):
        self.assertEqual([account_age.band(a) for a in (13,17,18,24,25,34,35,44,45,90)],['13-17','13-17','18-24','18-24','25-34','25-34','35-44','35-44','45+','45+'])
        self.assertIsNone(account_age.band(None));self.assertIsNone(account_age.band(12))
        self.assertFalse(account_age.is_adult(17));self.assertTrue(account_age.is_adult(18))
    def test_parse_rejects_bad_values(self):
        for bad,msg in [(None,'Enter your date of birth'),('','Enter your date of birth'),('05/05/1995','Enter your date of birth'),('1995-02-30','valid date'),('2999-01-01','valid date'),('1800-01-01','valid date'),('2020-01-01','at least 13')]:
            with self.assertRaisesRegex(ValueError,msg):account_age.parse(bad,self.today)
        self.assertEqual(account_age.parse('2013-10-29',self.today),'2013-10-29')
        with self.assertRaises(ValueError):account_age.parse('2013-10-30',self.today)

class SignupAgeTest(unittest.TestCase):
    setUp=test_server.ChatTest.setUp
    tearDown=test_server.ChatTest.tearDown
    call=test_server.ChatTest.call
    def attempt(self,**extra):
        body={'invite':self.server.invite,'name':'Age Tester','nickname':extra.pop('nickname','age_tester'),'sex':'undisclosed'};body.update(extra)
        try:return 201,self.call('/register',body)
        except urllib.error.HTTPError as e:return e.code,e.read().decode()
    def test_signup_needs_a_valid_age(self):
        self.assertEqual(self.attempt()[0],400)
        self.assertEqual(self.attempt(birth_date='2020-01-01')[0],400)
        self.assertEqual(self.attempt(birth_date='not-a-date')[0],400)
    def test_signup_needs_a_sex_choice(self):
        self.assertEqual(self.attempt(birth_date='1995-05-05',sex='')[0],400)
        self.assertEqual(self.attempt(birth_date='1995-05-05',sex='other')[0],400)
        for i,value in enumerate(('male','female','Undisclosed')):
            code,account=self.attempt(birth_date='1995-05-05',sex=value,nickname='sex_check_%d'%i)
            self.assertEqual(code,201);self.assertNotIn('sex',account)
            with self.server.db() as db:self.assertEqual(db.execute('SELECT sex FROM users WHERE id=?',(account['id'],)).fetchone()[0],value.lower())
    def test_rejected_signup_creates_nothing(self):
        self.attempt(birth_date='2020-01-01')
        with self.server.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
    def test_valid_age_is_stored_privately(self):
        code,account=self.attempt(birth_date='1995-05-05', sex='undisclosed',nickname='grown_up')
        self.assertEqual(code,201);self.assertNotIn('birth_date',account)
        with self.server.db() as db:self.assertEqual(db.execute('SELECT birth_date FROM users WHERE id=?',(account['id'],)).fetchone()[0],'1995-05-05')
        for path in ('/users','/profile','/profile?id='+account['id']):
            try:text=str(self.call(path,token=account['token']))
            except urllib.error.HTTPError:continue
            self.assertNotIn('1995-05-05',text);self.assertNotIn('birth_date',text);self.assertNotIn('undisclosed',text)
    def test_profile_edit_cannot_change_age(self):
        _,account=self.attempt(birth_date='1995-05-05')
        try:self.call('/profile',{'birth_date':'2012-01-01'},account['token'])
        except urllib.error.HTTPError:pass
        with self.server.db() as db:self.assertEqual(db.execute('SELECT birth_date FROM users WHERE id=?',(account['id'],)).fetchone()[0],'1995-05-05')

if __name__=='__main__':unittest.main()
