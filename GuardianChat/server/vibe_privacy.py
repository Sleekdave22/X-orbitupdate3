"""Author-controlled visibility and viewer-controlled feed muting, account scoped."""
import json

def schema(d):
 d.executescript('''CREATE TABLE IF NOT EXISTS vibe_privacy(uid TEXT PRIMARY KEY,public_audience TEXT NOT NULL DEFAULT 'everyone');
 CREATE TABLE IF NOT EXISTS vibe_visibility_rules(owner TEXT NOT NULL,target TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('exclude','mute')),PRIMARY KEY(owner,target,kind));''')

def config(d,uid):
 row=d.execute('SELECT public_audience FROM vibe_privacy WHERE uid=?',(uid,)).fetchone()
 return {'public_audience':row[0] if row else 'everyone',**{kind:[r[0] for r in d.execute('SELECT target FROM vibe_visibility_rules WHERE owner=? AND kind=? ORDER BY target',(uid,kind))] for kind in ('exclude','mute')}}

def permitted(d,viewer,author,visibility):
 if viewer==author:return True
 if d.execute("SELECT 1 FROM vibe_visibility_rules WHERE owner=? AND target=? AND kind='exclude'",(author,viewer)).fetchone():return False
 if visibility=='private':return True
 audience=config(d,author)['public_audience']
 if audience=='contacts':return bool(d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(author,viewer)).fetchone())
 if audience=='followers':return bool(d.execute("SELECT 1 FROM social_follows WHERE follower=? AND target=? AND state='accepted'",(viewer,author)).fetchone())
 return True

def muted(d,viewer,author):
 return bool(d.execute("SELECT 1 FROM vibe_visibility_rules WHERE owner=? AND target=? AND kind='mute'",(viewer,author)).fetchone())

def get(server,uid):
 with server.db() as d:
  settings=config(d,uid)
  rows=d.execute('''SELECT DISTINCT u.id,u.name,u.nickname FROM users u WHERE u.id<>? AND
   (EXISTS(SELECT 1 FROM contacts c WHERE c.owner=? AND c.peer=u.id) OR
    EXISTS(SELECT 1 FROM social_follows f WHERE (f.follower=? AND f.target=u.id) OR (f.target=? AND f.follower=u.id)) OR
    EXISTS(SELECT 1 FROM vibe_visibility_rules r WHERE r.owner=? AND r.target=u.id) OR
    EXISTS(SELECT 1 FROM vibe_views v JOIN vibe_items i ON i.id=v.item WHERE i.uid=? AND v.uid=u.id)) ORDER BY u.name,u.id''',(uid,uid,uid,uid,uid,uid)).fetchall()
  return settings|{'accounts':[dict(r) for r in rows]}

def save(d,uid,b):
 audience=b.get('public_audience')
 if audience not in ('everyone','contacts','followers'):raise ValueError('Choose who can view Public Vibes')
 values={}
 for kind in ('exclude','mute'):
  entries=b.get(kind,[])
  if not isinstance(entries,list) or len(entries)>500 or any(not isinstance(x,str) or x==uid for x in entries):raise ValueError('Choose valid accounts for Vibe privacy')
  for target in set(entries):
   if not d.execute('SELECT 1 FROM users WHERE id=?',(target,)).fetchone():raise ValueError('Account not available')
  values[kind]=sorted(set(entries))
 d.execute('INSERT INTO vibe_privacy VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET public_audience=excluded.public_audience',(uid,audience))
 for kind,targets in values.items():
  d.execute('DELETE FROM vibe_visibility_rules WHERE owner=? AND kind=?',(uid,kind))
  d.executemany('INSERT INTO vibe_visibility_rules VALUES(?,?,?)',[(uid,target,kind) for target in targets])
 return {'ok':True,**config(d,uid)}
