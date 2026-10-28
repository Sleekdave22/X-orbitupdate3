"""Optional coarse advert coordinates and honest distance estimates. No geocoding."""
import math

def coordinates(latitude,longitude):
 if latitude in (None,'') and longitude in (None,''):return None,None
 try:
  if isinstance(latitude,bool) or isinstance(longitude,bool):raise ValueError()
  lat,lon=float(latitude),float(longitude)
  if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError()
  return round(lat,2),round(lon,2)
 except (ValueError,TypeError):raise ValueError('Supply valid approximate latitude and longitude together')

def distance(a,b,c,d):
 a,b,c,d=map(math.radians,(a,b,c,d));h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
 return round(6371*2*math.asin(min(1,math.sqrt(h))),1)

def refine(items,q,mode):
 arg=lambda n,default='':q.get(n,[default])[0]
 lat,lon=coordinates(arg('latitude'),arg('longitude'))
 if mode=='distance' and lat is None:raise ValueError('Choose your approximate search location first')
 radius=None
 if mode=='distance':
  try:
   radius=float(arg('radius_km','50'))
   if not math.isfinite(radius) or not 1<=radius<=20000:raise ValueError()
  except ValueError:raise ValueError('Choose a distance between 1 and 20,000 km')
 result=[]
 for original in items:
  v=dict(original);v['distance_km']=None
  if lat is not None and v.get('latitude') is not None and v.get('longitude') is not None:v['distance_km']=distance(lat,lon,v['latitude'],v['longitude'])
  if radius is None or v['distance_km'] is not None and v['distance_km']<=radius:result.append(v)
 return result
