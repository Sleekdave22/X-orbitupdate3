#!/usr/bin/env python3
"""Private LAN testing only. No E2EE. Do not expose this HTTP server publicly."""
import shutil
import argparse, base64, hashlib, hmac, json, os, re, mimetypes, secrets, sqlite3, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import sys, zlib, struct, ssl, threading
sys.path.insert(0,str(Path(__file__).parent/"vendor"))
import qrcode
from push import PushGateway
import gaming
import market
import gamebox_core
from functools import lru_cache
@lru_cache(maxsize=1024)
def account_qr(uid):
    qr=qrcode.QRCode(box_size=6,border=4);qr.add_data(uid);qr.make(fit=True);matrix=qr.get_matrix();scale=6;width=len(matrix)*scale
    raw=b"".join(b"\x00"+bytes(0 if cell else 255 for cell in row for _ in range(scale)) for row in matrix for _ in range(scale))
    def chunk(kind,data):return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    png=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,width,8,0,0,0,0))+chunk(b"IDAT",zlib.compress(raw))+chunk(b"IEND",b"")
    return base64.b64encode(png).decode()
MAX_FILE = 8 * 1024 * 1024
MAX_VIDEO = 30 * 1024 * 1024
MAX_BODY = 41 * 1024 * 1024
class ChatServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, data, reset_call_history=False):
        self.push=PushGateway(Path(data)/"firebase-service-account.json")
        self.data=Path(data); self.data.mkdir(parents=True,exist_ok=True); self.data.chmod(0o700)
        (self.data/'files').mkdir(exist_ok=True)
        code=self.data/'invite.txt'
        if not code.exists(): code.write_text(secrets.token_urlsafe(12));code.chmod(0o600)
        self.invite=code.read_text().strip()
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,sender TEXT NOT NULL,recipient TEXT NOT NULL,text TEXT NOT NULL,filename TEXT,mime TEXT,fileid TEXT,size INTEGER,time INTEGER,client_id TEXT NOT NULL,UNIQUE(sender,client_id));''')
            user_columns={r[1] for r in db.execute('PRAGMA table_info(users)')}
            for name,kind in [('password_hash',"TEXT DEFAULT ''"),('nickname','TEXT'),('profile_version','INTEGER DEFAULT 0'),('avatar',"TEXT DEFAULT ''"),('avatar_mime',"TEXT DEFAULT ''"),('last_seen','INTEGER DEFAULT 0')]:
                if name not in user_columns:db.execute(f'ALTER TABLE users ADD COLUMN {name} {kind}')
            db.execute('UPDATE users SET nickname=id WHERE nickname IS NULL')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS unique_nickname ON users(nickname COLLATE NOCASE)')
            columns={r[1] for r in db.execute('PRAGMA table_info(messages)')}
            for name,kind in [('delivered_at','INTEGER DEFAULT 0'),('read_at','INTEGER DEFAULT 0'),('view_once','INTEGER DEFAULT 0'),('opened','INTEGER DEFAULT 0'),('lease_hash','TEXT'),('lease_until','INTEGER'),('kind',"TEXT DEFAULT 'message'"),('call_id','TEXT'),('reply_to','INTEGER'),('deleted_all','INTEGER DEFAULT 0'),('protected_media','INTEGER DEFAULT 0'),('protected_device','TEXT')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE messages ADD COLUMN {name} {kind}')
                    if name=='read_at':db.execute('UPDATE messages SET read_at=?',(int(time.time()),))
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS push_devices(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_hash TEXT NOT NULL,updated INTEGER NOT NULL)');db.execute('CREATE TABLE IF NOT EXISTS contacts(owner TEXT NOT NULL,peer TEXT NOT NULL,PRIMARY KEY(owner,peer))')
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS call_history(id TEXT PRIMARY KEY,caller TEXT NOT NULL,recipient TEXT NOT NULL,started REAL NOT NULL,connected REAL,ended REAL,outcome TEXT NOT NULL)')
            if 'kind' not in {r[1] for r in db.execute('PRAGMA table_info(call_history)')}:db.execute("ALTER TABLE call_history ADD COLUMN kind TEXT DEFAULT 'audio'")
            if reset_call_history:db.execute("UPDATE call_history SET ended=?,outcome='interrupted' WHERE ended IS NULL",(time.time(),))
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS unique_message_call ON messages(call_id) WHERE call_id IS NOT NULL')
            db.execute("INSERT OR IGNORE INTO messages(sender,recipient,text,time,client_id,kind,call_id,read_at,delivered_at) SELECT caller,recipient,'',CAST(ended*1000 AS INTEGER),'call-'||id,'call',id,?,? FROM call_history WHERE ended IS NOT NULL",(int(time.time()),int(time.time())))
            db.execute('CREATE INDEX IF NOT EXISTS call_history_caller ON call_history(caller,started)');db.execute('CREATE INDEX IF NOT EXISTS call_history_recipient ON call_history(recipient,started)')
            db.execute('CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO sessions SELECT token_hash,id FROM users')
        with self.db() as db:
            db.execute('CREATE INDEX IF NOT EXISTS messages_participants_id ON messages(sender,recipient,id)')
            db.execute('CREATE INDEX IF NOT EXISTS messages_unread ON messages(recipient,read_at,sender)')
            db.execute('CREATE INDEX IF NOT EXISTS messages_undelivered ON messages(recipient,delivered_at,id)')
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS message_hidden(user_id TEXT NOT NULL,message_id INTEGER NOT NULL,PRIMARY KEY(user_id,message_id))')
            db.execute('CREATE TABLE IF NOT EXISTS chat_pins(owner TEXT NOT NULL,peer TEXT NOT NULL,PRIMARY KEY(owner,peer))')
            db.execute('CREATE TABLE IF NOT EXISTS chat_hidden(owner TEXT NOT NULL,peer TEXT NOT NULL,through_id INTEGER NOT NULL,PRIMARY KEY(owner,peer))')
        import social
        __import__("account_preferences").init(self)
        social.init(self)
        __import__("social_spaces").init(self)
        gaming.init(self)
        market.init(self)
        __import__("account_notifications").init(self)
        __import__("vibes").init(self)
        __import__('navigation_state').init(self)
        __import__('media_editor').init(self)
        __import__("wallet").init(self)
        __import__("account_invites").init(self)
        __import__("stream_lifecycle").init(self)
        __import__("match_streams").init(self)
        self.stream_relay=__import__("stream_relay").StreamRelay(self)
        self.calls={};self.call_lock=threading.RLock()
        self.login_attempts={}
        self.api_hits={};self.api_lock=threading.Lock()
        self.migrate_files()
        self.expire_views()
        super().__init__(address,Handler)
    def server_close(self):
        relay=getattr(self,'stream_relay',None)
        if relay:relay.close()
        super().server_close()
    def _gamebox_service_actions(self):
        if time.monotonic()<getattr(self,'next_gamebox_tick',0):return
        self.next_gamebox_tick=time.monotonic()+30
        try:gamebox_core.tick(self);__import__('sponsored_leagues').tick(self);gamebox_core.dispatch_notices(self);__import__("social").dispatch_notices(self)
        except Exception as error:print('Gamebox background task failed: '+type(error).__name__,flush=True)
        try:__import__("wallet").maintenance(self)
        except Exception as error:print('Test wallet maintenance failed: '+type(error).__name__,flush=True)
        try:__import__('vibes').purge(self)
        except Exception as error:print('Vibe maintenance deferred: '+type(error).__name__,flush=True)
        try:
            with self.db() as db:__import__('media_editor').purge(db)
        except Exception as error:print('Editor maintenance deferred: '+type(error).__name__,flush=True)
        try:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE');__import__('market_connections').expire(db)
        except Exception as error:print('Market reservation maintenance deferred: '+type(error).__name__,flush=True)
        try:__import__('market_demand').sweep(self)
        except Exception as error:print('Demand matching deferred: '+type(error).__name__,flush=True)
        try:__import__('market_connections').dispatch(self)
        except Exception as error:print('Market notification dispatch deferred: '+type(error).__name__,flush=True)
        try:__import__('result_reviews').dispatch(self)
        except Exception as error:print('Private result review unavailable: '+type(error).__name__,flush=True)
    def push_call(self,call,event):
        if not self.push.enabled:return
        targets=[call['recipient']] if event=='call_ringing' else [call['caller'],call['recipient']]
        expires=int(call['created']+45) if event=='call_ringing' else int(time.time()+45)
        with self.db() as db:devices=[dict(r) for r in db.execute('SELECT p.token,p.user_id FROM push_devices p JOIN sessions s ON s.token_hash=p.session_hash AND s.user_id=p.user_id WHERE p.user_id IN (%s)' % ','.join('?' for _ in targets),targets)]
        def deliver():
            for device in devices:
                try:self.push.send(device['token'],{'event':event,'call_id':call['id'],'recipient':device['user_id'],'expires_at':str(expires)})
                except Exception as error:print('Call push failed: '+type(error).__name__,flush=True)
                else:print('Call push accepted: '+event,flush=True)
        threading.Thread(target=deliver,daemon=True).start()
    def expire_calls(self):
        now=time.time()
        for key,call in list(self.calls.items()):
            if call['state']=='ended':
                if now-call['ended_at']>60:del self.calls[key]
            elif (call['state']=='ringing' and now-call['created']>45) or now-min(call['seen'].values())>35 and call['state']=='active':
                self.finish_call(call,'No answer' if call['state']=='ringing' else 'Connection lost','missed' if call['state']=='ringing' else 'disconnected')
    def finish_call(self,call,reason,outcome):
        if call['state']=='ended':return
        self.push_call(call,'call_cancelled')
        now=time.time();call.update(state='ended',reason=reason,ended_at=now,offer=None,answer=None)
        with self.db() as db:
            db.execute('UPDATE call_history SET ended=?,outcome=? WHERE id=?',(now,outcome,call['id']))
            db.execute("INSERT OR IGNORE INTO messages(sender,recipient,text,time,client_id,kind,call_id,read_at,delivered_at) VALUES(?,?,'',?,?,'call',?,?,?)",(call['caller'],call['recipient'],int(now*1000),'call-'+call['id'],call['id'],int(now) if call.get('connected') or outcome=='declined' else 0,int(now)))
    def call_event(self,row,uid):
        r=dict(row);outgoing=r['caller']==uid;missed=not outgoing and r['outcome'] in ('missed','cancelled');duration=max(0,int((r['ended'] or time.time())-r['connected'])) if r['connected'] else 0
        kind='video' if r.get('kind')=='video' else 'audio';label=('Outgoing' if outgoing else 'Incoming')+' '+kind+' call'
        if missed:label='Missed '+kind+' call'
        elif r['outcome']=='missed':label='Unanswered outgoing '+kind+' call'
        elif r['outcome']=='cancelled':label='Cancelled outgoing '+kind+' call'
        elif r['outcome']=='declined':label+=' · Declined'
        elif r['connected']:label+=f' · {duration//60:02d}:{duration%60:02d}'
        elif r['outcome'] not in ('ringing','active'):label+=' · '+r['outcome'].capitalize()
        return {'direction':'outgoing' if outgoing else 'incoming','kind':kind,'missed':missed,'label':label,'duration':duration,'outcome':r['outcome']}
    def call_view(self,call,uid):
        peer=call['recipient'] if uid==call['caller'] else call['caller']
        with self.db() as db:row=db.execute('SELECT name FROM users WHERE id=?',(peer,)).fetchone()
        return {k:call.get(k) for k in ('id','caller','recipient','state','offer','answer','reason','connected','kind')}|{'peer':peer,'peer_name':row['name'] if row else 'Contact'}
    def db(self):
        db=sqlite3.connect(self.data/'chat.sqlite',timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA secure_delete=ON');return db
    def delete_view(self, db, row):
        if row['fileid']:
            self.file_path(row['fileid'],row['filename'],row['mime']).unlink(missing_ok=True)
            (self.data/'files'/row['fileid']).unlink(missing_ok=True)
        db.execute("UPDATE messages SET text='',filename=NULL,mime=NULL,fileid=NULL,size=0,lease_hash=NULL,lease_until=NULL WHERE id=?",(row['id'],))
    def expire_views(self):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT * FROM messages WHERE view_once=1 AND opened=1 AND (lease_until IS NULL OR lease_until<=?)',(int(time.time()),)).fetchall()
            for row in rows:self.delete_view(db,row)
    def service_actions(self):
        self.expire_views()
        if time.monotonic()>=getattr(self,"next_schedule_tick",0):
            self.next_schedule_tick=time.monotonic()+1
            try:
                __import__("match_scheduling").tick(self)
                if time.monotonic()<getattr(self,"next_gamebox_tick",0):gamebox_core.dispatch_notices(self)
            except Exception as error:print("Match reminder task failed: "+type(error).__name__,flush=True)
        __import__("stream_lifecycle").expire(self)
        self._gamebox_service_actions()
    def file_path(self, fid, filename, mime):
        # Keep a readable basename, with a unique ID so duplicate names never overwrite.
        name=str(filename or 'attachment').replace('\\','/').split('/')[-1]
        name=re.sub(r'[^\w. ()-]', '_', name).strip(' .')[:150] or 'attachment'
        suffix=Path(name).suffix
        if not suffix:
            suffix={ 'image/jpeg':'.jpg', 'image/png':'.png', 'audio/wav':'.wav',
                     'text/plain':'.txt' }.get(mime) or mimetypes.guess_extension(mime or '') or ''
        stem=Path(name).stem if Path(name).suffix else name
        return self.data/'files'/f'{stem}__{fid}{suffix}'
    def allow_request(self,uid,limit=600,window=60):
        """Per-account request ceiling for signed-in POSTs (a human never gets near it)."""
        now=time.time()
        with self.api_lock:
            start,count=self.api_hits.get(uid,(now,0))
            if now-start>=window:start,count=now,0
            if count>=limit:return False
            self.api_hits[uid]=(start,count+1)
            if len(self.api_hits)>5000:
                for key in [k for k,(st,_) in self.api_hits.items() if now-st>=window]:self.api_hits.pop(key,None)
            return True
    def note_failure(self,key):
        """Count a failed credential check per client address; bounded memory."""
        now=time.time()
        with self.api_lock:
            attempts,until=self.login_attempts.get(key,(0,0))
            self.login_attempts[key]=(attempts+1 if until>now else 1,now+60)
            if len(self.login_attempts)>2000:
                for k in [k for k,(_,u) in self.login_attempts.items() if u<=now]:self.login_attempts.pop(k,None)
    def migrate_files(self):
        with self.db() as db:
            for row in db.execute('SELECT fileid,filename,mime FROM messages WHERE fileid IS NOT NULL'):
                old=self.data/'files'/row['fileid']
                target=self.file_path(row['fileid'],row['filename'],row['mime'])
                if old.is_file() and not target.exists():old.rename(target)
class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args): pass # No message bodies, credentials or IDs in access logs.
    def reply(self,status,obj):
        data=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def user(self):
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        with self.server.db() as db: row=db.execute('SELECT user_id AS id FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row: raise PermissionError('Please connect again')
        return row['id']
    def do_GET(self):
        try:
            parsed=urlparse(self.path)
            if parsed.path=='/orbit-icon.png':
                data=(Path(__file__).parent/'orbit-icon.png').read_bytes();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path.startswith("/navigation-icons/") and parsed.path.split("/")[-1] in ("vibe-icon.svg","chat-icon.svg","call-icon.svg","profile-icon.svg","orbit-market-icon.svg") and parsed.path.count("/")==2:
                data=(Path(__file__).parent/parsed.path[1:]).read_bytes();self.send_response(200);self.send_header("Content-Type","image/svg+xml");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path in ('/branding/orbit-icon-plain.png','/branding/XOrbit-app-icon-1024.png','/branding/XOrbit-logo-dark.png','/branding/XOrbit-logo-light.png','/branding/orbit-wallpaper.png','/branding/orbit-wallpaper-v2.png','/branding/settings-dark.png','/branding/settings-light.png','/branding/orbit-icon-light.png'):
                data=(Path(__file__).parent/parsed.path[1:]).read_bytes();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path in ('/orbit-reveal.js','/media-editor.js','/media-editor.css','/market-types.js','/market-chat.js','/orbit-badges.js','/orbit-embed.js','/orbit-shell.css','/orbit-shell.js','/vibe-motion.js','/vibe-cache.js','/vibe-share.js','/vibe.html','/vibe.js','/vibe.css','/activity-ui.js','/orbit-navigation.js','/navigation.css','/private-results.js','/evidence-camera.js','/camera-sources.js','/market.html','/market.js','/market.css','/calls.js','/call.html','/call-screen.js','/call-screen.css','/gaming.html','/gaming.js','/gaming.css','/studio.js','/result-room.js','/orbit-theme.js','/orbit-theme.css','/social.js','/profile-tabs.css','/social-spaces.js','/phase-b.js','/form-panels.js','/form-panels.css','/scheduling.js','/wallet.html','/wallet.js','/live-room-ui.js','/stream-relay-ui.js','/invitations.js','/join.js','/account-search.js','/sponsored-ui.js','/personalization.js','/personalization.json'):
                data=(Path(__file__).parent/parsed.path[1:]).read_bytes();self.send_response(200);self.send_header('Content-Type','application/json' if parsed.path.endswith('.json') else 'text/javascript' if parsed.path.endswith('.js') else 'text/css' if parsed.path.endswith('.css') else 'text/html');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path=='/guardianchat-ca.crt':
                data=(Path(__file__).parent.parent/'chat/src/main/res/raw/guardianchat_local_ca.crt').read_bytes();self.send_response(200);self.send_header('Content-Type','application/x-x509-ca-cert');self.send_header('Content-Disposition','attachment; filename=guardianchat-ca.crt');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path=='/join':
                data=(Path(__file__).parent/'join.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path=='/invitations/check':
                token=parse_qs(parsed.query).get('invite',[''])[0]
                try:self.reply(200,__import__('account_invites').validatepublic(self.server,token))
                except (PermissionError,ValueError):self.reply(400,{'error':'This invitation link is unavailable. Ask your friend for a new link.'})
                return
            if parsed.path in ('/roboto-0.ttf','/roboto-1.ttf'):
                data=(Path(__file__).parent/parsed.path[1:]).read_bytes()
                self.send_response(200);self.send_header('Content-Type','font/ttf');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path=='/':
                data=(Path(__file__).parent/'index.html').read_bytes()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data);return
            uid=self.user()
            if parsed.path.startswith('/market/'):
                try:self.reply(200,market.get(self.server,uid,parsed.path,parse_qs(parsed.query)))
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if parsed.path=='/preferences':
                self.reply(200,__import__('account_preferences').get(self.server,uid));return
            if parsed.path=='/messages/notification':
                try:self.reply(200,__import__('message_notifications').preview(self.server,uid,int(parse_qs(parsed.query).get('id',['0'])[0])))
                except LookupError:self.reply(404,{'error':'Message unavailable'})
                return
            if parsed.path=='/invitations/mine':
                self.reply(200,__import__('account_invites').getown(self.server,uid));return
            if parsed.path=='/gaming/live-streams':
                self.reply(200,__import__('match_streams').list_streams(self.server,uid));return
            if parsed.path.startswith('/leagues/'):
                try:self.reply(200,__import__('sponsored_leagues').get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if parsed.path.startswith('/wallet/'):
                try:self.reply(200,__import__('wallet').get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if parsed.path.startswith('/scheduling/'):
                try:self.reply(200,__import__('match_scheduling').get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if parsed.path.startswith('/identities/') or parsed.path.startswith('/rankings/'):
                module=__import__('game_identities' if parsed.path.startswith('/identities/') else 'rankings')
                try:self.reply(200,module.get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if parsed.path.startswith('/spaces/'):
                try:self.reply(200,__import__('social_spaces').get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if parsed.path.startswith('/social/'):
                import social
                try:self.reply(200,social.get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if parsed.path=='/navigation/state':
                self.reply(200,__import__('navigation_state').get(self.server,uid));return
            if parsed.path.startswith('/media-editor/'):
                self.reply(200,__import__('media_editor').get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)));return
            if parsed.path=='/vibe/media':
                q=parse_qs(parsed.query);self.reply(200,__import__('vibes').media(self.server,uid,q.get('id',[''])[0],q.get('protected',['0'])[0]=='1'));return
            if parsed.path.startswith('/vibe/'):
                self.reply(200,__import__('vibes').get(self.server,uid,parsed.path.split('/')[-1],parse_qs(parsed.query)));return
            if parsed.path=='/notifications':
                self.reply(200,__import__("account_notifications").get(self.server,uid,parse_qs(parsed.query).get("category",[None])[0]));return
            if parsed.path=='/gamebox/summary':
                self.reply(200,gamebox_core.summary(self.server,uid));return
            if parsed.path=='/gamebox/studio':
                self.reply(200,gamebox_core.studio(self.server,uid));return
            if parsed.path=='/gamebox/result-state':
                q=parse_qs(parsed.query);self.reply(200,gamebox_core.result_state(self.server,uid,q.get('room',[''])[0],int(q.get('after',['0'])[0])));return
            if parsed.path=='/gamebox/review-video':
                q=parse_qs(parsed.query)
                with self.server.db() as db:
                    match=__import__('result_reviews').match(db,q.get('room',[''])[0])
                    if uid in (match['a'],match['b']) or not gaming.admin(db,uid):raise PermissionError('Evidence is private to an independent authorised reviewer')
                    video=gamebox_core.row(db,'SELECT video,mime FROM result_review_videos WHERE kind=? AND match_id=? AND uid=?',(match['kind'],match['id'],q.get('player',[''])[0]))
                    if not video or not video['video']:self.reply(404,{'error':'Recording unavailable'});return
                self.send_response(200);self.send_header('Content-Type',video['mime']);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(video['video'])));self.end_headers();self.wfile.write(video['video']);return
            if parsed.path=='/gamebox/room':
                q=parse_qs(parsed.query)
                with self.server.db() as db:
                    m=gamebox_core.participant(db,uid,q.get('match',[''])[0]);comments=[dict(r) for r in db.execute('SELECT r.*,p.tag FROM gb_room_messages r JOIN game_profiles p ON p.uid=r.uid WHERE match=? ORDER BY id DESC LIMIT 100',(m['id'],))]
                self.reply(200,{'comments':list(reversed(comments))});return
            if parsed.path=='/gamebox/evidence':
                q=parse_qs(parsed.query)
                with self.server.db() as db:
                    mid=q.get('match',[''])[0]
                    match=gamebox_core.row(db,'SELECT a,b FROM gb_matches WHERE id=?',(mid,))
                    if not match or uid in (match['a'],match['b']) or not gaming.admin(db,uid):raise PermissionError('Evidence is private to an independent authorised reviewer')
                    evidence=gamebox_core.row(db,'SELECT image,mime FROM gb_evidence WHERE match=? AND uid=?',(mid,q.get('player',[''])[0]))
                    if not evidence or not evidence['image']:self.reply(404,{'error':'Evidence unavailable'});return
                self.send_response(200);self.send_header('Content-Type',evidence['mime']);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(evidence['image'])));self.end_headers();self.wfile.write(evidence['image']);return
            if parsed.path=='/gaming/summary':
                self.reply(200,gaming.summary(self.server,uid,parse_qs(parsed.query).get('league',[None])[0]));return
            if parsed.path=='/gaming/stream-signals':
                q=parse_qs(parsed.query);self.reply(200,gaming.stream_signals(self.server,uid,q.get('room',[''])[0],int(q.get('after',['0'])[0])));return
            if parsed.path=='/gaming/admin':
                self.reply(200,gaming.administration(self.server,uid,parse_qs(parsed.query).get('league',[None])[0]));return
            if parsed.path=='/gaming/room':
                self.reply(200,gaming.room(self.server,uid,parse_qs(parsed.query).get('fixture',[''])[0]));return
            if parsed.path=='/gaming/evidence':
                q=parse_qs(parsed.query);data,mime=gaming.evidence(self.server,uid,q.get('fixture',[''])[0],q.get('player',[''])[0]);self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if parsed.path=='/calls':
                with self.server.call_lock:
                    self.server.expire_calls();calls=[]
                    for call in self.server.calls.values():
                        if uid in (call['caller'],call['recipient']):
                            call['seen'][uid]=time.time();calls.append(self.server.call_view(call,uid))
                    self.reply(200,{'calls':calls});return
            with self.server.db() as db:
                if parsed.path=='/call-history':
                    with self.server.call_lock:self.server.expire_calls()
                    rows=db.execute('SELECT h.*,u.name,u.nickname,u.profile_version FROM call_history h JOIN users u ON u.id=CASE WHEN h.caller=? THEN h.recipient ELSE h.caller END WHERE h.caller=? OR h.recipient=? ORDER BY h.started DESC LIMIT 200',(uid,uid,uid))
                    items=[]
                    for row in rows:
                        r=dict(row);r['peer']=r['recipient'] if r['caller']==uid else r['caller'];r['direction']='outgoing' if r['caller']==uid else 'incoming';r['duration']=max(0,int((r['ended'] or time.time())-r['connected'])) if r['connected'] else 0;r.update(self.server.call_event(row,uid));items.append(r)
                    self.reply(200,{'calls':items});return
                if parsed.path=='/message-status':
                    mid=int(parse_qs(parsed.query).get('id',['0'])[0]);row=db.execute('SELECT deleted_all,protected_media,fileid FROM messages WHERE id=? AND (sender=? OR recipient=?)',(mid,uid,uid)).fetchone()
                    if not row:self.reply(404,{'error':'Message unavailable'});return
                    self.reply(200,{'deleted':bool(row['deleted_all']),'protected_transfer_pending':bool(row['protected_media'] and row['fileid'])});return
                if parsed.path=='/media':
                    peer=parse_qs(parsed.query).get('peer',[''])[0]
                    if not peer:self.reply(400,{'error':'Choose a conversation'});return
                    if not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone():self.reply(403,{'error':'Conversation unavailable'});return
                    rows=db.execute('SELECT m.*,u.name AS peer_name FROM messages m JOIN users u ON u.id=CASE WHEN m.sender=? THEN m.recipient ELSE m.sender END WHERE ((m.sender=? AND m.recipient=?) OR (m.sender=? AND m.recipient=?)) AND m.view_once=0 AND m.protected_media=0 AND m.fileid IS NOT NULL AND m.id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?) ORDER BY m.time DESC,m.id DESC',(uid,uid,peer,peer,uid,uid))
                    items=[]
                    for row in rows:
                        item=dict(row);item.pop('lease_hash',None);item.pop('lease_until',None);items.append(item)
                    self.reply(200,{'media':items});return
                if parsed.path=='/profile':
                    target=parse_qs(parsed.query).get('id',[uid])[0]
                    if target!=uid and not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,target)).fetchone():self.reply(404,{'error':'Profile unavailable'});return
                    row=db.execute('SELECT id,name,nickname,avatar,avatar_mime,profile_version,last_seen FROM users WHERE id=?',(target,)).fetchone()
                    if not row:self.reply(404,{'error':'Profile unavailable'});return
                    profile=dict(row);profile['can_admin']=gaming.admin(db,uid) if target==uid else False;profile['gaming_stats']=gaming.playerstats(db,target);profile['online']=profile['last_seen']>int(time.time())-45;
                    if target==uid:profile['has_password']=bool(db.execute('SELECT password_hash FROM users WHERE id=?',(uid,)).fetchone()['password_hash'])
                    profile['qr_png']=account_qr(target);self.reply(200,profile);return
                if parsed.path=='/users':
                    items=[dict(r) for r in db.execute('SELECT u.id,u.name,u.nickname,u.profile_version,u.last_seen,(SELECT COUNT(*) FROM messages m WHERE m.sender=u.id AND m.recipient=c.owner AND m.read_at=0) unread,(SELECT COALESCE(MAX(id),0) FROM messages m WHERE m.sender=u.id AND m.recipient=c.owner) latest FROM users u JOIN contacts c ON c.peer=u.id WHERE c.owner=? ORDER BY u.name',(uid,))]
                    for item in items:
                        item['pinned']=bool(db.execute('SELECT 1 FROM chat_pins WHERE owner=? AND peer=?',(uid,item['id'])).fetchone())
                        item['online']=item['last_seen']>int(time.time())-45
                        last=db.execute('SELECT * FROM messages WHERE ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?) ORDER BY time DESC,id DESC LIMIT 1',(uid,item['id'],item['id'],uid,uid)).fetchone()
                        item['last_activity']=last['time'] if last else 0
                        if last:
                            if last['kind']=='call':
                                history=db.execute('SELECT * FROM call_history WHERE id=?',(last['call_id'],)).fetchone();item['preview']=self.server.call_event(history,uid)['label'] if history else 'Audio call'
                            else:item['preview']='Protected media' if last['protected_media'] else 'View-once content' if last['view_once'] else (last['text'] or last['filename'] or '')[:120]
                    if parse_qs(parsed.query).get('all',['0'])[0]!='1':
                        items=[item for item in items if not db.execute('SELECT 1 FROM chat_hidden WHERE owner=? AND peer=? AND through_id>=(SELECT COALESCE(MAX(id),0) FROM messages WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?))',(uid,item['id'],uid,item['id'],item['id'],uid)).fetchone()]
                    items.sort(key=lambda item:(-int(item['pinned']),-item['last_activity'],item['name'].casefold(),item['id']))
                    self.reply(200,{'users':items});return
                if parsed.path=='/inbox':
                    self.reply(200,{'ids':[r['id'] for r in db.execute('SELECT id FROM messages WHERE recipient=? AND delivered_at=0 ORDER BY id LIMIT 500',(uid,))]});return
                if parsed.path=='/receipts':
                    peer=parse_qs(parsed.query).get('peer',[''])[0]
                    self.reply(200,{'receipts':[dict(r) for r in db.execute('SELECT id,client_id,delivered_at,read_at FROM messages WHERE sender=? AND recipient=? ORDER BY id DESC LIMIT 1000',(uid,peer))]});return
                if parsed.path=='/messages':
                    q=parse_qs(parsed.query);peer=q.get('peer',[''])[0];after=int(q.get('after',['0'])[0])
                    rows=db.execute('SELECT * FROM messages WHERE id>? AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?) ORDER BY id LIMIT 100',(after,uid,peer,peer,uid,uid))
                    items=[]
                    for r in rows:
                        item=dict(r);item.pop('lease_hash',None);item.pop('lease_until',None)
                        if item.get('reply_to'):
                            original=db.execute('SELECT m.*,u.name AS sender_name FROM messages m JOIN users u ON u.id=m.sender WHERE m.id=? AND ((m.sender=? AND m.recipient=?) OR (m.sender=? AND m.recipient=?)) AND m.id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?)',(item['reply_to'],uid,peer,peer,uid,uid)).fetchone()
                            item['reply']={'id':item['reply_to'],'name':original['sender_name'] if original else '', 'text':('Protected media' if original['protected_media'] else 'View-once content' if original['view_once'] else (original['text'] or original['filename'] or 'Message')[:140]) if original else 'Message unavailable'}
                        if item['view_once'] or item['protected_media']:item.update(text='',filename='Protected media' if item['protected_media'] else 'View-once content',mime='',fileid=None,size=0)
                        item.pop('protected_device',None)
                        if item.get('kind')=='call':
                            history=db.execute('SELECT * FROM call_history WHERE id=?',(item['call_id'],)).fetchone()
                            if history:item['call']=self.server.call_event(history,uid)
                        items.append(item)
                    unread=db.execute('SELECT COUNT(*) FROM messages WHERE sender=? AND recipient=? AND read_at=0',(peer,uid)).fetchone()[0]
                    deleted=[r['id'] for r in db.execute('SELECT id FROM messages WHERE deleted_all=1 AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))',(uid,peer,peer,uid))]
                    self.reply(200,{'messages':items,'unread_count':unread,'deleted_ids':deleted});return
                if parsed.path.startswith('/files/'):
                    fid=parsed.path.split('/')[-1]
                    row=db.execute('SELECT * FROM messages WHERE fileid=? AND (sender=? OR recipient=?) AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?)',(fid,uid,uid,uid)).fetchone()
                    if not row: self.reply(404,{'error':'File not available'});return
                    if row['view_once'] or row['protected_media']:
                        if row['protected_media'] and not hmac.compare_digest(hashlib.sha256(self.headers.get('X-Protected-Device','').encode()).hexdigest(),row['protected_device'] or ''):self.reply(403,{'error':'Protected media belongs to another device'});return
                        lease=self.headers.get('X-View-Token','')
                        valid=uid==row['recipient'] and row['lease_until'] and row['lease_until']>=time.time() and hmac.compare_digest(hashlib.sha256(lease.encode()).hexdigest(),row['lease_hash'] or '')
                        if not valid:self.reply(403,{'error':'View-once session unavailable'});return
                    p=self.server.file_path(fid,row['filename'],row['mime'])
                    if not p.is_file(): self.reply(404,{'error':'File not available'});return
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(p.stat().st_size));self.send_header('Cache-Control','no-store');self.end_headers()
                    with p.open('rb') as f:
                        while chunk:=f.read(65536):self.wfile.write(chunk)
                    return
            self.reply(404,{'error':'Not found'})
        except PermissionError as e:self.reply(401,{'error':str(e)})
        except (ValueError,KeyError):self.reply(400,{'error':'Invalid request'})
        except (BrokenPipeError,ConnectionResetError):pass
    def do_POST(self):
        try:
            self.connection.settimeout(20)
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>MAX_BODY:self.reply(413,{'error':'Videos must be 30 MB or smaller; other attachments 8 MB or smaller'});self.close_connection=True;return
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):raise ValueError()
            if self.path=='/login':
                key=self.client_address[0];attempts,until=self.server.login_attempts.get(key,(0,0))
                if attempts>=8 and until>time.time():self.reply(429,{'error':'Too many attempts. Try again in one minute.'});return
                identity=str(body.get('identity','')).strip().lstrip('@');password=str(body.get('password',''))
                with self.server.db() as db:
                    row=db.execute('SELECT * FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(identity,identity)).fetchone()
                    stored=row['password_hash'] if row else ''
                    salt=stored.split(':')[0] if stored else '0'*32
                    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),200000).hex()
                    if not stored or not hmac.compare_digest(stored,salt+':'+digest):
                        self.server.note_failure(key);raise PermissionError('Incorrect account or password')
                    token=secrets.token_urlsafe(32);db.execute('INSERT INTO sessions VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id']))
                    self.server.login_attempts.pop(key,None)
                    self.reply(200,{'id':row['id'],'name':row['name'],'nickname':row['nickname'],'token':token});return
            if self.path=='/register':
                using_link='invite_link' in body
                reg_key='register:'+self.client_address[0];attempts,until=self.server.login_attempts.get(reg_key,(0,0))
                if attempts>=8 and until>time.time():self.reply(429,{'error':'Too many attempts. Try again in one minute.'});return
                if not using_link and not hmac.compare_digest(str(body.get('invite','')),self.server.invite):self.server.note_failure(reg_key);raise PermissionError('Incorrect invitation code')
                password=body.get('password','')
                if using_link and (not isinstance(password,str) or not 10<=len(password)<=128):self.reply(400,{'error':'Use a password of 10–128 characters'});return
                name=str(body.get('name','')).strip()
                if not 1<=len(name)<=40:raise ValueError()
                uid=uuid.uuid4().hex[:12];token=secrets.token_urlsafe(32)
                nickname=str(body.get('nickname') or uid).strip().lstrip('@').lower()
                if not re.fullmatch(r'[a-z0-9_]{3,24}',nickname):self.reply(400,{'error':'Nickname must be 3–24 letters, numbers or underscores'});return
                with self.server.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    try:inviter=__import__('account_invites').authorize_registration(self.server,db,body)
                    except ValueError as e:self.reply(400,{'error':str(e)});return
                    if db.execute('SELECT 1 FROM users WHERE nickname=? COLLATE NOCASE',(nickname,)).fetchone():self.reply(409,{'error':'That nickname is already taken'});return
                    password_hash=''
                    if using_link:
                        salt=secrets.token_hex(16);password_hash=salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),200000).hex()
                    db.execute('INSERT INTO users(id,name,token_hash,nickname,password_hash) VALUES(?,?,?,?,?)',(uid,name,hashlib.sha256(token.encode()).hexdigest(),nickname,password_hash))
                    __import__('wallet').create_wallet(db,uid)
                    db.execute('INSERT INTO sessions VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid))
                    __import__('account_invites').record(db,uid,inviter)
                self.reply(201,{'id':uid,'token':token,'name':name,'nickname':nickname});return
            uid=self.user()
            if not self.server.allow_request(uid):self.reply(429,{'error':'Too many requests. Please wait a moment.'});return
            if self.path.startswith('/media-editor/'):
                try:self.reply(200,__import__('media_editor').post(self.server,uid,self.path.split('/')[-1],body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if self.path=='/navigation/calls-seen':
                try:self.reply(200,__import__('navigation_state').calls_seen(self.server,uid,body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if self.path=='/invitations/reset':
                self.reply(200,__import__('account_invites').getown(self.server,uid,rotate=True));return
            if self.path.startswith('/leagues/'):
                try:self.reply(200,__import__('sponsored_leagues').post(self.server,uid,self.path.split('/')[-1],body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if self.path.startswith('/wallet/'):
                try:self.reply(200,__import__('wallet').post(self.server,uid,self.path.split('/')[-1],body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if self.path.startswith('/scheduling/'):
                try:self.reply(200,__import__('match_scheduling').post(self.server,uid,self.path.split('/')[-1],body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if self.path.startswith('/identities/') or self.path=='/rankings/publish':
                try:
                    if self.path.startswith('/identities/'):result=__import__('game_identities').post(self.server,uid,self.path.split('/')[-1],body)
                    else:
                        with self.server.db() as db:
                            db.execute('BEGIN IMMEDIATE');result=__import__('rankings').publish(db,uid,body)
                    self.reply(200,result)
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if self.path.startswith('/spaces/'):
                try:self.reply(200,__import__('social_spaces').post(self.server,uid,self.path.split('/')[-1],body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if self.path=='/preferences':
                self.reply(200,__import__('account_preferences').save(self.server,uid,body));return
            if self.path.startswith('/social/'):
                import social
                try:self.reply(200,social.post(self.server,uid,self.path.split('/')[-1],body))
                except PermissionError as e:self.reply(403,{'error':str(e)})
                return
            if self.path in ('/messages','/messages/forward','/calls/start','/contacts'):
                import social
                target=str(body.get('recipient',body.get('peer',body.get('code','')))).lstrip('@')
                with self.server.db() as db:
                    other=db.execute('SELECT id FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(target,target)).fetchone()
                    if other and social.blocked(db,uid,other['id']):self.reply(403,{'error':'Account interaction unavailable'});return
            if self.path.startswith('/market/'):
                try:self.reply(200,market.post(self.server,uid,self.path.split('/')[-1],body))
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if self.path.startswith('/vibe/'):
                if self.path=='/vibe/reply':
                    self.reply(200,__import__('vibes').reply(self.server,uid,body));return
                self.reply(200,__import__('vibes').post(self.server,uid,self.path.split('/')[-1],body));return
            if self.path=='/notifications/seen':
                self.reply(200,__import__("account_notifications").seen(self.server,uid,body));return
            if self.path.startswith('/gamebox/'):
                self.reply(200,gamebox_core.post(self.server,uid,self.path.split('/')[-1],body));return
            if self.path in ('/gaming/match_stream_create','/gaming/stream_join','/gaming/stream_relay_offer','/gaming/stream_relay_close'):
                try:
                    if self.path.endswith('/match_stream_create'):result=__import__('match_streams').create(self.server,uid,body)
                    elif self.path.endswith('/stream_join'):result=__import__('match_streams').join(self.server,uid,str(body.get('room','')))
                    elif self.path.endswith('/stream_relay_offer'):result=self.server.stream_relay.offer(uid,body,hashlib.sha256(self.headers.get('Authorization','').removeprefix('Bearer ').encode()).hexdigest())
                    else:result=self.server.stream_relay.close_peer(uid,body)
                    self.reply(200,result)
                except PermissionError as e:self.reply(403,{'error':str(e)})
                except __import__('stream_relay').RelayUnavailable as e:self.reply(503,{'error':str(e)})
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if self.path.startswith('/gaming/'):
                try:self.reply(200,gaming.post(self.server,uid,self.path.split('/')[-1],body))
                except ValueError as e:self.reply(400,{'error':str(e)})
                return
            if self.path in ('/push/register','/push/unregister'):
                push_token=str(body.get('push_token',''))
                if not 20<=len(push_token)<=4096:raise ValueError()
                session_hash=hashlib.sha256(self.headers.get('Authorization','').removeprefix('Bearer ').encode()).hexdigest()
                with self.server.db() as db:
                    if self.path=='/push/register':db.execute('INSERT INTO push_devices(token,user_id,session_hash,updated) VALUES(?,?,?,?) ON CONFLICT(token) DO UPDATE SET user_id=excluded.user_id,session_hash=excluded.session_hash,updated=excluded.updated',(push_token,uid,session_hash,int(time.time())))
                    else:db.execute('DELETE FROM push_devices WHERE token=? AND user_id=?',(push_token,uid))
                self.reply(200,{'registered':self.path=='/push/register','push_configured':self.server.push.enabled});return
            if self.path=='/presence':
                with self.server.db() as presence_db:presence_db.execute('UPDATE users SET last_seen=? WHERE id=?',(int(time.time()),uid))
                self.reply(200,{'ok':True});return
            if self.path.startswith('/calls/'):
                with self.server.call_lock:
                    self.server.expire_calls()
                    if self.path=='/calls/start':
                        peer=str(body.get('peer',''));offer=body.get('offer',{});kind=body.get('kind','audio')
                        if kind not in ('audio','video'):raise ValueError('Invalid call type')
                        if not isinstance(offer,dict) or offer.get('type')!='offer' or not isinstance(offer.get('sdp'),str) or not 1<=len(offer['sdp'])<=65536:raise ValueError('Invalid offer')
                        with self.server.db() as db:
                            if not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone():raise PermissionError('Add this contact first')
                        if any(c['state']!='ended' and (uid in (c['caller'],c['recipient']) or peer in (c['caller'],c['recipient'])) for c in self.server.calls.values()):self.reply(409,{'error':'You or this contact are already in a call'});return
                        key=uuid.uuid4().hex;now=time.time();call={'id':key,'kind':kind,'caller':uid,'recipient':peer,'state':'ringing','offer':offer,'answer':None,'created':now,'seen':{uid:now,peer:now}};self.server.calls[key]=call;
                        with self.server.db() as db:db.execute('INSERT INTO call_history(id,caller,recipient,started,outcome,kind) VALUES(?,?,?,?,?,?)',(key,uid,peer,now,'ringing',kind))
                        self.server.push_call(call,'call_ringing')
                        self.reply(201,self.server.call_view(call,uid));return
                    call=self.server.calls.get(str(body.get('id','')))
                    if not call or uid not in (call['caller'],call['recipient']):raise PermissionError('Call unavailable')
                    if self.path=='/calls/answer':
                        answer=body.get('answer',{})
                        if uid!=call['recipient'] or call['state']!='ringing':raise PermissionError('Call cannot be answered')
                        if not isinstance(answer,dict) or answer.get('type')!='answer' or not isinstance(answer.get('sdp'),str) or not 1<=len(answer['sdp'])<=65536:raise ValueError('Invalid answer')
                        call.update(state='active',answer=answer);call['seen'][uid]=time.time()
                    elif self.path=='/calls/connected':
                        if call['state']!='active':raise PermissionError('Call not active')
                        if not call.get('connected'):
                            call['connected']=time.time()
                            with self.server.db() as db:db.execute("UPDATE call_history SET connected=?,outcome='connected' WHERE id=?",(call['connected'],call['id']))
                    elif self.path=='/calls/end':self.server.finish_call(call,'Call ended','completed' if call.get('connected') else 'declined' if uid==call['recipient'] else 'cancelled')
                    else:self.reply(404,{'error':'Not found'});return
                    self.reply(200,self.server.call_view(call,uid));return
            if self.path=='/password':
                password=str(body.get('password',''))
                if not 10<=len(password)<=128:self.reply(400,{'error':'Use a password of 10–128 characters'});return
                with self.server.db() as db:
                    old=db.execute('SELECT password_hash FROM users WHERE id=?',(uid,)).fetchone()['password_hash']
                    if old:
                        current=str(body.get('current_password',''))
                        if not 1<=len(current)<=128:raise PermissionError('Confirm your current password first')
                        old_salt=old.split(':')[0];actual=hashlib.pbkdf2_hmac('sha256',current.encode(),bytes.fromhex(old_salt),200000).hex()
                        if not hmac.compare_digest(old,old_salt+':'+actual):raise PermissionError('Current password is incorrect')
                    salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),200000).hex()
                    db.execute('UPDATE users SET password_hash=? WHERE id=?',(salt+':'+digest,uid))
                self.reply(200,{'saved':True});return
            if self.path=='/logout':
                token_hash=hashlib.sha256(self.headers.get('Authorization','').removeprefix('Bearer ').encode()).hexdigest()
                with self.server.db() as db:
                    if not db.execute('SELECT password_hash FROM users WHERE id=?',(uid,)).fetchone()['password_hash']:self.reply(409,{'error':'Set your sign-in password before logging out'});return
                    db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash,))
                    db.execute('UPDATE users SET token_hash=? WHERE id=? AND token_hash=?',(secrets.token_hex(32),uid,token_hash))
                self.reply(200,{'logged_out':True});return
            if self.path=='/profile':
                with self.server.db() as db:
                    old=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
                    name=str(body.get('name',old['name'])).strip();nickname=str(body.get('nickname',old['nickname'])).strip().lstrip('@').lower()
                    if not 1<=len(name)<=40 or not re.fullmatch(r'[a-z0-9_]{3,24}',nickname):self.reply(400,{'error':'Use a name and a 3–24 character nickname'});return
                    if db.execute('SELECT 1 FROM users WHERE nickname=? COLLATE NOCASE AND id<>?',(nickname,uid)).fetchone():self.reply(409,{'error':'That nickname is already taken'});return
                    avatar=old['avatar'];mime=old['avatar_mime']
                    if 'avatar' in body:
                        raw=base64.b64decode(body['avatar'],validate=True);mime=str(body.get('avatar_mime',''))
                        if len(raw)>256*1024 or not ((mime=='image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or (mime=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n'))):self.reply(400,{'error':'Choose a JPEG or PNG profile picture under 256 KB'});return
                        from profile_images import normalize
                        raw,mime=normalize(raw,mime)
                        avatar=base64.b64encode(raw).decode('ascii')
                    db.execute('UPDATE users SET name=?,nickname=?,avatar=?,avatar_mime=?,profile_version=profile_version+1 WHERE id=?',(name,nickname,avatar,mime,uid))
                self.reply(200,{'id':uid,'name':name,'nickname':nickname});return
            if self.path=='/delivered':
                ids=body.get('ids',[])
                if not isinstance(ids,list) or not 1<=len(ids)<=500:raise ValueError()
                with self.server.db() as db:
                    for mid in ids:db.execute('UPDATE messages SET delivered_at=? WHERE id=? AND recipient=? AND delivered_at=0',(int(time.time()),int(mid),uid))
                self.reply(200,{'delivered':True});return
            if self.path=='/read':
                with self.server.db() as db:db.execute('UPDATE messages SET read_at=?,delivered_at=CASE WHEN delivered_at=0 THEN ? ELSE delivered_at END WHERE recipient=? AND sender=? AND id<=?',(int(time.time()),int(time.time()),uid,str(body['peer']),int(body['through'])))
                self.reply(200,{'read':True});return
            if self.path=='/chats/pin':
                peer=str(body['peer'])
                with self.server.db() as db:
                    if not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone():self.reply(404,{'error':'Conversation unavailable'});return
                    if type(body.get('pinned'))!=bool:self.reply(400,{'error':'Choose pin or unpin'});return
                    if body['pinned']:db.execute('INSERT OR IGNORE INTO chat_pins VALUES(?,?)',(uid,peer))
                    else:db.execute('DELETE FROM chat_pins WHERE owner=? AND peer=?',(uid,peer))
                self.reply(200,{'pinned':body['pinned']});return
            if self.path in ('/chats/delete','/chats/clear'):
                peer=str(body['peer'])
                with self.server.db() as db:
                    if not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone():self.reply(404,{'error':'Conversation unavailable'});return
                    through=db.execute('SELECT COALESCE(MAX(id),0) FROM messages WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)',(uid,peer,peer,uid)).fetchone()[0]
                    db.execute('INSERT OR IGNORE INTO message_hidden SELECT ?,id FROM messages WHERE ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) AND id<=?',(uid,uid,peer,peer,uid,through))
                    db.execute('UPDATE messages SET read_at=?,delivered_at=? WHERE sender=? AND recipient=? AND id<=?',(int(time.time()),int(time.time()),peer,uid,through))
                    if self.path=='/chats/delete':db.execute('INSERT OR REPLACE INTO chat_hidden VALUES(?,?,?)',(uid,peer,through))
                    else:db.execute('DELETE FROM chat_hidden WHERE owner=? AND peer=?',(uid,peer))
                self.reply(200,{'deleted':True});return
            if self.path in ('/messages/forward','/messages/delete'):
                with self.server.db() as db:
                    row=db.execute('SELECT * FROM messages WHERE id=? AND (sender=? OR recipient=?) AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?)',(int(body['message_id']),uid,uid,uid)).fetchone()
                    if not row:self.reply(404,{'error':'Message unavailable'});return
                    if self.path=='/messages/delete':
                        scope=body.get('scope','me')
                        if scope not in ('me','everyone'):raise ValueError()
                        if scope=='everyone':
                            if row['sender']!=uid or row['kind']=='call':self.reply(403,{'error':'Only the sender can delete this message for everyone'});return
                            if row['fileid']:self.server.file_path(row['fileid'],row['filename'],row['mime']).unlink(missing_ok=True)
                            db.execute("UPDATE messages SET text='This message was deleted',filename=NULL,mime=NULL,fileid=NULL,size=0,view_once=0,protected_media=0,protected_device=NULL,opened=0,lease_hash=NULL,lease_until=NULL,reply_to=NULL,deleted_all=1,read_at=?,delivered_at=? WHERE id=?",(int(time.time()),int(time.time()),row['id']))
                            self.reply(200,{'deleted':True,'scope':'everyone'});return
                        db.execute('INSERT OR IGNORE INTO message_hidden VALUES(?,?)',(uid,row['id']))
                        if row['recipient']==uid:db.execute('UPDATE messages SET read_at=?,delivered_at=? WHERE id=?',(int(time.time()),int(time.time()),row['id']))
                        self.reply(200,{'deleted':True});return
                    if row['view_once'] or row['protected_media'] or row['deleted_all'] or row['kind']=='call':self.reply(403,{'error':'This content cannot be forwarded'});return
                    peer=str(body['peer']);client=str(body['client_id'])
                    if not 1<=len(client)<=80:raise ValueError()
                    if not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone():self.reply(403,{'error':'Add this contact first'});return
                    existing=db.execute('SELECT id FROM messages WHERE sender=? AND client_id=?',(uid,client)).fetchone()
                    if existing:self.reply(200,{'id':existing['id']});return
                    fid=None
                    if row['fileid']:
                        original=self.server.file_path(row['fileid'],row['filename'],row['mime'])
                        if not original.is_file():self.reply(404,{'error':'File unavailable'});return
                        fid=uuid.uuid4().hex;shutil.copyfile(original,self.server.file_path(fid,row['filename'],row['mime']))
                    try:
                        result=db.execute('INSERT INTO messages(sender,recipient,text,filename,mime,fileid,size,time,client_id,view_once) VALUES(?,?,?,?,?,?,?,?,?,0)',(uid,peer,row['text'],row['filename'],row['mime'],fid,row['size'],int(time.time()*1000),client))
                    except Exception:
                        if fid:self.server.file_path(fid,row['filename'],row['mime']).unlink(missing_ok=True)
                        raise
                    forwarded_id=result.lastrowid
                __import__('message_notifications').dispatch(self.server,forwarded_id)
                self.reply(201,{'id':forwarded_id});return
            if self.path=='/contacts':
                code=str(body.get('code','')).strip().lower().replace('-','');lookup=code.lstrip('@')
                with self.server.db() as db:
                    other=db.execute('SELECT id,name FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(code,lookup)).fetchone()
                    if not other or other['id']==uid:self.reply(400,{'error':'Enter another person’s valid contact code'});return
                    code=other['id']
                    db.execute('DELETE FROM chat_hidden WHERE owner=? AND peer=?',(uid,code))
                    db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)',(uid,code))
                    db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)',(code,uid))
                self.reply(200,{'contact':dict(other)});return
            if self.path in ('/protected/open','/protected/received'):
                device=str(body.get('device',''))
                if not 32<=len(device)<=128:raise ValueError()
                device_hash=hashlib.sha256(device.encode()).hexdigest()
                with self.server.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    row=db.execute('SELECT * FROM messages WHERE id=? AND recipient=? AND protected_media=1 AND deleted_all=0 AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?)',(int(body['message_id']),uid,uid)).fetchone()
                    if not row:self.reply(404,{'error':'Protected media unavailable'});return
                    if row['protected_device'] and not hmac.compare_digest(row['protected_device'],device_hash):self.reply(410,{'error':'This protected media is unavailable on a different device'});return
                    if self.path=='/protected/received':
                        if not row['protected_device']:self.reply(409,{'error':'Download protected media first'});return
                        if row['fileid']:self.server.file_path(row['fileid'],row['filename'],row['mime']).unlink(missing_ok=True)
                        db.execute('UPDATE messages SET text=?,fileid=NULL,size=0,lease_hash=NULL,lease_until=NULL WHERE id=?',('',row['id']))
                        self.reply(200,{'stored':True});return
                    if not row['fileid']:self.reply(410,{'error':'Protected media only exists on the original device'});return
                    lease=secrets.token_urlsafe(32)
                    db.execute('UPDATE messages SET protected_device=?,lease_hash=?,lease_until=?,read_at=?,delivered_at=? WHERE id=?',(device_hash,hashlib.sha256(lease.encode()).hexdigest(),int(time.time())+120,int(time.time()),int(time.time()),row['id']))
                    item=dict(row);item.pop('protected_device',None);item.pop('lease_hash',None);item.pop('lease_until',None);item['view_token']=lease
                self.reply(200,item);return
            if self.path=='/once/download':
                with self.server.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    row=db.execute('SELECT * FROM messages WHERE id=? AND recipient=? AND view_once=1 AND opened=0 AND deleted_all=0 AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?)',(int(body['message_id']),uid,uid)).fetchone()
                    if not row:self.reply(404,{'error':'View-once content unavailable'});return
                    lease=secrets.token_urlsafe(32)
                    db.execute('UPDATE messages SET lease_hash=?,lease_until=? WHERE id=?',(hashlib.sha256(lease.encode()).hexdigest(),int(time.time())+600,row['id']))
                    item=dict(row);item.pop('lease_hash',None);item.pop('lease_until',None);item['view_token']=lease
                self.reply(200,item);return
            if self.path in ('/open','/close'):
                with self.server.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    row=db.execute('SELECT * FROM messages WHERE id=? AND recipient=? AND view_once=1',(int(body['message_id']),uid)).fetchone()
                    if not row:self.reply(404,{'error':'Content unavailable'});return
                    if self.path=='/close':
                        if not row['opened']:self.reply(409,{'error':'Content has not been opened'});return
                        self.server.delete_view(db,row)
                        self.reply(200,{'closed':True});return
                    if row['opened']:self.reply(409,{'error':'This view-once content has already been opened'});return
                    lease=secrets.token_urlsafe(32)
                    db.execute("UPDATE messages SET delivered_at=CASE WHEN delivered_at=0 THEN CAST(strftime('%s','now') AS INTEGER) ELSE delivered_at END,read_at=CAST(strftime('%s','now') AS INTEGER),opened=1,lease_hash=?,lease_until=? WHERE id=?",(hashlib.sha256(lease.encode()).hexdigest(),int(time.time())+120,row['id']))
                    item=dict(row);item.pop('lease_hash',None);item.pop('lease_until',None);item['view_token']=lease;item['opened']=1
                self.reply(200,item);return
            if self.path!='/messages':self.reply(404,{'error':'Not found'});return
            peer=str(body['peer']);text=str(body.get('text','')).strip();client=str(body['client_id'])
            if len(text)>4000 or not 1<=len(client)<=80:raise ValueError()
            with self.server.db() as db:
                if not db.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone():self.reply(403,{'error':'Add this person using their contact code first'});return
                existing=db.execute('SELECT id FROM messages WHERE sender=? AND client_id=?',(uid,client)).fetchone()
                if existing:self.reply(200,{'id':existing['id']});return
                reply=body.get('reply_to')
                if reply is not None:
                    reply=int(reply)
                    if not db.execute('SELECT 1 FROM messages WHERE id=? AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) AND id NOT IN (SELECT message_id FROM message_hidden WHERE user_id=?)',(reply,uid,peer,peer,uid,uid)).fetchone():self.reply(400,{'error':'Reply must belong to this conversation'});return
                data=None;fid=None;filename=None;mime=None
                if body.get('data'):
                    data=base64.b64decode(body['data'],validate=True)
                    limit=MAX_VIDEO if str(body.get('mime','')).startswith('video/') else MAX_FILE
                    if len(data)>limit:self.reply(413,{'error':'Videos must be 30 MB or smaller; other attachments 8 MB or smaller'});return
                    filename=str(body.get('filename','attachment')).replace('\\','/').split('/')[-1][:150]
                    mime=str(body.get('mime','application/octet-stream'))[:100]
                    fid=uuid.uuid4().hex
                if not text and not data:raise ValueError()
                once=bool(body.get('view_once',False));protected=bool(body.get('protected_media',False))
                if protected and (once or not data):self.reply(400,{'error':'Protected media requires an attachment and cannot also be view once'});return
                if protected and not mime.startswith(('image/','video/','audio/')):self.reply(400,{'error':'Protected media supports images, videos and audio'});return
                if once and data and not (mime.startswith(('image/','video/','audio/','text/')) or mime=='application/pdf'):
                    self.reply(400,{'error':'View once supports messages, images, video, audio, text and PDF previews'});return
                if data:self.server.file_path(fid,filename,mime).write_bytes(data)
                try:
                    cur=db.execute('INSERT INTO messages(sender,recipient,text,filename,mime,fileid,size,time,client_id,view_once,reply_to,protected_media) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(uid,peer,text,filename,mime,fid,len(data) if data else 0,int(time.time()*1000),client,int(once),reply,int(protected)))
                    msgid=cur.lastrowid
                except Exception:
                    if fid:self.server.file_path(fid,filename,mime).unlink(missing_ok=True)
                    raise
            __import__('message_notifications').dispatch(self.server,msgid)
            self.reply(201,{'id':msgid})
        except PermissionError as e:self.reply(401,{'error':str(e)})
        except (ValueError,KeyError,TypeError):self.reply(400,{'error':'Invalid message or attachment'})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception:self.reply(500,{'error':'Server could not save this message'})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8765);p.add_argument('--data',default=str(Path(__file__).parent/'data'));p.add_argument('--cert');p.add_argument('--key');a=p.parse_args();
    if bool(a.cert)!=bool(a.key):p.error('Supply both --cert and --key')
    s=ChatServer((a.host,a.port),a.data,reset_call_history=bool(a.cert))
    if a.cert:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(a.cert,a.key);s.socket=context.wrap_socket(s.socket,server_side=True)
    print(f'GuardianChat LAN server on port {a.port}. Invitation code is in {s.data / "invite.txt"}. Use test content only.',flush=True)
    if a.cert:
        import lan_stun
        lan_stun.start()
    s.serve_forever()
