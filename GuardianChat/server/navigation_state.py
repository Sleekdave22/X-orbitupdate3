"""Small account-scoped navigation summary; no private Vibe media is exposed."""
import time
import vibes

def init(server):
 with server.db() as d:d.execute('CREATE TABLE IF NOT EXISTS navigation_call_views(uid TEXT NOT NULL,call_id TEXT NOT NULL,PRIMARY KEY(uid,call_id))')

def calls_seen(server,uid,body):
 ids=body.get('ids')
 if not isinstance(ids,list) or len(ids)>200 or any(not isinstance(x,str) or not 1<=len(x)<=128 for x in ids):raise ValueError('Choose the displayed missed calls')
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  for ident in set(ids):
   if not d.execute("SELECT 1 FROM call_history WHERE id=? AND recipient=? AND ended IS NOT NULL AND outcome IN ('missed','cancelled')",(ident,uid)).fetchone():raise PermissionError('Missed call unavailable to this account')
   d.execute('INSERT OR IGNORE INTO navigation_call_views(uid,call_id) VALUES(?,?)',(uid,ident))
 return {'seen':len(set(ids))}

def get(server,uid):
 with server.call_lock:server.expire_calls()
 with server.db() as d:
  unread=d.execute("""SELECT COUNT(*) FROM messages m JOIN contacts c ON c.owner=m.recipient AND c.peer=m.sender
   WHERE m.recipient=? AND m.read_at=0 AND m.kind!='call' AND m.deleted_all=0
   AND NOT EXISTS(SELECT 1 FROM message_hidden h WHERE h.user_id=? AND h.message_id=m.id)
   AND NOT EXISTS(SELECT 1 FROM chat_hidden h WHERE h.owner=? AND h.peer=m.sender AND h.through_id>=m.id)
   AND NOT EXISTS(SELECT 1 FROM social_blocks b WHERE (b.owner=? AND b.target=m.sender) OR (b.owner=m.sender AND b.target=?))""",(uid,uid,uid,uid,uid)).fetchone()[0]
  missed=d.execute("""SELECT COUNT(*) FROM call_history h WHERE h.recipient=? AND h.ended IS NOT NULL AND h.outcome IN ('missed','cancelled')
   AND NOT EXISTS(SELECT 1 FROM navigation_call_views v WHERE v.uid=? AND v.call_id=h.id)
   AND NOT EXISTS(SELECT 1 FROM social_blocks b WHERE (b.owner=? AND b.target=h.caller) OR (b.owner=h.caller AND b.target=?))""",(uid,uid,uid,uid)).fetchone()[0]
  active={};unseen=0
  for r in d.execute("""SELECT i.id,i.uid,i.visibility,i.created,i.expires,1 AS media,
   EXISTS(SELECT 1 FROM vibe_views v WHERE v.item=i.id AND v.uid=?) AS viewed,
   (i.uid=? OR EXISTS(SELECT 1 FROM contacts c WHERE c.owner=? AND c.peer=i.uid)
    OR EXISTS(SELECT 1 FROM social_follows f WHERE f.follower=? AND f.target=i.uid AND f.state='accepted')) AS connected
   FROM vibe_items i JOIN users u ON u.id=i.uid WHERE i.expires>? AND i.media IS NOT NULL ORDER BY i.created,i.rowid""",(uid,uid,uid,uid,int(time.time()))):
   if not vibes.allowed(d,uid,r) or __import__('vibe_privacy').muted(d,uid,r['uid']):continue
   if not r['connected']:continue
   if r['uid']!=uid and not r['viewed']:unseen+=1
   prior=active.get(r['uid']);count=(prior['count'] if prior else 0)+1
   active[r['uid']]={'count':count,'item':r['id'],'visibility':r['visibility'],'expires':r['expires']}
  return {'account':uid,'unread_messages':unread,'missed_calls':missed,'unseen_vibes':unseen,'vibes':active}
