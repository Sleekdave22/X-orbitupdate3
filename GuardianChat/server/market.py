"""Orbit Market: shop accounts, adverts and search.

Every X ORBIT account may open one shop. Every active advert is visible to every
signed-in account. Search returns the shops (accounts) whose adverts match.
"""
import re
import time
import uuid

CATEGORIES = ['Gaming', 'Devices & accessories', 'Fashion', 'Food', 'Services', 'Digital', 'Other']
AD_LIFE = 30 * 86400          # an advert stays visible for 30 days unless renewed
MAX_ACTIVE_ADS = 20           # per shop
MAX_NEW_ADS_PER_HOUR = 5      # per shop
HOLD_AFTER_REPORTS = 3        # distinct reporters hide an advert until an administrator decides
PAGE = 20


def init(server):
    with server.db() as d:
        d.executescript('''
        CREATE TABLE IF NOT EXISTS market_accounts(
          uid TEXT PRIMARY KEY, shop_name TEXT NOT NULL, about TEXT NOT NULL DEFAULT '',
          created INTEGER NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS market_shop_name ON market_accounts(shop_name COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS market_ads(
          id TEXT PRIMARY KEY, uid TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          category TEXT NOT NULL, price TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL,
          expires INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'active');
        CREATE INDEX IF NOT EXISTS market_ads_state ON market_ads(status, expires, created);
        CREATE INDEX IF NOT EXISTS market_ads_owner ON market_ads(uid, status);
        CREATE TABLE IF NOT EXISTS market_reports(
          ad TEXT NOT NULL, uid TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL,
          PRIMARY KEY(ad, uid));
        ''')
    __import__('market_pilot').init(server)


def clean(value, low, high, label):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not low <= len(text) <= high:
        raise ValueError('%s must be %d to %d characters' % (label, low, high) if low else '%s must be at most %d characters' % (label, high))
    return text


def is_admin(db, uid):
    import gaming
    return gaming.admin(db, uid)


def account_of(db, uid):
    return db.execute('SELECT * FROM market_accounts WHERE uid=?', (uid,)).fetchone()


def ad_view(r, me):
    return {'id': r['id'], 'title': r['title'], 'description': r['description'], 'category': r['category'],
            'price': r['price'], 'created': r['created'], 'expires': r['expires'], 'status': r['status'],
            'uid': r['uid'], 'shop_name': r['shop_name'], 'nickname': r['nickname'] or '', 'owner_name': r['owner_name'] or '', 'mine': r['uid'] == me}


BASE = '''SELECT a.*, m.shop_name, u.nickname, u.name AS owner_name FROM market_ads a
          JOIN market_accounts m ON m.uid=a.uid JOIN users u ON u.id=a.uid '''
LIVE = "a.status='active' AND a.expires>? AND NOT EXISTS(SELECT 1 FROM market_seller_meta s WHERE s.uid=a.uid AND s.restricted=1)"


def like(term):
    return '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def search_clause(q):
    terms = [t for t in re.split(r'\s+', q.lower().strip()) if t][:6]
    sql, args = '', []
    for t in terms:
        sql += (" AND (lower(a.title) LIKE ? ESCAPE '\\' OR lower(a.description) LIKE ? ESCAPE '\\'"
                " OR lower(a.category) LIKE ? ESCAPE '\\' OR lower(m.shop_name) LIKE ? ESCAPE '\\'"
                " OR lower(u.nickname) LIKE ? ESCAPE '\\')")
        args += [like(t)] * 5
    return sql, args


def get(server, uid, path, query):
    if path=='/market/admin':return __import__('market_admin').get(server,uid)
    if path in ('/market/demand_mine','/market/demand_hot','/market/demand_admin'):
        return __import__('market_demand').get(server,uid,path,query)
    if path in ('/market/demo_wallet','/market/demo_orders','/market/demo_order'):
        return __import__('market_demo').get(server,uid,path,query)
    if path in ('/market/saved','/market/offers','/market/offer','/market/chat_context','/market/activity','/market/activity_item'):
        return __import__('market_connections').get(server,uid,path,query)
    if path in ('/market/catalog','/market/listings','/market/listing','/market/image','/market/store','/market/mine'):
        return __import__('market_pilot').get(server,uid,path,query)
    now = int(time.time())
    with server.db() as d:
        if path == '/market/summary':
            mine = account_of(d, uid)
            out = {'categories': CATEGORIES, 'limits': {'max_active_ads': MAX_ACTIVE_ADS, 'ad_days': AD_LIFE // 86400},
                   'account': None, 'ads': [], 'is_admin': is_admin(d, uid), 'held': []}
            if mine:
                out['account'] = {'shop_name': mine['shop_name'], 'about': mine['about']}
                rows = d.execute(BASE + "WHERE a.uid=? AND a.status!='removed' ORDER BY a.created DESC", (uid,)).fetchall()
                out['ads'] = [ad_view(r, uid) for r in rows]
            if out['is_admin']:
                rows = d.execute(BASE + "WHERE a.status='held' ORDER BY a.created DESC LIMIT 50").fetchall()
                out['held'] = [ad_view(r, uid) for r in rows]
            return out
        if path == '/market/ads':
            q = (query.get('q', [''])[0] or '')[:80]
            category = query.get('category', [''])[0]
            offset = max(0, int(query.get('offset', ['0'])[0] or 0))
            clause, args = search_clause(q)
            where = 'WHERE ' + LIVE + clause
            params = [now] + args
            if category in CATEGORIES:
                where += ' AND a.category=?'
                params.append(category)
            if not q.strip():
                rows = d.execute(BASE + where + ' ORDER BY a.created DESC LIMIT ? OFFSET ?', params + [PAGE + 1, offset]).fetchall()
                return {'mode': 'ads', 'ads': [ad_view(r, uid) for r in rows[:PAGE]], 'more': len(rows) > PAGE}
            rows = d.execute(BASE + where + ' ORDER BY a.created DESC LIMIT 300', params).fetchall()
            shops = {}
            for r in rows:
                s = shops.setdefault(r['uid'], {'uid': r['uid'], 'shop_name': r['shop_name'], 'nickname': r['nickname'] or '', 'owner_name': r['owner_name'] or '',
                                                 'matches': 0, 'latest': 0, 'ads': []})
                s['matches'] += 1
                s['latest'] = max(s['latest'], r['created'])
                if len(s['ads']) < 5:
                    s['ads'].append(ad_view(r, uid))
            ordered = sorted(shops.values(), key=lambda s: (-s['matches'], -s['latest']))
            for s in ordered:
                s['about'] = d.execute('SELECT about FROM market_accounts WHERE uid=?', (s['uid'],)).fetchone()['about']
            return {'mode': 'accounts', 'accounts': ordered[offset:offset + PAGE], 'more': len(ordered) > offset + PAGE,
                    'total_ads': len(rows)}
        if path == '/market/account':
            target = query.get('id', [''])[0]
            shop = account_of(d, target)
            if not shop:
                raise ValueError('Shop not found')
            nick = d.execute('SELECT nickname, name FROM users WHERE id=?', (target,)).fetchone()
            rows = d.execute(BASE + 'WHERE a.uid=? AND ' + LIVE + ' ORDER BY a.created DESC', (target, now)).fetchall()
            return {'uid': target, 'shop_name': shop['shop_name'], 'about': shop['about'], 'nickname': (nick['nickname'] or '') if nick else '', 'owner_name': (nick['name'] or '') if nick else '',
                    'ads': [ad_view(r, uid) for r in rows]}
    raise ValueError('Unknown market request')


def post(server, uid, action, b):
    if action in ('demand_create','demand_close','demand_alerts'):
        m=__import__('market_demand');return {'demand_create':m.create,'demand_close':m.close,'demand_alerts':m.set_alerts}[action](server,uid,b)
    if action in ('admin_demand_config','admin_demand_close'):
        return __import__('market_demand').admin_post(server,uid,action,b)
    if action in ('admin_config','admin_category','admin_seller','admin_feature','admin_synonym'):
        return __import__('market_admin').post(server,uid,action,b)
    if action in ('demo_deposit','demo_withdraw','demo_order_create','demo_order_action'):
        return __import__('market_demo').post(server,uid,action,b)
    if action in ('save_item','offer_create','offer_action','inquiry','activity_seen'):
        return __import__('market_connections').post(server,uid,action,b)
    if action in ('save_listing','listing_state','report_seller','search_preferences'):
        return __import__('market_pilot').post(server,uid,action,b)
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        policy=__import__('market_admin').settings(d)
        mine = account_of(d, uid)
        if action == 'register':
            if mine:
                raise ValueError('You already have a shop')
            name = clean(b.get('shop_name'), 3, 40, 'Shop name')
            about = clean(b.get('about'), 0, 300, 'About')
            try:
                d.execute('INSERT INTO market_accounts VALUES(?,?,?,?)', (uid, name, about, now))
            except Exception:
                raise ValueError('That shop name is already taken')
            return {'ok': True}
        if action == 'admin_restore' or action == 'admin_remove':
            if not is_admin(d, uid):
                raise ValueError('Only the administrator may do that')
            ad = d.execute('SELECT id,uid FROM market_ads WHERE id=?', (b.get('id'),)).fetchone()
            if not ad:
                raise ValueError('Advert not found')
            if d.execute('SELECT 1 FROM market_reservations WHERE listing=?',(ad['id'],)).fetchone():raise ValueError('Resolve the active reservation or demo order before removing this listing')
            d.execute('UPDATE market_ads SET status=? WHERE id=?', ('active' if action == 'admin_restore' else 'removed', ad['id']))
            if action=='admin_restore':d.execute('UPDATE market_ads SET expires=max(expires,?) WHERE id=?',(now+policy['life_days']*86400,ad['id']))
            __import__('market_admin').audit(d,uid,action,ad['id'],str(b.get('reason') or 'Legacy Market moderation'),None,{'status':'active' if action=='admin_restore' else 'removed'})
            d.execute('UPDATE market_listing_meta SET state=?,revision=revision+1,updated=? WHERE id=?',('ACTIVE' if action=='admin_restore' else 'REMOVED',now,ad['id']))
            __import__('account_notifications').add(d,ad['uid'],'market','shop','Your advert was '+('restored' if action=='admin_restore' else 'removed after review')+'.',{'ad':ad['id']})
            if action == 'admin_restore':
                d.execute('DELETE FROM market_reports WHERE ad=?', (ad['id'],))
            return {'ok': True}
        if action == 'report':
            ad = d.execute("SELECT * FROM market_ads WHERE id=? AND status='active'", (b.get('id'),)).fetchone()
            if not ad:
                raise ValueError('Advert not found')
            if ad['uid'] == uid:
                raise ValueError('You cannot report your own advert')
            d.execute('INSERT OR IGNORE INTO market_reports VALUES(?,?,?,?)', (ad['id'], uid, clean(b.get('reason'), 0, 200, 'Reason'), now))
            if d.execute('SELECT COUNT(*) FROM market_reports WHERE ad=?', (ad['id'],)).fetchone()[0] >= HOLD_AFTER_REPORTS:
                d.execute("UPDATE market_ads SET status='held' WHERE id=?", (ad['id'],))
                d.execute("UPDATE market_listing_meta SET state='PENDING_REVIEW',revision=revision+1,updated=? WHERE id=?",(now,ad['id']))
                __import__('account_notifications').add(d,ad['uid'],'market','shop','Your advert is held for review.',{'ad':ad['id']})
            return {'ok': True}
        if not mine:
            raise ValueError('Open your shop first')
        if action == 'update_shop':
            name = clean(b.get('shop_name'), 3, 40, 'Shop name')
            try:
                d.execute('UPDATE market_accounts SET shop_name=?, about=? WHERE uid=?', (name, clean(b.get('about'), 0, 300, 'About'), uid))
            except Exception:
                raise ValueError('That shop name is already taken')
            return {'ok': True}
        if action == 'post_ad':
            title = clean(b.get('title'), 3, 80, 'Title')
            description = clean(b.get('description'), 0, 600, 'Description')
            price = clean(b.get('price'), 0, 30, 'Price')
            category = b.get('category')
            if category not in CATEGORIES:
                raise ValueError('Choose a category')
            live = d.execute("SELECT COUNT(*) FROM market_ads WHERE uid=? AND status IN ('active','held') AND expires>?", (uid, now)).fetchone()[0]
            if live >= policy['max_listings']:
                raise ValueError('You can have %d live adverts. Remove one first.' % MAX_ACTIVE_ADS)
            if d.execute('SELECT COUNT(*) FROM market_ads WHERE uid=? AND created>?', (uid, now - 3600)).fetchone()[0] >= policy['max_new_hour']:
                raise ValueError('Please slow down: %d new adverts per hour' % MAX_NEW_ADS_PER_HOUR)
            ad_id = uuid.uuid4().hex
            d.execute('INSERT INTO market_ads(id,uid,title,description,category,price,created,expires) VALUES(?,?,?,?,?,?,?,?)',
                      (ad_id, uid, title, description, category, price, now, now + policy['life_days']*86400))
            if policy['review_required'] or any(re.search(r'\b'+re.escape(t)+r'\b',title+' '+description,re.I) for t in policy['prohibited_terms']):d.execute("UPDATE market_ads SET status='held' WHERE id=?",(ad_id,))
            return {'ok': True, 'id': ad_id}
        if action in ('remove_ad', 'renew_ad'):
            ad = d.execute('SELECT * FROM market_ads WHERE id=? AND uid=?', (b.get('id'), uid)).fetchone()
            if not ad or ad['status'] == 'removed':
                raise ValueError('Advert not found')
            if d.execute('SELECT 1 FROM market_reservations WHERE listing=?',(ad['id'],)).fetchone():raise ValueError('This listing has an active reservation')
            if action == 'remove_ad':
                d.execute("UPDATE market_ads SET status='removed' WHERE id=?", (ad['id'],))
                d.execute("UPDATE market_listing_meta SET state='REMOVED',revision=revision+1,updated=? WHERE id=?",(now,ad['id']))
            else:
                if ad['status'] == 'held':
                    raise ValueError('This advert is waiting for an administrator')
                d.execute('UPDATE market_ads SET expires=? WHERE id=?', (now + AD_LIFE, ad['id']))
            return {'ok': True}
    raise ValueError('Unknown market action')
