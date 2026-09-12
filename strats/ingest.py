"""Acquire immutable source snapshots; normalize without filling missing observations."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, gzip, hashlib, json, re, urllib.request
import xml.etree.ElementTree as ET
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
FIELDS = {'BC_1MONTH':1/12,'BC_2MONTH':2/12,'BC_3MONTH':.25,'BC_4MONTH':1/3,
          'BC_6MONTH':.5,'BC_1YEAR':1.,'BC_2YEAR':2.,'BC_3YEAR':3.,'BC_5YEAR':5.,
          'BC_7YEAR':7.,'BC_10YEAR':10.,'BC_20YEAR':20.,'BC_30YEAR':30.}
URLS = {f'treasury-{y}.xml':f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value={y}' for y in (2024,2025,2026)}
URLS.update({'options.json':'https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json',
 'securities.json':'https://www.treasurydirect.gov/TA_WS/securities/search?format=json&type=Note&auctionDate=2025-08-01,2025-08-31'})

def digest(b): return hashlib.sha256(b).hexdigest()

def acquire(source_dir=None):
    """A refresh is explicit; a failed download raises, never substitutes invented data."""
    records=[]
    for name,url in URLS.items():
        if source_dir:
            source=Path(source_dir)/name
            b=source.read_bytes()
            # Files in this task were downloaded immediately before initial ingestion.
            retrieved=datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat()
        else:
            with urllib.request.urlopen(url, timeout=60) as r: b=r.read()
            retrieved=datetime.now(timezone.utc).isoformat()
        if name.endswith('.json'): json.loads(b)
        else: ET.fromstring(b)
        sha=digest(b); rel=f'raw/{name[:-4] if name.endswith(".xml") else name[:-5]}-{sha[:12]}{Path(name).suffix}.gz'
        (DATA/rel).parent.mkdir(parents=True,exist_ok=True)
        (DATA/rel).write_bytes(gzip.compress(b,mtime=0))
        records.append(dict(name=name,url=url,path=rel,sha256_uncompressed=sha,
                            bytes_uncompressed=len(b),retrieved_at_utc=retrieved))
    manifest={'data_mode':'observed_market_and_official_data','sources':records,
              'policy':'No fabricated prices, yields, quotes, security terms, or historical observations.'}
    (DATA/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    normalize()

def raw(name):
    manifest=json.loads((DATA/'manifest.json').read_text())
    rec=next(r for r in manifest['sources'] if r['name']==name)
    b=gzip.decompress((DATA/rec['path']).read_bytes())
    if digest(b)!=rec['sha256_uncompressed']: raise ValueError(f'Hash mismatch: {name}')
    return b

def normalize():
    rows=[]
    for year in (2024,2025,2026):
        for prop in ET.fromstring(raw(f'treasury-{year}.xml')).iter():
            if not prop.tag.endswith('}properties'): continue
            r={x.tag.split('}')[-1]:x.text for x in prop}
            for key,tenor in FIELDS.items():
                if r.get(key): rows.append({'date':r['NEW_DATE'][:10],'tenor':tenor,'par_yield':float(r[key])/100,'source_field':key})
    rates=pd.DataFrame(rows).sort_values(['date','tenor'])
    if rates.duplicated(['date','tenor']).any(): raise ValueError('Duplicate rates')
    rates.to_csv(DATA/'normalized/treasury.csv',index=False)
    securities=json.loads(raw('securities.json'))
    keys=['cusip','securityTerm','issueDate','datedDate','maturityDate','interestRate','firstInterestPaymentDate','interestPaymentFrequency','auctionDate','pricePer100','highYield']
    pd.DataFrame([{k:r[k] for k in keys} for r in securities]).to_csv(DATA/'normalized/securities.csv',index=False)
    obj=json.loads(raw('options.json')); quotes=[]
    asof=pd.Timestamp(obj['timestamp'])
    for row in obj['data']['options']:
        m=re.fullmatch(r'(SPXW|SPX)(\d{6})([CP])(\d{8})', row['option'])
        if not m: continue
        root,expiry,kind,strike=m.groups(); expiration=pd.to_datetime(expiry,format='%y%m%d')
        days=(expiration.normalize()-asof.normalize()).days
        # Keep the entire SPXW 30-120 day sub-universe, including rejected quotes.
        if root=='SPXW' and 30<=days<=120:
            quotes.append(dict(row,root=root,expiry=str(expiration.date()),kind=kind,strike=int(strike)/1000,
                               snapshot_timestamp=obj['timestamp'],source_row_type='observed_quote'))
    df=pd.DataFrame(quotes)
    if df.empty or df.option.duplicated().any(): raise ValueError('Invalid option universe')
    df.to_csv(DATA/'normalized/options.csv',index=False)
    meta={k:v for k,v in obj.items() if k!='data'}
    meta['underlying']={k:v for k,v in obj['data'].items() if k!='options'}
    meta['timestamp_convention']='Cboe timestamp has no offset; analysis explicitly assumes America/New_York.'
    (DATA/'normalized/options_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    m=json.loads((DATA/'manifest.json').read_text())
    m['normalized_files']={p.name:digest(p.read_bytes()) for p in sorted((DATA/'normalized').iterdir()) if p.is_file()}
    m['counts']={'rate_observations':len(rates),'curve_dates':rates.date.nunique(),'security_records':len(securities),'options_in_scope':len(df)}
    (DATA/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps(m['counts']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');p.add_argument('--source-dir');a=p.parse_args()
    if a.download or a.source_dir: acquire(a.source_dir)
    else: normalize()
