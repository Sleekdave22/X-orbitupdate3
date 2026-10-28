"""Private original assets and bounded, cancellable shared-editor jobs."""
import base64,hashlib,json,os,shutil,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
import media_processing as processing

def init(server):
 with server.db() as d:
  d.executescript('''CREATE TABLE IF NOT EXISTS media_editor_assets(id TEXT PRIMARY KEY,uid TEXT NOT NULL,destination TEXT NOT NULL,client TEXT NOT NULL,digest TEXT NOT NULL,mime TEXT NOT NULL,data BLOB NOT NULL,info TEXT NOT NULL,expires INTEGER NOT NULL,UNIQUE(uid,client));
  CREATE TABLE IF NOT EXISTS media_editor_jobs(id TEXT PRIMARY KEY,uid TEXT NOT NULL,asset TEXT NOT NULL,client TEXT NOT NULL,recipe TEXT NOT NULL,state TEXT NOT NULL,error TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,UNIQUE(uid,client));
  CREATE TABLE IF NOT EXISTS media_editor_renders(id TEXT PRIMARY KEY,uid TEXT NOT NULL,asset TEXT NOT NULL,job TEXT NOT NULL,position INTEGER NOT NULL,mime TEXT NOT NULL,data BLOB NOT NULL,poster TEXT NOT NULL,duration_ms INTEGER NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL);
  ''')
  d.execute("UPDATE media_editor_jobs SET state='failed',error='Processing was interrupted. Retry using the preserved original.' WHERE state IN ('queued','processing')")
 server.media_editor_slots=threading.BoundedSemaphore(1)

def purge(d):
 old=[r[0] for r in d.execute('SELECT id FROM media_editor_assets WHERE expires<=?',(int(time.time()),))]
 for ident in old:
  d.execute('DELETE FROM media_editor_renders WHERE asset=?',(ident,));d.execute('DELETE FROM media_editor_jobs WHERE asset=?',(ident,));d.execute('DELETE FROM media_editor_assets WHERE id=?',(ident,))

def asset(d,uid,ident):
 row=d.execute('SELECT * FROM media_editor_assets WHERE id=? AND uid=? AND expires>?',(ident,uid,int(time.time()))).fetchone()
 if not row:raise PermissionError('Editor original unavailable to this account')
 return row

def render(d,uid,ident,destination=None):
 row=d.execute('''SELECT r.*,a.destination FROM media_editor_renders r JOIN media_editor_assets a ON a.id=r.asset JOIN media_editor_jobs j ON j.id=r.job
 WHERE r.id=? AND r.uid=? AND a.expires>? AND j.state='ready' ''',(ident,uid,int(time.time()))).fetchone()
 if not row or destination and row['destination']!=destination:raise PermissionError('Edited media unavailable to this account or destination')
 return row

def get(server,uid,action,q):
 ident=q.get('id',[''])[0]
 with server.db() as d:
  if action=='media':
   row=render(d,uid,ident);return {'id':ident,'data':base64.b64encode(row['data']).decode(),'mime':row['mime'],'poster':row['poster'],'duration_ms':row['duration_ms'],'start_ms':row['start_ms'],'end_ms':row['end_ms']}
  if action=='original':
   row=asset(d,uid,ident);return {'id':ident,'info':json.loads(row['info']),'data':base64.b64encode(row['data']).decode(),'mime':row['mime'],'expires':row['expires']}
  if action=='job':
   row=d.execute('SELECT * FROM media_editor_jobs WHERE id=? AND uid=?',(ident,uid)).fetchone()
   if not row:raise PermissionError('Editor job unavailable to this account')
   asset(d,uid,row['asset'])
   parts=[dict(r) for r in d.execute('SELECT id,mime,position,poster,duration_ms,start_ms,end_ms FROM media_editor_renders WHERE job=? ORDER BY position',(ident,))] if row['state']=='ready' else []
   return {'id':ident,'state':row['state'],'error':row['error'],'parts':parts,'progress':100 if row['state']=='ready' else 10 if row['state']=='processing' else 0}
  if action=='policy':return {'vibe_seconds':60,'plaza_seconds':processing.PLAZA_VIDEO_SECONDS,'max_source_bytes':processing.MAX_BYTES,'original_retention_hours':24,'max_gallery_items':6}
 raise ValueError('Unknown editor request')

def post(server,uid,action,b):
 if action=='upload':
  dest=b.get('destination');client=b.get('client_id');mime=b.get('mime')
  if dest not in ('vibe','plaza') or not isinstance(client,str) or not 8<=len(client)<=100 or not isinstance(mime,str):raise ValueError('Invalid editor upload')
  encoded=b.get('media','')
  if not isinstance(encoded,str) or len(encoded)>28*1024*1024:raise ValueError('Choose a file up to 20 MB')
  try:
   raw=base64.b64decode(encoded,validate=True)
   if not raw or len(raw)>processing.MAX_BYTES:raise ValueError('Choose a file up to 20 MB')
   if mime.startswith('video/'):
    if not server.media_editor_slots.acquire(blocking=False):raise ValueError('The editor is busy. Your file is unchanged; retry shortly.')
    try:
     code='import json,sys;from media_processing import probe;print(json.dumps(probe(sys.stdin.buffer.read(),'+repr(mime)+')))'
     info=json.loads(subprocess.run([sys.executable,'-c',code],input=raw,capture_output=True,cwd=Path(__file__).parent,timeout=25,check=True).stdout)
    finally:server.media_editor_slots.release()
   else:info=processing.probe(raw,mime)
  except Exception as e:raise ValueError(str(e) if isinstance(e,ValueError) else 'This media could not be opened. Choose another photo or video.') from e
  digest=hashlib.sha256(raw).hexdigest()
  with server.db() as d:
   d.execute('BEGIN IMMEDIATE');purge(d)
   old=d.execute('SELECT * FROM media_editor_assets WHERE uid=? AND client=?',(uid,client)).fetchone()
   if old:
    if old['digest']!=digest or old['destination']!=dest:raise ValueError('Retry cannot replace an editor original')
    return {'id':old['id'],'info':json.loads(old['info']),'expires':old['expires']}
   if d.execute('SELECT COUNT(*) FROM media_editor_assets WHERE uid=?',(uid,)).fetchone()[0]>=30:raise ValueError('Editor storage is full. Finish existing edits or wait for temporary originals to expire.')
   ident=uuid.uuid4().hex;expires=int(time.time())+86400
   d.execute('INSERT INTO media_editor_assets VALUES(?,?,?,?,?,?,?,?,?)',(ident,uid,dest,client,digest,info['mime'],raw,json.dumps(info),expires))
   return {'id':ident,'info':info,'expires':expires}
 if action=='process':
  client=b.get('client_id');edits=b.get('edits')
  if not isinstance(client,str) or not 8<=len(client)<=100 or not isinstance(edits,dict):raise ValueError('Invalid editor process request')
  with server.db() as d:
   d.execute('BEGIN IMMEDIATE');row=asset(d,uid,b.get('asset'));processing.recipe(json.loads(row['info']),edits,row['destination']);encoded=json.dumps(edits,sort_keys=True)
   old=d.execute('SELECT * FROM media_editor_jobs WHERE uid=? AND client=?',(uid,client)).fetchone()
   if old:
    if old['asset']!=row['id'] or old['recipe']!=encoded:raise ValueError('Retry cannot replace an editor recipe')
    if old['state']!='failed':return {'id':old['id'],'state':old['state']}
   if d.execute("SELECT COUNT(*) FROM media_editor_jobs WHERE state IN ('queued','processing')").fetchone()[0]>=4:raise ValueError('The editor is busy. Your original is saved; retry shortly.')
   ident=old['id'] if old else uuid.uuid4().hex
   if old:d.execute("UPDATE media_editor_jobs SET state='queued',error='' WHERE id=?",(ident,))
   else:d.execute('INSERT INTO media_editor_jobs(id,uid,asset,client,recipe,state,created) VALUES(?,?,?,?,?,?,?)',(ident,uid,row['id'],client,encoded,'queued',int(time.time())))
  launch_worker(server,ident);return {'id':ident,'state':'queued'}
 if action=='cancel':
  with server.db() as d:
   d.execute('BEGIN IMMEDIATE');row=d.execute('SELECT id FROM media_editor_jobs WHERE id=? AND uid=?',(b.get('id'),uid)).fetchone()
   if not row:raise PermissionError('Editor job unavailable to this account')
   d.execute("UPDATE media_editor_jobs SET state='cancelled',error='' WHERE id=?",(row['id'],));d.execute('DELETE FROM media_editor_renders WHERE job=?',(row['id'],))
  return {'cancelled':True}
 raise ValueError('Unknown editor action')

def launch_worker(server,ident):threading.Thread(target=worker,args=(server,ident),daemon=True).start()

def worker(server,ident):
 with server.media_editor_slots:
  child=None;scratch=None
  try:
   with server.db() as d:
    job=d.execute('SELECT * FROM media_editor_jobs WHERE id=?',(ident,)).fetchone()
    if not job or job['state']!='queued':return
    original=asset(d,job['uid'],job['asset']);payload={'media':base64.b64encode(original['data']).decode(),'mime':original['mime'],'destination':original['destination'],'edits':json.loads(job['recipe'])}
    d.execute("UPDATE media_editor_jobs SET state='processing' WHERE id=?",(ident,))
   code="import json,sys,base64;from media_processing import process;b=json.load(sys.stdin);print(json.dumps(process(base64.b64decode(b['media']),b['mime'],b['edits'],b['destination'])))"
   scratch=tempfile.mkdtemp(prefix='orbit-editor-job-')
   request_file=Path(scratch)/'input.json';request_file.write_bytes(json.dumps(payload).encode());request_file.chmod(0o600)
   # A regular private input file avoids a partial-stdin timeout deadlock for
   # larger originals while communicate() is retried to support cancellation.
   with request_file.open('rb') as input_file:child=subprocess.Popen([sys.executable,'-c',code],stdin=input_file,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=Path(__file__).parent,env=dict(os.environ,TMPDIR=scratch,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2'))
   deadline=time.monotonic()+180
   while True:
    try:
     stdout,stderr=child.communicate(timeout=.3);break
    except subprocess.TimeoutExpired:
     with server.db() as d:state=d.execute('SELECT state FROM media_editor_jobs WHERE id=?',(ident,)).fetchone()
     if not state or state['state']=='cancelled':child.kill();child.communicate();return
     if time.monotonic()>deadline:raise ValueError('Processing took too long. Your original is saved; trim a shorter section and retry.')
   if child.returncode:raise ValueError('This edit could not be exported. Your original is saved; try a shorter section or another format.')
   parts=json.loads(stdout)['parts']
   with server.db() as d:
    d.execute('BEGIN IMMEDIATE');state=d.execute('SELECT state FROM media_editor_jobs WHERE id=?',(ident,)).fetchone()
    if not state or state['state']=='cancelled':return
    asset(d,job['uid'],job['asset'])
    for part in parts:d.execute('INSERT INTO media_editor_renders VALUES(?,?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,job['uid'],job['asset'],ident,part['position'],part['mime'],base64.b64decode(part['data']),part['poster'],part['duration_ms'],part['start_ms'],part['end_ms']))
    d.execute("UPDATE media_editor_jobs SET state='ready' WHERE id=?",(ident,))
  except Exception as e:
   if child and child.poll() is None:child.kill();child.communicate()
   with server.db() as d:d.execute("UPDATE media_editor_jobs SET state='failed',error=? WHERE id=? AND state!='cancelled'",(str(e)[:300],ident))
  finally:
   if scratch:shutil.rmtree(scratch,ignore_errors=True)
