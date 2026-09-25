from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, random, math, sqlite3, uuid, os, urllib.parse, urllib.request, threading, time
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).parent
DB = ROOT / 'citypulse.db'
SEED = 42
def load_env_file():
 path=ROOT/'.env'
 if not path.exists(): return
 for line in path.read_text(encoding='utf-8').splitlines():
  line=line.strip()
  if not line or line.startswith('#') or '=' not in line: continue
  key,value=line.split('=',1); os.environ.setdefault(key.strip(),value.strip().strip('"\''))
load_env_file()
ZONES = [
 {'id':'mansarovar','name':'Mansarovar','lat':26.8500,'lon':75.7600},
 {'id':'vaishali','name':'Vaishali Nagar','lat':26.9124,'lon':75.7400},
 {'id':'sodala','name':'Sodala','lat':26.9020,'lon':75.7700},
 {'id':'malviya','name':'Malviya Nagar','lat':26.8540,'lon':75.8050},
 {'id':'cscheme','name':'C-Scheme','lat':26.9120,'lon':75.8000},
 {'id':'jagatpura','name':'Jagatpura','lat':26.8220,'lon':75.8700},
 {'id':'tonkroad','name':'Tonk Road','lat':26.8800,'lon':75.8100},
 {'id':'ajmerroad','name':'Ajmer Road','lat':26.9000,'lon':75.7300},
]
WEIGHTS={'traffic':.35,'air_quality':.30,'incidents':.20,'weather':.15}
DATA_MODE=os.getenv('CITYPULSE_DATA_MODE','live').lower()
TOMTOM_API_KEY=os.getenv('TOMTOM_API_KEY','').strip()
AI_PROVIDER=os.getenv('AI_PROVIDER','groq').strip().lower()
GROQ_API_KEY=os.getenv('GROQ_API_KEY','').strip()
GROQ_MODEL=os.getenv('GROQ_MODEL','openai/gpt-oss-20b').strip()
LIVE_TTL=300
LIVE_LAST_REFRESH=0
TOMTOM_TTL=1200
TOMTOM_LAST_REFRESH=0
LIVE_LOCK=threading.Lock()
AI_LOCK=threading.Lock()
AI_CACHE_KEY=None
AI_CACHE_TEXT=None
AI_CACHE_STATUS='not_configured'
AI_RETRY_AFTER=0
AI_LAST_CALL=0
AI_MIN_INTERVAL=600
LIVE_STATE={k:{'mode':'DEMO','healthy':False,'message':'Synthetic fallback'} for k in ('weather','air_quality','traffic','incidents')}

def fetch_json(url):
 req=urllib.request.Request(url,headers={'User-Agent':'CityPulse civic demo/1.0'})
 with urllib.request.urlopen(req,timeout=5) as response:
  if response.status != 200: raise RuntimeError('provider returned HTTP '+str(response.status))
  return json.loads(response.read().decode('utf-8'))

def generate_brief(context):
 """Use the configured Groq open-weight model; cache by analytics snapshot."""
 global AI_CACHE_KEY,AI_CACHE_TEXT,AI_CACHE_STATUS,AI_RETRY_AFTER,AI_LAST_CALL
 if AI_PROVIDER!='groq' or not GROQ_API_KEY:
  return ['AI summary is not configured. Add GROQ_API_KEY to the local .env file to enable it.'], 'not_configured'
 signature=json.dumps(context,sort_keys=True,separators=(',',':'))
 with AI_LOCK:
  if signature==AI_CACHE_KEY and AI_CACHE_TEXT:
   return AI_CACHE_TEXT,AI_CACHE_STATUS
  if AI_CACHE_TEXT and time.monotonic()-AI_LAST_CALL<AI_MIN_INTERVAL:
   return AI_CACHE_TEXT,'groq · cached'
  if time.monotonic()<AI_RETRY_AFTER:
   if AI_CACHE_TEXT:
    return AI_CACHE_TEXT,'groq · cached (retrying)'
   return ['AI summary is temporarily unavailable. Metrics and live feeds continue without it.'], 'temporarily_unavailable'
  payload={'model':GROQ_MODEL,'messages':[
   {'role':'system','content':'Write a concise civic briefing using only facts and numbers in the supplied JSON. Call `score` the CityPulse index and `risk_score` the risk score; keep them distinct. Never invent a value or call a score a probability. State feed modes accurately: LIVE MODEL is model-estimated, DEMO/SIMULATION is synthetic, and COMMUNITY reports are unverified. Do not describe feed records as reliable or verified unless the input explicitly says so. Do not infer causation or give emergency instructions. Return exactly 3 brief plain-text sections: Situation, Relevance, and Next 60 minutes. Every section must include a non-empty sentence after its heading. If no action is supported, explicitly say that the current feeds do not support a specific next step.'},
   {'role':'user','content':json.dumps(context,separators=(',',':'))}],
   'temperature':0.2,'max_completion_tokens':900,'reasoning_effort':'low','reasoning_format':'hidden'}
  req=urllib.request.Request('https://api.groq.com/openai/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+GROQ_API_KEY,'Content-Type':'application/json','User-Agent':'CityPulse civic prototype/1.0'},method='POST')
  try:
   AI_LAST_CALL=time.monotonic()
   with urllib.request.urlopen(req,timeout=12) as response: answer=json.loads(response.read().decode())
   content=answer['choices'][0]['message']['content'].strip()
   paragraphs=[line.strip().lstrip('-• ').strip() for line in content.splitlines() if line.strip()]
   if not paragraphs:
    finish_reason=(answer.get('choices') or [{}])[0].get('finish_reason','unknown')
    raise ValueError('empty provider response (finish_reason='+str(finish_reason)+')')
   AI_CACHE_KEY=signature; AI_CACHE_TEXT=paragraphs[:5]; AI_CACHE_STATUS='groq · '+GROQ_MODEL; AI_RETRY_AFTER=0
   return AI_CACHE_TEXT,AI_CACHE_STATUS
  except Exception as exc:
   AI_RETRY_AFTER=time.monotonic()+60
   print(f'Groq request failed: {type(exc).__name__}: {str(exc)[:240]}')
   if AI_CACHE_TEXT:
    return AI_CACHE_TEXT,'groq · cached (retrying)'
   return ['AI summary is temporarily unavailable. Metrics and live feeds continue without it.'], 'temporarily_unavailable'

def location_payload(payload):
 return payload if isinstance(payload,list) else [payload]

def save_live_observation(c,z,ts,source,metric,value,unit):
 if value is None: return
 c.execute('insert into observations(id,ts,zone_id,source,metric,value,unit,confidence,status,data_mode,source_timestamp,ingested_at) values(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),ts,z['id'],source,metric,float(value),unit,.85,'valid','live',ts,datetime.now(timezone.utc).isoformat()))

def refresh_live_feeds(force=False):
 """Fetch model-updated weather/AQI and optional TomTom road flow, caching for five minutes."""
 global LIVE_LAST_REFRESH,TOMTOM_LAST_REFRESH
 if DATA_MODE!='live': return
 now=time.monotonic()
 if not force and now-LIVE_LAST_REFRESH<LIVE_TTL: return
 if not LIVE_LOCK.acquire(blocking=False): return
 try:
  now=time.monotonic()
  if not force and now-LIVE_LAST_REFRESH<LIVE_TTL: return
  state=connect(); active=state.execute("select value from sim where key='scenario'").fetchone(); state.close()
  if active and active[0] != 'baseline': return
  c=connect()
  coords=';'.join(f"{z['lat']},{z['lon']}" for z in ZONES)
  for source,url,metrics in [
   ('weather','https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode({'latitude':','.join(str(z['lat']) for z in ZONES),'longitude':','.join(str(z['lon']) for z in ZONES),'current':'temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,weather_code','timezone':'UTC'}),{'temperature_2m':('temperature','°C'),'relative_humidity_2m':('humidity','%'),'precipitation':('rainfall','mm/h'),'rain':('rainfall','mm/h'),'wind_speed_10m':('wind_speed','km/h')}),
   ('air_quality','https://air-quality-api.open-meteo.com/v1/air-quality?'+urllib.parse.urlencode({'latitude':','.join(str(z['lat']) for z in ZONES),'longitude':','.join(str(z['lon']) for z in ZONES),'current':'us_aqi,pm2_5,pm10,nitrogen_dioxide','timezone':'UTC'}),{'us_aqi':('aqi','US AQI'),'pm2_5':('pm25','µg/m³'),'pm10':('pm10','µg/m³'),'nitrogen_dioxide':('no2','µg/m³')})]:
   try:
    response=location_payload(fetch_json(url)); n=min(len(response),len(ZONES)); count=0
    for i,z in enumerate(ZONES[:n]):
     item=response[i]; current=item.get('current',{}); ts=current.get('time')
     if not ts: continue
     stamp=datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).isoformat()
     seen=set()
     for api_metric,(metric,unit) in metrics.items():
      if metric in seen or api_metric not in current: continue
      seen.add(metric); value=current[api_metric]
      if metric=='rainfall': value=float(value)*3600/max(1,int(current.get('interval',3600)))
      save_live_observation(c,z,stamp,source,metric,value,unit); count+=1
    if count: LIVE_STATE[source]={'mode':'LIVE MODEL','healthy':True,'message':'Open-Meteo model current conditions','updated':datetime.now(timezone.utc).isoformat(),'count':count}
    else: raise RuntimeError('provider response had no current observations')
   except Exception as exc:
    old=c.execute('select count(*) from observations where source=? and data_mode="live"',(source,)).fetchone()[0]
    LIVE_STATE[source]={'mode':'CACHED' if old else 'DEMO','healthy':False,'message':str(exc)[:120]}
  if TOMTOM_API_KEY and (force or now-TOMTOM_LAST_REFRESH>=TOMTOM_TTL):
   count=0
   for z in ZONES:
    try:
     params=urllib.parse.urlencode({'point':f"{z['lat']},{z['lon']}",'unit':'KMPH','key':TOMTOM_API_KEY})
     result=fetch_json('https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?'+params)
     flow=result.get('flowSegmentData',{}); cur=flow.get('currentSpeed'); free=flow.get('freeFlowSpeed')
     if cur is None or free is None or free<=0: continue
     congestion=max(0,min(100,(1-cur/free)*100)); ts=datetime.now(timezone.utc).isoformat()
     save_live_observation(c,z,ts,'traffic','congestion_index',congestion,'index'); save_live_observation(c,z,ts,'traffic','average_speed',cur,'km/h'); count+=1
    except Exception: continue
   LIVE_STATE['traffic']={'mode':'LIVE' if count else 'DEMO','healthy':bool(count),'message':'TomTom real-time road flow' if count else 'TomTom feed unavailable'}
   TOMTOM_LAST_REFRESH=time.monotonic()
  elif not TOMTOM_API_KEY: LIVE_STATE['traffic']={'mode':'DEMO','healthy':False,'message':'Set TOMTOM_API_KEY for live traffic flow'}
  community_count=c.execute("select count(*) from incidents where status='reported'").fetchone()[0]
  LIVE_STATE['incidents']={'mode':'COMMUNITY','healthy':True,'message':f'{community_count} unverified local report(s)'} if community_count else {'mode':'DEMO','healthy':False,'message':'No live civic incident feed configured'}
  c.commit(); c.close(); LIVE_LAST_REFRESH=time.monotonic()
 finally: LIVE_LOCK.release()

def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def initialize():
 c=connect(); c.executescript('''CREATE TABLE IF NOT EXISTS zones(id TEXT PRIMARY KEY,name TEXT,lat REAL,lon REAL);
 CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,ts TEXT,zone_id TEXT,source TEXT,metric TEXT,value REAL,unit TEXT,confidence REAL,status TEXT,data_mode TEXT);
 CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,ts TEXT,zone_id TEXT,kind TEXT,severity TEXT,lat REAL,lon REAL,status TEXT,description TEXT);
 CREATE TABLE IF NOT EXISTS sim(key TEXT PRIMARY KEY,value TEXT);''')
 columns={row['name'] for row in c.execute('pragma table_info(observations)')}
 for column in ('source_timestamp','ingested_at'):
  if column not in columns: c.execute(f'alter table observations add column {column} TEXT')
 if c.execute('select count(*) from observations').fetchone()[0] == 0: seed(c)
 c.commit(); c.close()

def seed(c):
 rng=random.Random(SEED); now=datetime.now(timezone.utc).replace(second=0,microsecond=0); start=now-timedelta(hours=24); zones=ZONES
 c.executemany('insert or replace into zones values(?,?,?,?)',[(z['id'],z['name'],z['lat'],z['lon']) for z in zones])
 for i in range(289):
  t=start+timedelta(minutes=5*i); hour=t.hour; rush=12 if hour in (8,9,17,18,19) else 0
  rain=max(0, 3+2*math.sin(i/11)+rng.random()*2) if 100<=i<=118 else max(0,rng.random()*.3)
  for zi,z in enumerate(zones):
   congestion=max(8,min(92,27+rush+zi*2+rain*2.2+math.sin(i/9+zi)*8+rng.gauss(0,3)))
   aqi=max(24,min(180,62+zi*3+math.sin(i/15)*12+rng.gauss(0,5)))
   temp=27+5*math.sin(i/60)+rng.gauss(0,1); humidity=42+rain*3+rng.random()*12
   vals=[('traffic','congestion_index',congestion,'index'),('traffic','average_speed',max(8,65-congestion*.48),'km/h'),('weather','temperature',temp,'°C'),('weather','rainfall',rain,'mm/h'),('weather','humidity',humidity,'%'),('air_quality','aqi',aqi,'AQI'),('air_quality','pm25',aqi*.42,'µg/m³'),('air_quality','pm10',aqi*.68,'µg/m³')]
   for src,m,v,u in vals: c.execute('insert into observations(id,ts,zone_id,source,metric,value,unit,confidence,status,data_mode,source_timestamp,ingested_at) values(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),t.isoformat(),z['id'],src,m,round(v,1),u,.92,'valid','synthetic',t.isoformat(),datetime.now(timezone.utc).isoformat()))
 # synthetic incident events
 for j,(offset,zid,kind,sev,desc) in enumerate([(22,'sodala','road blockage','medium','Road blockage reported in demo scenario'),(61,'malviya','waterlogging','high','Waterlogging report in demo data'),(130,'mansarovar','accident','high','Traffic incident marker for demonstration'),(201,'tonkroad','public complaint','low','Public complaint in synthetic feed')]):
  t=now-timedelta(minutes=offset); z=next(z for z in zones if z['id']==zid)
  c.execute('insert into incidents values(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),t.isoformat(),zid,kind,sev,z['lat'],z['lon'],'active',desc))
 c.execute("insert or replace into sim values('scenario','baseline')")

def clamp(x): return max(0,min(100,x))
def latest(c,zone,metric):
 active=c.execute("select value from sim where key='scenario'").fetchone()
 simulated=bool(active and active[0]!='baseline')
 order='ts desc,ingested_at desc' if simulated else "case when data_mode='synthetic' then 0 else 1 end desc,ts desc,ingested_at desc"
 r=c.execute(f'select value,ts from observations where zone_id=? and metric=? order by {order} limit 1',(zone,metric)).fetchone(); return (float(r['value']),r['ts']) if r else (None,None)
def aqi_stress(x):
 bands=[(50,0,20),(100,20,40),(150,40,60),(200,60,80),(500,80,100)]; lo=0; slo=0
 for hi,shi0,shi1 in bands:
  if x<=hi: return clamp(shi0+(x-lo)/(hi-lo)*(shi1-shi0))
  lo=hi; slo=shi1
 return 100
def score_zone(c,z):
 tr,_=latest(c,z['id'],'congestion_index'); aq,_=latest(c,z['id'],'aqi'); rain,_=latest(c,z['id'],'rainfall')
 incidents=c.execute("select severity,ts from incidents where zone_id=? and status!='resolved'",(z['id'],)).fetchall()
 iload=sum({'low':1,'medium':2,'high':4,'critical':6}.get(x['severity'],1)*max(.25,1-max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(x['ts'])).total_seconds()/3600)/24) for x in incidents)
 ist=clamp(iload/12*100); ws=clamp(min(100,(rain or 0)/25*60)+min(25,max(0,(rain or 0)-8)*2))
 parts={'traffic':tr or 0,'air_quality':aqi_stress(aq or 0),'incidents':ist,'weather':ws}
 return round(sum(parts[k]*w for k,w in WEIGHTS.items())),parts

def snapshot():
 refresh_live_feeds()
 c=connect(); zones=[]; all_parts=[]
 for z in ZONES:
  score,parts=score_zone(c,z); all_parts.append((score,parts))
  signals={m:latest(c,z['id'],m)[0] for m in ['congestion_index','aqi','rainfall','temperature','average_speed']}
  active=c.execute("select count(*) from incidents where zone_id=? and status!='resolved'",(z['id'],)).fetchone()[0]
  zones.append({**z,'score':score,'status':label(score),'signals':signals,'active_incidents':active,'risk':risk(parts)})
 overall=round(sum(x[0] for x in all_parts)/len(all_parts)); parts={k:sum(x[1][k] for x in all_parts)/len(all_parts) for k in WEIGHTS}
 recent=c.execute("select * from incidents where status!='resolved' order by ts desc").fetchall()
 anomalies=[]
 for z in ZONES:
  vals=c.execute('select value,ts from observations where zone_id=? and metric="congestion_index" order by ts desc limit 13',(z['id'],)).fetchall()[::-1]
  if len(vals)>=9:
   hist=[float(v['value']) for v in vals[:-1]]; cur=float(vals[-1]['value']); mean=sum(hist)/len(hist); sd=(sum((v-mean)**2 for v in hist)/len(hist))**.5
   if sd>0 and abs((cur-mean)/sd)>=2: anomalies.append({'zone':z['name'],'metric':'Traffic congestion','value':cur,'z':round((cur-mean)/sd,1),'severity':'HIGH'})
 correlations=correlate(c)
 records=c.execute('select source,count(*) n from observations group by source').fetchall()
 history=c.execute('select ts,avg(value) value from observations where metric="congestion_index" group by ts order by ts').fetchall()
 quality=92 if len(records)>=3 else 45
 scenario=c.execute("select value from sim where key='scenario'").fetchone(); scenario=scenario[0] if scenario else 'baseline'
 incident_n=len(recent)
 c.close()
 context={'score':overall,'status':label(overall),'signal_stress':{k:round(v) for k,v in parts.items()},'zones':[{'name':z['name'],'score':z['score'],'status':z['status'],'signals':z['signals'],'risk_score':z['risk']} for z in zones],'active_incident_records':incident_n,'anomalies':anomalies,'correlations':correlations,'risk_score':risk(parts),'source_modes':{n:LIVE_STATE[n]['mode'] for n in LIVE_STATE},'simulation':scenario}
 brief_text,brief_provider=generate_brief(context)
 return {'score':overall,'status':label(overall),'parts':{k:round(v) for k,v in parts.items()},'zones':zones,'incidents':[dict(x) for x in recent],'anomalies':anomalies,'correlations':correlations,'quality':quality,'scenario':scenario,'history':[round(r['value'],1) for r in history[-289:]],'feeds':[{'name':n,'mode':'SIMULATION' if scenario!='baseline' else LIVE_STATE[n]['mode'],'healthy':True if scenario!='baseline' else LIVE_STATE[n]['healthy'],'message':'Simulation data' if scenario!='baseline' else LIVE_STATE[n]['message'],'count':sum(r['n'] for r in records if r['source']==n)} for n in ['weather','traffic','air_quality','incidents']],'updated':datetime.now().astimezone().strftime('%I:%M:%S %p'),'brief':brief_text,'brief_provider':brief_provider}
def label(s): return 'HEALTHY' if s<20 else 'STABLE' if s<40 else 'MODERATE' if s<60 else 'HIGH STRESS' if s<80 else 'CRITICAL'
def risk(p): return round(clamp(p['traffic']*.65+p['air_quality']*.2+p['incidents']*.15+8))
def correlate(c):
 pairs=[('rainfall','congestion_index','Rainfall ↔ Traffic'),('congestion_index','aqi','Traffic ↔ AQI')]; out=[]
 for a,b,name in pairs:
  rows=c.execute('select a.value x,b.value y from observations a join observations b on a.ts=b.ts and a.zone_id=b.zone_id where a.metric=? and b.metric=? order by a.ts desc limit 160',(a,b)).fetchall(); xs=[r['x'] for r in rows if r['x'] is not None and r['y'] is not None]; ys=[r['y'] for r in rows if r['x'] is not None and r['y'] is not None]
  if len(xs)<12: continue
  mx=sum(xs)/len(xs); my=sum(ys)/len(ys); den=(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**.5
  if not den: continue
  r=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den; out.append({'name':name,'r':round(r,2),'n':len(xs),'strength':'Strong' if abs(r)>=.6 else 'Moderate' if abs(r)>=.3 else 'Weak'})
 return out
def apply_scenario(name):
 global LIVE_LAST_REFRESH
 c=connect(); now=datetime.now(timezone.utc).replace(second=0,microsecond=0); rng=random.Random(SEED+int(now.timestamp()//300));
 if name=='baseline':
  c.execute('delete from observations'); c.execute("delete from incidents where status!='reported'"); seed(c); LIVE_LAST_REFRESH=0
 else:
  # Append a new aligned observation bucket for each zone. Scenario effects flow into all derived outputs.
  t=(now+timedelta(minutes=5)).isoformat()
  for zi,z in enumerate(ZONES):
   old={m:latest(c,z['id'],m)[0] or 0 for m in ['congestion_index','aqi','rainfall','temperature','humidity','average_speed','pm25','pm10']}
   rain=18+rng.random()*5 if name=='heavy_rain' else (old['rainfall']*.2)
   con=min(98,old['congestion_index']+(25 if name in ('heavy_rain','traffic_accident') else 4))
   aq=min(220,old['aqi']+(55 if name=='pollution_spike' else 4))
   speed=max(7,65-con*.48)
   values=[('traffic','congestion_index',con,'index'),('traffic','average_speed',speed,'km/h'),('weather','temperature',old['temperature'],'°C'),('weather','rainfall',rain,'mm/h'),('weather','humidity',old['humidity']+20 if name=='heavy_rain' else old['humidity'],'%'),('air_quality','aqi',aq,'AQI'),('air_quality','pm25',aq*.42,'µg/m³'),('air_quality','pm10',aq*.68,'µg/m³')]
   for src,m,v,u in values: c.execute('insert into observations(id,ts,zone_id,source,metric,value,unit,confidence,status,data_mode,source_timestamp,ingested_at) values(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),t,z['id'],src,m,round(v,1),u,.94,'valid','synthetic',t,datetime.now(timezone.utc).isoformat()))
  if name in ('traffic_accident','heavy_rain'):
   z=ZONES[2]; c.execute('insert into incidents values(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),t,z['id'],'accident' if name=='traffic_accident' else 'waterlogging','high',z['lat'],z['lon'],'active','Synthetic '+name.replace('_',' ')+' simulation event'))
 c.execute("insert or replace into sim values('scenario',?)",(name,)); c.commit(); c.close()

class Handler(BaseHTTPRequestHandler):
 def respond(self,obj,status=200):
  data=json.dumps(obj).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Content-Length',str(len(data))); self.end_headers()
  try: self.wfile.write(data)
  except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
   # Browsers may cancel an in-flight poll during refresh/navigation. The response
   # has no remaining recipient, so treat this as a normal client disconnect.
   pass
 def do_GET(self):
  if self.path.startswith('/api/dashboard'): return self.respond(snapshot())
  if self.path.startswith('/api/health'): return self.respond({'status':'ok','mode':DATA_MODE,'feeds':LIVE_STATE,'ai_provider':AI_PROVIDER,'ai_model':GROQ_MODEL,'ai_configured':bool(GROQ_API_KEY)})
  if self.path=='/' or self.path.startswith('/index'): 
   data=(ROOT/'index.html').read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
  self.respond({'error':'Not found'},404)
 def do_POST(self):
  try: body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
  except: return self.respond({'error':'Invalid JSON'},400)
  if self.path=='/api/simulation/start' and body.get('scenario') in ['heavy_rain','traffic_accident','pollution_spike','normal_city']:
   apply_scenario('baseline' if body['scenario']=='normal_city' else body['scenario']); return self.respond(snapshot())
  if self.path=='/api/simulation/reset': apply_scenario('baseline'); return self.respond(snapshot())
  if self.path=='/api/incidents':
   zone_id=str(body.get('zone_id',''))
   categories={'Road obstruction','Waterlogging','Power outage','Transit disruption','Streetlight issue','Other'}
   severities={'low','medium','high'}
   kind=str(body.get('kind','')).strip()
   severity=str(body.get('severity','medium')).lower().strip()
   note=' '.join(str(body.get('description','')).split())[:220]
   zone=next((z for z in ZONES if z['id']==zone_id),None)
   if not zone or kind not in categories or severity not in severities:
    return self.respond({'error':'Choose a valid area, issue type, and severity.'},400)
   c=connect(); c.execute('insert into incidents values(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),datetime.now(timezone.utc).isoformat(),zone_id,kind,severity,zone['lat'],zone['lon'],'reported',note or 'No additional details')); c.commit(); c.close()
   return self.respond(snapshot(),201)
  return self.respond({'error':'Unknown action'},404)
 def log_message(self,*args): pass

if __name__=='__main__':
 initialize(); port=int(os.getenv('PORT','8000')); server=ThreadingHTTPServer(('127.0.0.1',port),Handler); print(f'CityPulse running at http://127.0.0.1:{port}'); server.serve_forever()

