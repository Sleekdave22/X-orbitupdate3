"""Plaza Demand and Hot Demand.

Buyers post categorised requests. Similar requests (even when worded differently) are grouped using
cheap local text normalisation: lower-casing, accents, stop words, the Plaza synonym table and light
singularisation, then token overlap. No remote model is called.

A group turns "hot" when enough DISTINCT accounts have asked for it (default 5, admin range 3 to 10).
Sellers who opted into demand alerts and who list in that category are notified, at most
`daily_push_cap` (default 2) hot-demand notices per recipient per rolling day, and never twice for the
same group. Buyers are told once per matching listing when a relevant listing appears.
"""
import json, re, time, uuid, difflib

DEFAULTS = {'hot_threshold': 5, 'daily_push_cap': 2}
LIMITS = {'hot_threshold': (3, 10), 'daily_push_cap': (0, 10)}
MAX_REQUESTS_PER_DAY = 5
MAX_OPEN_PER_USER = 20
REQUEST_LIFE = 60 * 86400
SELLER_RECENT = 90 * 86400
JOIN_SCORE = 0.5


def init(server):
    with server.db() as d:
        d.executescript('''
        CREATE TABLE IF NOT EXISTS demand_groups(id TEXT PRIMARY KEY,category_id TEXT NOT NULL,label TEXT NOT NULL,
          tokens TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,hot_at INTEGER,
          status TEXT NOT NULL DEFAULT 'open');
        CREATE INDEX IF NOT EXISTS demand_groups_scan ON demand_groups(status,category_id,hot_at);
        CREATE TABLE IF NOT EXISTS demand_requests(id TEXT PRIMARY KEY,uid TEXT NOT NULL,grp TEXT NOT NULL,
          category_id TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',client_id TEXT NOT NULL DEFAULT '');
        CREATE UNIQUE INDEX IF NOT EXISTS demand_one_per_group ON demand_requests(uid,grp) WHERE status='open';
        CREATE INDEX IF NOT EXISTS demand_requests_group ON demand_requests(grp,status);
        CREATE INDEX IF NOT EXISTS demand_requests_owner ON demand_requests(uid,created);
        CREATE TABLE IF NOT EXISTS demand_seller_prefs(uid TEXT PRIMARY KEY,alerts INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS demand_notices(uid TEXT NOT NULL,grp TEXT NOT NULL,kind TEXT NOT NULL,created INTEGER NOT NULL,
          PRIMARY KEY(uid,grp,kind));
        CREATE INDEX IF NOT EXISTS demand_notices_day ON demand_notices(uid,kind,created);
        CREATE TABLE IF NOT EXISTS demand_matches(grp TEXT NOT NULL,listing TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(grp,listing));
        CREATE TABLE IF NOT EXISTS demand_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')


# ---- text handling -------------------------------------------------------------------------------
def _synonyms(d):
    try:
        return {r['term']: r['replacement'] for r in d.execute('SELECT term,replacement FROM market_synonyms')}
    except Exception:
        return {}


def _stem(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def normalise(d, text):
    from market_search import tokens, STOP
    syn = _synonyms(d)
    out = []
    for t in tokens(text):
        t = _stem(t)
        t = syn.get(t, t)
        for part in tokens(t):
            if part in STOP or len(part) < 2 and not part.isdigit():
                continue
            part = _stem(part)
            if part not in out:
                out.append(part)
    return out[:30]


def score(a, b):
    """Similarity of two token lists, 0 to 1. Overlap-based, plus a spelling tolerance for single tokens."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    # near-spelling matches count as shared tokens (e.g. "iphon" / "iphone")
    shared = len(sa & sb)
    for x in sa - sb:
        if any(len(x) > 4 and difflib.SequenceMatcher(None, x, y).ratio() >= 0.86 for y in sb - sa):
            shared += 1
    jaccard = shared / max(1, len(sa | sb))
    contain = shared / max(1, min(len(sa), len(sb)))
    return max(jaccard, 0.8 * contain if min(len(sa), len(sb)) >= 2 else 0.0)


# ---- helpers -------------------------------------------------------------------------------------
def config(d):
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        r = d.execute('SELECT value FROM market_configuration WHERE key=?', ('demand_' + k,)).fetchone()
        if r:
            try:
                v = json.loads(r['value'])
                if type(v) is int and LIMITS[k][0] <= v <= LIMITS[k][1]:
                    out[k] = v
            except Exception:
                pass
    return out


def requesters(d, grp):
    return d.execute("SELECT COUNT(DISTINCT uid) FROM demand_requests WHERE grp=? AND status='open'", (grp,)).fetchone()[0]


def group_view(d, g, uid=None):
    n = requesters(d, g['id'])
    mine = bool(uid and d.execute("SELECT 1 FROM demand_requests WHERE grp=? AND uid=? AND status='open'", (g['id'], uid)).fetchone())
    return {'id': g['id'], 'category_id': g['category_id'], 'label': g['label'], 'requesters': n,
            'hot': bool(g['hot_at']), 'created': g['created'], 'mine': mine}


def _emit(d, uid, message, target):
    from market_connections import emit
    emit(d, uid, 'demand', message, target)


def _blocked(d, a, b):
    import social
    return social.blocked(d, a, b)


# ---- notifications -------------------------------------------------------------------------------
def notify_sellers(d, g, now):
    cfg = config(d)
    cap = cfg['daily_push_cap']
    asked = {r['uid'] for r in d.execute("SELECT DISTINCT uid FROM demand_requests WHERE grp=? AND status='open'", (g['id'],))}
    rows = d.execute('''SELECT DISTINCT a.uid FROM market_ads a JOIN market_listing_meta m ON m.id=a.id
        JOIN demand_seller_prefs p ON p.uid=a.uid AND p.alerts=1
        WHERE m.category_id=? AND a.status!='removed' AND a.created>?''', (g['category_id'], now - SELLER_RECENT)).fetchall()
    sent = 0
    label = g['label']
    for r in rows:
        s = r['uid']
        if s in asked or any(_blocked(d, s, q) for q in asked):
            continue
        if d.execute("SELECT 1 FROM demand_notices WHERE uid=? AND grp=? AND kind='hot'", (s, g['id'])).fetchone():
            continue
        today = d.execute("SELECT COUNT(*) FROM demand_notices WHERE uid=? AND kind='hot' AND created>?", (s, now - 86400)).fetchone()[0]
        if today >= cap:
            continue
        d.execute("INSERT INTO demand_notices VALUES(?,?,'hot',?)", (s, g['id'], now))
        _emit(d, s, 'Hot demand: buyers are asking for "%s".' % label, {'demand': g['id']})
        sent += 1
    return sent


def match_listing(d, g, listing):
    """True when a listing's text covers enough of the group's core tokens."""
    core = json.loads(g['tokens'])
    have = normalise(d, listing['title'] + ' ' + (listing['description'] or ''))
    if not core:
        return False
    return score(core, have) >= 0.5 or len(set(core) & set(have)) >= max(1, (len(core) * 2 + 2) // 3)


def notify_buyers(d, g, listing, now):
    if d.execute('SELECT 1 FROM demand_matches WHERE grp=? AND listing=?', (g['id'], listing['id'])).fetchone():
        return 0
    d.execute('INSERT INTO demand_matches VALUES(?,?,?)', (g['id'], listing['id'], now))
    sent = 0
    for r in d.execute("SELECT DISTINCT uid FROM demand_requests WHERE grp=? AND status='open'", (g['id'],)).fetchall():
        b = r['uid']
        if b == listing['uid'] or _blocked(d, b, listing['uid']):
            continue
        _emit(d, b, 'A listing you asked for is now on Plaza: %s' % listing['title'][:60], {'listing': listing['id'], 'demand': g['id']})
        sent += 1
    return sent


def sweep(server, interval=60):
    """Background: tell buyers when matching listings appear (also drafts published later).
    Runs at most once per `interval` seconds; every notice is deduplicated by demand_matches."""
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        r = d.execute("SELECT value FROM demand_state WHERE key='last_sweep'").fetchone()
        if r and now - int(r['value']) < interval:
            return 0
        d.execute("INSERT INTO demand_state VALUES('last_sweep',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
        d.execute("UPDATE demand_requests SET status='expired' WHERE status='open' AND created<?", (now - REQUEST_LIFE,))
        d.execute("UPDATE demand_groups SET status='closed' WHERE status='open' AND NOT EXISTS(SELECT 1 FROM demand_requests r WHERE r.grp=demand_groups.id AND r.status='open')")
        groups = d.execute("SELECT * FROM demand_groups WHERE status='open'").fetchall()
        if not groups:
            return 0
        listings = d.execute('''SELECT a.id,a.uid,a.title,a.description,a.created,m.category_id FROM market_ads a
            JOIN market_listing_meta m ON m.id=a.id WHERE a.status='active' AND a.expires>? AND a.created>?
            ORDER BY a.created DESC LIMIT 300''', (now, now - 7 * 86400)).fetchall()
        sent = 0
        for lst in listings:
            for g in groups:
                if g['category_id'] == lst['category_id'] and match_listing(d, g, lst):
                    sent += notify_buyers(d, g, lst, now)
        return sent


# ---- API -----------------------------------------------------------------------------------------
def _text(value, low, high, label):
    if not isinstance(value, str):
        raise ValueError('%s must be text' % label)
    v = re.sub(r'\s+', ' ', value).strip()
    if not low <= len(v) <= high:
        raise ValueError('%s must be %d to %d characters' % (label, low, high) if low else '%s must be at most %d characters' % (label, high))
    return v


def create(server, uid, b):
    title = _text(b.get('title'), 3, 80, 'Title')
    desc = _text(b.get('description', ''), 0, 400, 'Description')
    client = _text(b.get('client_id', ''), 0, 80, 'Retry key')
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        cat = d.execute('SELECT id FROM market_categories WHERE id=? AND enabled=1', (b.get('category'),)).fetchone()
        if not cat:
            raise ValueError('Choose a category')
        if client:
            prior = d.execute('SELECT grp FROM demand_requests WHERE uid=? AND client_id=?', (uid, client)).fetchone()
            if prior:
                g = d.execute('SELECT * FROM demand_groups WHERE id=?', (prior['grp'],)).fetchone()
                return {'ok': True, 'group': group_view(d, g, uid), 'duplicate': True}
        if d.execute('SELECT COUNT(*) FROM demand_requests WHERE uid=? AND created>?', (uid, now - 86400)).fetchone()[0] >= MAX_REQUESTS_PER_DAY:
            raise ValueError('You can post %d requests a day' % MAX_REQUESTS_PER_DAY)
        if d.execute("SELECT COUNT(*) FROM demand_requests WHERE uid=? AND status='open'", (uid,)).fetchone()[0] >= MAX_OPEN_PER_USER:
            raise ValueError('Close an open request before adding another')
        toks = normalise(d, title + ' ' + desc)
        if not toks:
            raise ValueError('Describe what you are looking for')
        best, best_score = None, 0.0
        for g in d.execute("SELECT * FROM demand_groups WHERE category_id=? AND status='open'", (cat['id'],)):
            s = score(toks, json.loads(g['tokens']))
            if s > best_score:
                best, best_score = g, s
        if best is not None and best_score >= JOIN_SCORE:
            g = best
            if d.execute("SELECT 1 FROM demand_requests WHERE grp=? AND uid=? AND status='open'", (g['id'], uid)).fetchone():
                return {'ok': True, 'group': group_view(d, g, uid), 'duplicate': True}
            merged = list(dict.fromkeys(json.loads(g['tokens']) + toks))[:30]
            d.execute('UPDATE demand_groups SET tokens=?,updated=? WHERE id=?', (json.dumps(merged), now, g['id']))
        else:
            gid = uuid.uuid4().hex
            d.execute('INSERT INTO demand_groups(id,category_id,label,tokens,created,updated) VALUES(?,?,?,?,?,?)',
                      (gid, cat['id'], title, json.dumps(toks), now, now))
            g = d.execute('SELECT * FROM demand_groups WHERE id=?', (gid,)).fetchone()
        d.execute('INSERT INTO demand_requests(id,uid,grp,category_id,title,description,created,client_id) VALUES(?,?,?,?,?,?,?,?)',
                  (uuid.uuid4().hex, uid, g['id'], cat['id'], title, desc, now, client))
        cfg = config(d)
        g = d.execute('SELECT * FROM demand_groups WHERE id=?', (g['id'],)).fetchone()
        if not g['hot_at'] and requesters(d, g['id']) >= cfg['hot_threshold']:
            d.execute('UPDATE demand_groups SET hot_at=? WHERE id=?', (now, g['id']))
            g = d.execute('SELECT * FROM demand_groups WHERE id=?', (g['id'],)).fetchone()
            notify_sellers(d, g, now)
        # a listing may already exist for this request
        for lst in d.execute('''SELECT a.id,a.uid,a.title,a.description,m.category_id FROM market_ads a JOIN market_listing_meta m ON m.id=a.id
                WHERE m.category_id=? AND a.status='active' AND a.expires>? ORDER BY a.created DESC LIMIT 50''', (cat['id'], now)):
            if match_listing(d, g, lst) and not d.execute('SELECT 1 FROM demand_matches WHERE grp=? AND listing=?', (g['id'], lst['id'])).fetchone():
                d.execute('INSERT INTO demand_matches VALUES(?,?,?)', (g['id'], lst['id'], now))
                if lst['uid'] != uid and not _blocked(d, uid, lst['uid']):
                    _emit(d, uid, 'A listing you asked for is already on Plaza: %s' % lst['title'][:60], {'listing': lst['id'], 'demand': g['id']})
        return {'ok': True, 'group': group_view(d, g, uid), 'duplicate': False}


def close(server, uid, b):
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        r = d.execute("SELECT * FROM demand_requests WHERE id=? AND uid=? AND status='open'", (b.get('id'), uid)).fetchone()
        if not r:
            raise ValueError('Request not found')
        d.execute("UPDATE demand_requests SET status='closed' WHERE id=?", (r['id'],))
        if not d.execute("SELECT 1 FROM demand_requests WHERE grp=? AND status='open'", (r['grp'],)).fetchone():
            d.execute("UPDATE demand_groups SET status='closed' WHERE id=?", (r['grp'],))
        return {'ok': True}


def set_alerts(server, uid, b):
    if type(b.get('alerts')) is not bool:
        raise ValueError('Choose on or off')
    with server.db() as d:
        d.execute('INSERT INTO demand_seller_prefs VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET alerts=excluded.alerts', (uid, int(b['alerts'])))
        return {'ok': True, 'alerts': b['alerts']}


def get(server, uid, path, query):
    now = int(time.time())
    with server.db() as d:
        if path == '/market/demand_mine':
            rows = d.execute("SELECT r.id,r.title,r.description,r.created,r.status,r.category_id,r.grp FROM demand_requests r WHERE r.uid=? AND r.status='open' ORDER BY r.created DESC LIMIT 50", (uid,)).fetchall()
            out = []
            for r in rows:
                g = d.execute('SELECT * FROM demand_groups WHERE id=?', (r['grp'],)).fetchone()
                out.append(dict(r) | {'requesters': requesters(d, r['grp']), 'hot': bool(g['hot_at'])})
            pref = d.execute('SELECT alerts FROM demand_seller_prefs WHERE uid=?', (uid,)).fetchone()
            return {'requests': out, 'alerts': bool(pref and pref['alerts']), 'threshold': config(d)['hot_threshold']}
        if path == '/market/demand_hot':
            offset = max(0, int(query.get('offset', ['0'])[0] or 0))
            mine = {r['category_id'] for r in d.execute("SELECT DISTINCT m.category_id FROM market_ads a JOIN market_listing_meta m ON m.id=a.id WHERE a.uid=? AND a.status!='removed'", (uid,))}
            rows = d.execute("SELECT * FROM demand_groups WHERE status='open' AND hot_at IS NOT NULL ORDER BY hot_at DESC LIMIT 21 OFFSET ?", (offset,)).fetchall()
            items = [group_view(d, g, uid) | {'relevant': g['category_id'] in mine} for g in rows[:20]]
            items.sort(key=lambda v: (not v['relevant'], 0))
            return {'groups': items, 'more': len(rows) > 20}
        if path == '/market/demand_admin':
            from market_admin import authorize
            authorize(d, uid)
            rows = d.execute('SELECT * FROM demand_groups ORDER BY updated DESC LIMIT 100').fetchall()
            return {'config': config(d), 'limits': LIMITS, 'groups': [group_view(d, g) | {'status': g['status']} for g in rows]}
    raise ValueError('Unknown Demand request')


def admin_post(server, uid, action, b):
    from market_admin import authorize, audit
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        authorize(d, uid)
        reason = _text(b.get('reason', ''), 1, 500, 'Audit reason')
        if action == 'admin_demand_config':
            before = config(d)
            new = {}
            for k, (lo, hi) in LIMITS.items():
                v = b.get(k, before[k])
                if type(v) is not int or not lo <= v <= hi:
                    raise ValueError('Invalid Demand setting: ' + k)
                new[k] = v
            for k, v in new.items():
                d.execute('INSERT INTO market_configuration VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('demand_' + k, json.dumps(v)))
            audit(d, uid, action, 'demand', reason, before, new)
            return {'ok': True, 'config': new}
        if action == 'admin_demand_close':
            g = d.execute('SELECT * FROM demand_groups WHERE id=?', (b.get('id'),)).fetchone()
            if not g:
                raise ValueError('Demand group not found')
            d.execute("UPDATE demand_groups SET status='closed' WHERE id=?", (g['id'],))
            d.execute("UPDATE demand_requests SET status='closed' WHERE grp=? AND status='open'", (g['id'],))
            audit(d, uid, action, g['id'], reason, {'status': g['status']}, {'status': 'closed'})
            return {'ok': True}
    raise ValueError('Unknown Demand action')
