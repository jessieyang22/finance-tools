"""Fixed-rate Treasury cash flows, clean/dirty prices, and zero-curve risk."""
import calendar
import numpy as np
import pandas as pd
from .curves import key_weights


def coupon_date(maturity,months_back):
    maturity=pd.Timestamp(maturity).normalize()
    date=maturity-pd.DateOffset(months=months_back)
    # Preserve end-of-month convention from August 31 through February.
    if maturity.is_month_end: date=date+pd.offsets.MonthEnd(0)
    return date


def cashflows(bond,settlement):
    settle=pd.Timestamp(settlement).normalize();maturity=pd.Timestamp(bond['maturityDate']).normalize()
    if settle<pd.Timestamp(bond['issueDate']).normalize() or settle>=maturity:
        raise ValueError('Settlement must be within issued bond life')
    dates=[];i=0
    while True:
        date=coupon_date(maturity,6*i)
        if date<=settle: previous=date;break
        dates.append(date);i+=1
    dates=sorted(dates);coupon=float(bond['interestRate'])/2
    values=np.full(len(dates),coupon);values[-1]+=100
    times=np.array([(x-settle).days/365 for x in dates])
    accrued=coupon*(settle-previous).days/(dates[0]-previous).days
    return dates,times,values,accrued


def value(bond,settlement,curve):
    dates,t,cfs,accrued=cashflows(bond,settlement)
    dirty=float(cfs@curve.df(t))
    return {'dirty':dirty,'accrued':accrued,'clean':dirty-accrued}


def risk(bond,settlement,curve):
    p=value(bond,settlement,curve)['dirty'];h=1e-4
    down=value(bond,settlement,curve.bump_zero(-h))['dirty']
    up=value(bond,settlement,curve.bump_zero(h))['dirty']
    result={'dv01_per_100':(down-up)/2,'duration_zero_parallel':(down-up)/(2*h*p),
            'convexity_zero_parallel':(down+up-2*p)/(p*h*h)}
    result['key_dv01']=np.array([(value(bond,settlement,curve.bump_zero(-h*w))['dirty']-
                                value(bond,settlement,curve.bump_zero(h*w))['dirty'])/2
                               for w in key_weights(curve.times[1:])])
    return result


def auction_price_from_yield(bond):
    """Independent Treasury semiannual yield-price check against published auction price."""
    dates,t,cfs,accrued=cashflows(bond,bond['issueDate'])
    first=dates[0];previous=coupon_date(pd.Timestamp(bond['maturityDate']),6*len(dates))
    fraction=(first-pd.Timestamp(bond['issueDate'])).days/(first-previous).days
    y=float(bond['highYield'])/100
    dirty=float(np.sum(cfs/(1+y/2)**(fraction+np.arange(len(cfs)))))
    return dirty-accrued
