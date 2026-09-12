"""Transparent approximate bootstrap from official indicative Treasury par yields."""
from dataclasses import dataclass
import numpy as np

TENORS=np.array([.5,1.,2.,3.,5.,7.,10.,20.,30.])

@dataclass
class Curve:
    times: np.ndarray
    discounts: np.ndarray

    def df(self,t):
        a=np.asarray(t,dtype=float)
        if np.any(a<0) or np.any(a>self.times[-1]): raise ValueError('Outside supported curve maturities')
        return np.exp(np.interp(a,self.times,np.log(self.discounts)))

    def zero(self,t):
        a=np.asarray(t,dtype=float)
        if np.any(a<=0): raise ValueError('Zero rate requires positive maturity')
        return -np.log(self.df(a))/a

    def bump_zero(self,changes):
        """Changes are continuously compounded decimal zero-rate shocks on positive nodes."""
        changes=np.broadcast_to(changes,self.times[1:].shape)
        return Curve(self.times.copy(),np.r_[1.,self.discounts[1:]*np.exp(-changes*self.times[1:])])


def bootstrap(par):
    y=np.asarray(par,dtype=float)
    if y.shape!=TENORS.shape or not np.isfinite(y).all(): raise ValueError('Complete par curve required')
    grid=np.arange(.5,30.01,.5); coupons=np.interp(grid,TENORS,y)/2
    ds=[]
    for c in coupons:
        discount=(1-c*sum(ds))/(1+c)
        if not np.isfinite(discount) or discount<=0: raise ValueError('Non-positive discount factor')
        ds.append(discount)
    return Curve(np.r_[0.,grid],np.r_[1.,ds])


def key_weights(times,knots=(.5,1.,2.,3.,5.,7.,10.,20.,30.)):
    """Partition-of-unity triangular zero-rate bumps, flat at both boundaries."""
    eye=np.eye(len(knots))
    return np.array([np.interp(times,knots,row) for row in eye])
