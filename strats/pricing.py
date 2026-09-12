"""European forward-option valuation. Prices are index points, not dollars."""
import math
import numpy as np
from scipy.special import ndtr
from scipy.optimize import brentq


def black76(forward, strike, t, rate, vol, kind='C'):
    if kind not in ('C','P') or forward<=0 or strike<=0 or t<0 or vol<0:
        raise ValueError('Invalid option inputs')
    sign=1 if kind=='C' else -1
    discount=math.exp(-rate*t)
    if t==0 or vol==0: return discount*max(sign*(forward-strike),0.)
    s=vol*math.sqrt(t);d1=math.log(forward/strike)/s+s/2;d2=d1-s
    return discount*sign*(forward*ndtr(sign*d1)-strike*ndtr(sign*d2))


def implied_vol(price, forward, strike, t, rate, kind='C'):
    if t<=0: raise ValueError('Expired option')
    discount=math.exp(-rate*t)
    low=black76(forward,strike,t,rate,0,kind)
    high=discount*(forward if kind=='C' else strike)
    if not low<price<high: raise ValueError('Price outside strict European bounds')
    if black76(forward,strike,t,rate,5.,kind)<price: raise ValueError('IV exceeds solver bracket')
    return brentq(lambda v:black76(forward,strike,t,rate,v,kind)-price,1e-9,5.,xtol=1e-12)


def greeks(forward,strike,t,rate,vol,kind='C'):
    """F held independent of r. Vega per +1 vol point, theta per day, rho per +1 bp."""
    if min(t,vol)<=0: raise ValueError('Greeks need positive time and volatility')
    discount=math.exp(-rate*t);s=vol*math.sqrt(t)
    d1=math.log(forward/strike)/s+s/2
    density=math.exp(-d1*d1/2)/math.sqrt(2*math.pi)
    price=black76(forward,strike,t,rate,vol,kind)
    return {'forward_delta':discount*(ndtr(d1)-(kind=='P')),
            'forward_gamma':discount*density/(forward*s),
            'vega_per_vol_point':discount*forward*density*math.sqrt(t)*.01,
            'theta_per_day':(rate*price-discount*forward*density*vol/(2*math.sqrt(t)))/365,
            'rho_per_bp_fixed_forward':-t*price*.0001}


def crr(forward,strike,t,rate,vol,kind='C',steps=400):
    """CRR tree on the forward, a martingale under deterministic rates; European exercise."""
    if steps<1 or int(steps)!=steps or min(forward,strike,t,vol)<=0: raise ValueError('Invalid tree inputs')
    if kind not in ('C','P'): raise ValueError('Invalid kind')
    dt=t/steps;u=math.exp(vol*math.sqrt(dt));d=1/u;p=(1-d)/(u-d)
    if not 0<p<1: raise ValueError('Invalid risk-neutral probability')
    terminal=forward*np.exp((2*np.arange(steps+1)-steps)*math.log(u))
    values=np.maximum((1 if kind=='C' else -1)*(terminal-strike),0.)
    for _ in range(steps): values=math.exp(-rate*dt)*(p*values[1:]+(1-p)*values[:-1])
    return float(values[0])
