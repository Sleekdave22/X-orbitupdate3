"""Broadcast friend matching (Chat).

Consent is structural. Only people who switch on "Available to be friended" can receive a request.
A sender picks exactly 5 traits they would like in a friend: 3 are Highly Important and 2 are
Considerable. A person is a match only when they have all 3 Highly Important traits AND at least 1 of
the 2 Considerable ones. Only matches receive a request. The sender never learns who was matched or how
many; they only hear back from people who accept. Accepting creates a mutual contact and nothing else.

Receivers' own trait lists are never returned to anyone. A request shows the sender, their stated
intent and which of the sender's chosen traits the receiver has.
"""
import json, random, time, uuid

TRAITS = [
    ('funny', 'Funny'), ('calm', 'Calm'), ('adventurous', 'Adventurous'), ('curious', 'Curious'),
    ('creative', 'Creative'), ('ambitious', 'Ambitious'), ('caring', 'Caring'), ('honest', 'Honest'),
    ('loyal', 'Loyal'), ('outgoing', 'Outgoing'), ('quiet_thinker', 'Quiet thinker'), ('optimistic', 'Optimistic'),
    ('organised', 'Organised'), ('spontaneous', 'Spontaneous'), ('sporty', 'Sporty'), ('gamer', 'Gamer'),
    ('bookworm', 'Bookworm'), ('music_lover', 'Music lover'), ('foodie', 'Foodie'), ('traveller', 'Traveller'),
    ('techie', 'Techie'), ('faith_centred', 'Faith-centred'), ('family_oriented', 'Family-oriented'),
    ('deep_talker', 'Deep talker'),
]
TRAIT_KEYS = {k for k, _ in TRAITS}
INTENTS = [('casual', 'Casual hangouts'), ('deep', 'Deep conversations'), ('activity', 'Activity partners'),
           ('long_term', 'Long-term friendship'), ('exploring', 'Just exploring')]
INTENT_KEYS = {k for k, _ in INTENTS}
NOTIFY_MODES = ('instant', 'daily', 'off')

MY_TRAITS_MIN = 5          # needed before someone can switch availability on
MY_TRAITS_MAX = 12
BROADCASTS_PER_DAY = 3
MAX_RECIPIENTS = 50        # per broadcast
PAIR_COOLDOWN = 14 * 86400 # the same sender cannot reach the same person again within this time
DECLINE_COOLDOWN = 30 * 86400
REQUEST_LIFE = 30 * 86400
DAILY_SUMMARY_HOUR = 9     # local time when daily-summary requests surface
NOTE_MAX = 80


def init(server):
    with server.db() as d:
        d.executescript('''
        CREATE TABLE IF NOT EXISTS friend_settings(uid TEXT PRIMARY KEY,available INTEGER NOT NULL DEFAULT 0,
          notify TEXT NOT NULL DEFAULT 'instant',quiet_start INTEGER,quiet_end INTEGER,tz_offset INTEGER NOT NULL DEFAULT 0,
          updated INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS friend_traits(uid TEXT NOT NULL,trait TEXT NOT NULL,PRIMARY KEY(uid,trait));
        CREATE TABLE IF NOT EXISTS friend_broadcasts(id TEXT PRIMARY KEY,sender TEXT NOT NULL,intent TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',high TEXT NOT NULL,considerable TEXT NOT NULL,created INTEGER NOT NULL,sent INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS friend_broadcasts_day ON friend_broadcasts(sender,created);
        CREATE TABLE IF NOT EXISTS friend_requests(id TEXT PRIMARY KEY,broadcast TEXT NOT NULL,sender TEXT NOT NULL,
          receiver TEXT NOT NULL,intent TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',matched TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',created INTEGER NOT NULL,visible_at INTEGER,seen INTEGER NOT NULL DEFAULT 0,
          responded INTEGER,sender_seen INTEGER NOT NULL DEFAULT 1);
        CREATE UNIQUE INDEX IF NOT EXISTS friend_one_per_broadcast ON friend_requests(broadcast,receiver);
        CREATE INDEX IF NOT EXISTS friend_requests_inbox ON friend_requests(receiver,status,created);
        CREATE INDEX IF NOT EXISTS friend_requests_pair ON friend_requests(sender,receiver,created);
        CREATE TABLE IF NOT EXISTS friend_blocks(blocker TEXT NOT NULL,blocked TEXT NOT NULL,created INTEGER NOT NULL,
          PRIMARY KEY(blocker,blocked));
        ''')


def catalog():
    return {'traits': [{'id': k, 'label': v} for k, v in TRAITS], 'intents': [{'id': k, 'label': v} for k, v in INTENTS],
            'limits': {'my_traits_min': MY_TRAITS_MIN, 'my_traits_max': MY_TRAITS_MAX, 'broadcasts_per_day': BROADCASTS_PER_DAY,
                       'note_max': NOTE_MAX, 'daily_summary_hour': DAILY_SUMMARY_HOUR}}


def _settings(d, uid):
    r = d.execute('SELECT * FROM friend_settings WHERE uid=?', (uid,)).fetchone()
    if not r:
        return {'available': False, 'notify': 'instant', 'quiet_start': None, 'quiet_end': None, 'tz_offset': 0}
    return {'available': bool(r['available']), 'notify': r['notify'], 'quiet_start': r['quiet_start'],
            'quiet_end': r['quiet_end'], 'tz_offset': r['tz_offset']}


def _mine(d, uid):
    return sorted(r['trait'] for r in d.execute('SELECT trait FROM friend_traits WHERE uid=?', (uid,)))


def _hour(v, name):
    if v is None or v == '':
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 23:
        raise ValueError('%s must be an hour from 0 to 23' % name)
    return v


def info(server, uid):
    with server.db() as d:
        out = catalog()
        out['mine'] = _mine(d, uid)
        out['settings'] = _settings(d, uid)
        return out


def set_traits(server, uid, body):
    traits = body.get('traits')
    if not isinstance(traits, list) or any(not isinstance(t, str) for t in traits):
        raise ValueError('Choose your traits from the list')
    chosen = set(traits)
    if not chosen <= TRAIT_KEYS:
        raise ValueError('Choose your traits from the list')
    if len(chosen) > MY_TRAITS_MAX:
        raise ValueError('Choose at most %d traits' % MY_TRAITS_MAX)
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        if len(chosen) < MY_TRAITS_MIN and _settings(d, uid)['available']:
            raise ValueError('Keep at least %d traits while you are available, or switch availability off first' % MY_TRAITS_MIN)
        d.execute('DELETE FROM friend_traits WHERE uid=?', (uid,))
        d.executemany('INSERT INTO friend_traits(uid,trait) VALUES(?,?)', [(uid, t) for t in sorted(chosen)])
    return {'mine': sorted(chosen)}


def set_settings(server, uid, body):
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        cur = _settings(d, uid)
        available = cur['available'] if 'available' not in body else bool(body['available'])
        notify = body.get('notify', cur['notify'])
        if notify not in NOTIFY_MODES:
            raise ValueError('Choose instant, daily summary or off')
        qs = _hour(body['quiet_start'], 'Quiet hours start') if 'quiet_start' in body else cur['quiet_start']
        qe = _hour(body['quiet_end'], 'Quiet hours end') if 'quiet_end' in body else cur['quiet_end']
        if (qs is None) != (qe is None):
            raise ValueError('Set both the start and the end of quiet hours')
        tz = body.get('tz_offset', cur['tz_offset'])
        if isinstance(tz, bool) or not isinstance(tz, int) or not -14 * 60 <= tz <= 14 * 60:
            raise ValueError('Invalid time zone')
        if available and len(_mine(d, uid)) < MY_TRAITS_MIN:
            raise ValueError('Choose at least %d traits about yourself before you become available' % MY_TRAITS_MIN)
        d.execute('INSERT INTO friend_settings(uid,available,notify,quiet_start,quiet_end,tz_offset,updated) VALUES(?,?,?,?,?,?,?) '
                  'ON CONFLICT(uid) DO UPDATE SET available=excluded.available,notify=excluded.notify,quiet_start=excluded.quiet_start,'
                  'quiet_end=excluded.quiet_end,tz_offset=excluded.tz_offset,updated=excluded.updated',
                  (uid, int(available), notify, qs, qe, tz, int(time.time())))
        return {'settings': _settings(d, uid)}


def _visible_at(s, now):
    """When a new request should start to show in the receiver's badge. Requests are always in the inbox."""
    if s['notify'] == 'off':
        return None
    local = now + s['tz_offset'] * 60
    if s['notify'] == 'daily':
        day = local - local % 86400
        at = day + DAILY_SUMMARY_HOUR * 3600
        if at <= local:
            at += 86400
        return at - s['tz_offset'] * 60
    qs, qe = s['quiet_start'], s['quiet_end']
    if qs is None or qs == qe:
        return now
    hour = (local % 86400) // 3600
    inside = (qs <= hour < qe) if qs < qe else (hour >= qs or hour < qe)
    if not inside:
        return now
    day = local - local % 86400
    at = day + qe * 3600
    if at <= local:
        at += 86400
    return at - s['tz_offset'] * 60


def _validate_broadcast(body):
    high, cons = body.get('high'), body.get('considerable')
    if not isinstance(high, list) or not isinstance(cons, list) or any(not isinstance(t, str) for t in high + cons):
        raise ValueError('Choose 3 Highly Important and 2 Considerable traits')
    if len(set(high)) != 3 or len(set(cons)) != 2 or len(high) != 3 or len(cons) != 2:
        raise ValueError('Choose exactly 3 Highly Important and 2 Considerable traits')
    if set(high) & set(cons):
        raise ValueError('A trait can only be in one group')
    if not (set(high) | set(cons)) <= TRAIT_KEYS:
        raise ValueError('Choose traits from the list')
    intent = body.get('intent')
    if intent not in INTENT_KEYS:
        raise ValueError('Choose what kind of friendship you want')
    note = str(body.get('note') or '').strip()
    if len(note) > NOTE_MAX:
        raise ValueError('Keep your note under %d characters' % NOTE_MAX)
    return sorted(high), sorted(cons), intent, note


def is_match(theirs, high, cons):
    """The whole rule: all 3 Highly Important, at least 1 of the 2 Considerable."""
    theirs = set(theirs)
    return set(high) <= theirs and len(set(cons) & theirs) >= 1


def broadcast(server, uid, body):
    high, cons, intent, note = _validate_broadcast(body)
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        used = d.execute('SELECT COUNT(*) FROM friend_broadcasts WHERE sender=? AND created>?', (uid, now - 86400)).fetchone()[0]
        if used >= BROADCASTS_PER_DAY:
            raise PermissionError('You can send %d broadcasts a day. Try again tomorrow.' % BROADCASTS_PER_DAY)
        bid = uuid.uuid4().hex[:16]
        import social
        candidates = [r['uid'] for r in d.execute(
            'SELECT s.uid FROM friend_settings s JOIN users u ON u.id=s.uid WHERE s.available=1 AND s.uid<>?', (uid,))]
        random.shuffle(candidates)
        sent = 0
        for rid in candidates:
            if sent >= MAX_RECIPIENTS:
                break
            theirs = {r['trait'] for r in d.execute('SELECT trait FROM friend_traits WHERE uid=?', (rid,))}
            if not is_match(theirs, high, cons):
                continue
            if social.blocked(d, uid, rid):
                continue
            if d.execute('SELECT 1 FROM friend_blocks WHERE (blocker=? AND blocked=?) OR (blocker=? AND blocked=?)', (rid, uid, uid, rid)).fetchone():
                continue
            if d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?', (uid, rid)).fetchone():
                continue
            if d.execute("SELECT 1 FROM friend_requests WHERE sender=? AND receiver=? AND (status='pending' OR created>?)",
                         (uid, rid, now - PAIR_COOLDOWN)).fetchone():
                continue
            if d.execute("SELECT 1 FROM friend_requests WHERE sender=? AND receiver=? AND status='declined' AND created>?",
                         (uid, rid, now - DECLINE_COOLDOWN)).fetchone():
                continue
            matched = sorted(set(high) | (set(cons) & theirs))
            s = _settings(d, rid)
            d.execute('INSERT INTO friend_requests(id,broadcast,sender,receiver,intent,note,matched,created,visible_at) VALUES(?,?,?,?,?,?,?,?,?)',
                      (uuid.uuid4().hex[:16], bid, uid, rid, intent, note, json.dumps(matched), now, _visible_at(s, now)))
            sent += 1
        d.execute('INSERT INTO friend_broadcasts(id,sender,intent,note,high,considerable,created,sent) VALUES(?,?,?,?,?,?,?,?)',
                  (bid, uid, intent, note, json.dumps(high), json.dumps(cons), now, sent))
    # Deliberately no count: the sender must not learn how many people matched.
    return {'id': bid, 'remaining_today': BROADCASTS_PER_DAY - used - 1}


def _label(k):
    return dict(TRAITS).get(k, k)


def inbox(server, uid):
    now = int(time.time())
    with server.db() as d:
        d.execute("UPDATE friend_requests SET status='expired' WHERE status='pending' AND created<?", (now - REQUEST_LIFE,))
        rows = d.execute("""SELECT r.*,u.name,u.nickname FROM friend_requests r JOIN users u ON u.id=r.sender
            WHERE r.receiver=? AND r.status='pending' ORDER BY r.created DESC LIMIT 100""", (uid,)).fetchall()
        import social
        out = []
        for r in rows:
            if social.blocked(d, uid, r['sender']):
                continue
            out.append({'id': r['id'], 'from': {'id': r['sender'], 'name': r['name'], 'nickname': r['nickname']},
                        'intent': r['intent'], 'intent_label': dict(INTENTS).get(r['intent'], r['intent']), 'note': r['note'],
                        'matched': [{'id': k, 'label': _label(k)} for k in json.loads(r['matched'])], 'created': r['created']})
        d.execute("UPDATE friend_requests SET seen=1 WHERE receiver=? AND status='pending'", (uid,))
        return {'requests': out}


def respond(server, uid, body):
    rid, action = str(body.get('id') or ''), body.get('action')
    if action not in ('accept', 'decline', 'ignore', 'block'):
        raise ValueError('Choose accept, decline, ignore or block')
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        r = d.execute("SELECT * FROM friend_requests WHERE id=? AND receiver=? AND status='pending'", (rid, uid)).fetchone()
        if not r:
            raise ValueError('This request is no longer available')
        import social
        if action == 'accept':
            if social.blocked(d, uid, r['sender']):
                raise PermissionError('Account interaction unavailable')
            d.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)', (uid, r['sender']))
            d.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)', (r['sender'], uid))
            d.execute("UPDATE friend_requests SET status='accepted',responded=?,sender_seen=0 WHERE id=?", (now, rid))
        elif action == 'ignore':
            d.execute("UPDATE friend_requests SET status='ignored',responded=? WHERE id=?", (now, rid))
        else:
            d.execute("UPDATE friend_requests SET status='declined',responded=? WHERE id=?", (now, rid))
            if action == 'block':
                d.execute('INSERT OR IGNORE INTO friend_blocks(blocker,blocked,created) VALUES(?,?,?)', (uid, r['sender'], now))
                d.execute("UPDATE friend_requests SET status='declined' WHERE receiver=? AND sender=? AND status='pending'", (uid, r['sender']))
    return {'status': {'accept': 'accepted', 'ignore': 'ignored'}.get(action, 'declined')}


def mine(server, uid):
    """The sender's own broadcasts. Only people who accepted are named; no delivery counts are shown."""
    with server.db() as d:
        out = []
        for b in d.execute('SELECT * FROM friend_broadcasts WHERE sender=? ORDER BY created DESC LIMIT 20', (uid,)):
            accepted = [{'id': r['receiver'], 'name': r['name'], 'nickname': r['nickname'], 'new': not r['sender_seen']} for r in d.execute(
                "SELECT r.receiver,r.sender_seen,u.name,u.nickname FROM friend_requests r JOIN users u ON u.id=r.receiver WHERE r.broadcast=? AND r.status='accepted'", (b['id'],))]
            out.append({'id': b['id'], 'created': b['created'], 'intent': b['intent'], 'intent_label': dict(INTENTS).get(b['intent'], b['intent']),
                        'note': b['note'], 'high': [{'id': k, 'label': _label(k)} for k in json.loads(b['high'])],
                        'considerable': [{'id': k, 'label': _label(k)} for k in json.loads(b['considerable'])], 'accepted': accepted})
        d.execute("UPDATE friend_requests SET sender_seen=1 WHERE sender=? AND status='accepted'", (uid,))
        used = d.execute('SELECT COUNT(*) FROM friend_broadcasts WHERE sender=? AND created>?', (uid, int(time.time()) - 86400)).fetchone()[0]
        return {'broadcasts': out, 'remaining_today': max(0, BROADCASTS_PER_DAY - used)}


def badge(d, uid):
    """Number shown on the Chat 'Find friends' button: visible pending requests plus new acceptances."""
    now = int(time.time())
    pending = d.execute("SELECT COUNT(*) FROM friend_requests WHERE receiver=? AND status='pending' AND seen=0 AND visible_at IS NOT NULL "
                        "AND visible_at<=? AND created>?", (uid, now, now - REQUEST_LIFE)).fetchone()[0]
    accepted = d.execute("SELECT COUNT(*) FROM friend_requests WHERE sender=? AND status='accepted' AND sender_seen=0", (uid,)).fetchone()[0]
    return pending + accepted


def get(server, uid, path):
    route = path.split('?')[0]
    if route == '/friends/info':
        return info(server, uid)
    if route == '/friends/inbox':
        return inbox(server, uid)
    if route == '/friends/mine':
        return mine(server, uid)
    raise KeyError(route)


def post(server, uid, path, body):
    route = {'/friends/traits': set_traits, '/friends/settings': set_settings, '/friends/broadcast': broadcast,
             '/friends/respond': respond}.get(path)
    if not route:
        raise KeyError(path)
    return route(server, uid, body)
