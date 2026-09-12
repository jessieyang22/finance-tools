"""Observed SPXW quotes -> parity forwards -> IV/Greeks -> smile diagnostics and hedges."""
import json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .ingest import DATA, ROOT
from .pricing import black76, implied_vol, greeks, crr

OUT=ROOT/'reports/options-pricing'

def analyze():
    OUT.mkdir(parents=True,exist_ok=True)
    q=pd.read_csv(DATA/'normalized/options.csv')
    meta=json.loads((DATA/'normalized/options_metadata.json').read_text())
    asof=pd.Timestamp(meta['timestamp']).tz_localize('America/New_York')
    rates=pd.read_csv(DATA/'normalized/treasury.csv',parse_dates=['date'])
    # Previous calendar date avoids use of a same-day Treasury close.
    available=rates[rates.date<pd.Timestamp(asof.date())]
    rate_date=available.date.max(); rr=available[available.date==rate_date].sort_values('tenor')
    if (pd.Timestamp(asof.date())-rate_date).days>7: raise ValueError('Rate snapshot too stale')
    spot=meta['underlying']['current_price']
    q['mid']=(q.bid+q.ask)/2;q['spread']=q.ask-q.bid
    q['reason']='accepted_preliminary'
    q.loc[(q.bid<=0)|(q.ask<q.bid)|~np.isfinite(q.bid+q.ask),'reason']='invalid_or_zero_market'
    q.loc[(q.reason=='accepted_preliminary')&((q.spread/q.mid>.35)|(q.bid_size<=0)|(q.ask_size<=0)),'reason']='wide_or_empty_market'
    q.loc[(q.reason=='accepted_preliminary')&~q.strike.between(.85*spot,1.15*spot),'reason']='outside_strike_scope'
    all_exp=sorted(q.expiry.unique())
    # Four expiries closest to target durations, deterministic and independent of results.
    chosen=sorted(set(min(all_exp,key=lambda e:abs((pd.Timestamp(e)-asof.tz_localize(None).normalize()).days-d)) for d in (35,60,90,115)))
    q.loc[(q.reason=='accepted_preliminary')&~q.expiry.isin(chosen),'reason']='unselected_expiry'
    records=[];forwards=[];pairs_audit=[]
    for expiry in chosen:
        end=pd.Timestamp(expiry+' 16:00:00',tz='America/New_York')
        t=(end-asof).total_seconds()/(365*86400)
        rate=2*math.log1p(float(np.interp(t,rr.tenor,rr.par_yield))/2)
        discount=math.exp(-rate*t)
        sub=q[(q.expiry==expiry)&(q.reason=='accepted_preliminary')]
        paired=sub.pivot(index='strike',columns='kind',values=['mid','bid','ask']).dropna()
        paired=paired.loc[paired.index.to_series().between(.97*spot,1.03*spot)]
        if len(paired)<5:
            q.loc[(q.expiry==expiry)&(q.reason=='accepted_preliminary'),'reason']='insufficient_parity_pairs';continue
        estimates=paired.index.to_numpy()+(paired['mid']['C']-paired['mid']['P']).to_numpy()/discount
        forward=float(np.median(estimates))
        for strike,row in paired.iterrows():
            lo=strike+(row[('bid','C')]-row[('ask','P')])/discount
            hi=strike+(row[('ask','C')]-row[('bid','P')])/discount
            pairs_audit.append(dict(expiry=expiry,strike=strike,forward_lower=lo,forward_upper=hi,
                                    fitted_forward=forward,inside_bid_ask_bounds=bool(lo<=forward<=hi)))
        forwards.append(dict(expiry=expiry,t=t,rate=rate,discount=discount,forward=forward,
                             pairs=len(paired),forward_iqr=float(np.percentile(estimates,75)-np.percentile(estimates,25))))
        for idx,row in sub.iterrows():
            if (row.kind=='C' and row.strike<forward) or (row.kind=='P' and row.strike>=forward):
                q.loc[idx,'reason']='in_the_money_counterpart';continue
            try:
                vol=implied_vol(row.mid,forward,row.strike,t,rate,row.kind)
                rec=dict(row);rec.update(forward=forward,t=t,rate=rate,iv_mid=vol,
                                        model_price=black76(forward,row.strike,t,rate,vol,row.kind))
                for side in ('bid','ask'):
                    try:rec['iv_'+side]=implied_vol(row[side],forward,row.strike,t,rate,row.kind)
                    except ValueError:rec['iv_'+side]=np.nan
                rec.update(greeks(forward,row.strike,t,rate,vol,row.kind));records.append(rec)
                q.loc[idx,'reason']='accepted'
            except ValueError as e: q.loc[idx,'reason']='no_valid_iv'
    q.to_csv(OUT/'quote_audit.csv',index=False)
    result=pd.DataFrame(records)
    if result.empty: raise ValueError('No valid observed options')
    result=result.sort_values(['expiry','strike']).reset_index(drop=True)
    fit_stats=[];fit_records=[];checks=[];tree=[];hedges=[]
    fig,ax=plt.subplots(figsize=(10,6))
    for expiry,sub in result.groupby('expiry'):
        sub=sub.copy().sort_values('strike');x=np.log(sub.strike/sub.forward).to_numpy();w=sub.iv_mid.to_numpy()**2*sub.t.to_numpy()
        hold=np.arange(len(sub))%5==0
        if (~hold).sum()<10: continue
        coefficients=np.polyfit(x[~hold],w[~hold],2)
        fitted_variance=np.polyval(coefficients,x)
        fitted_iv=np.sqrt(np.maximum(fitted_variance,1e-12)/sub.t.to_numpy())
        prices=np.array([black76(r.forward,r.strike,r.t,r.rate,v,r.kind) for (_,r),v in zip(sub.iterrows(),fitted_iv)])
        sub['smile_iv']=fitted_iv;sub['smile_price']=prices;sub['cross_section_holdout']=hold
        sub['negative_fitted_variance']=fitted_variance<=0
        fit_records.extend(sub.to_dict('records'))
        fit_stats.append(dict(expiry=expiry,training_quotes=int((~hold).sum()),heldout_quotes=int(hold.sum()),
                              heldout_price_rmse=float(np.sqrt(np.mean((prices[hold]-sub.mid.to_numpy()[hold])**2))),
                              heldout_inside_spread=float(np.mean((prices[hold]>=sub.bid.to_numpy()[hold])&(prices[hold]<=sub.ask.to_numpy()[hold]))),
                              negative_variance_nodes=int((fitted_variance<=0).sum())))
        ax.scatter(sub.strike/sub.forward,100*sub.iv_mid,s=10,alpha=.7,label=expiry)
        ax.plot(sub.strike/sub.forward,100*fitted_iv,linewidth=1)
        # Convert both put/call mids to equivalent calls before strike-shape checks.
        calls=sub.mid.to_numpy()+np.where(sub.kind.to_numpy()=='P',np.exp(-sub.rate*sub.t)*(sub.forward-sub.strike),0)
        k=sub.strike.to_numpy();slopes=np.diff(calls)/np.diff(k)
        checks.append(dict(expiry=expiry,monotonicity_violations=int((slopes>1e-8).sum()),
                           convexity_violations=int((np.diff(slopes)<-1e-8).sum()),
                           note='Midpoint diagnostics, not executable arbitrage; discrete quote noise and parity estimate matter.'))
        atm=sub.iloc[np.argmin(np.abs(x))]
        for steps in (100,200,400,800):
            price=crr(atm.forward,atm.strike,atm.t,atm.rate,atm.iv_mid,atm.kind,steps)
            tree.append(dict(option=atm.option,steps=steps,analytical_price=atm.model_price,tree_price=price,abs_error=abs(price-atm.model_price)))
        # Option-only hedge: two observed contracts neutralize forward delta and vega.
        candidates=sub[(sub.option!=atm.option)&(sub.vega_per_vol_point>1)]
        puts=candidates[candidates.kind=='P'];calls_sub=candidates[candidates.kind=='C']
        if not puts.empty and not calls_sub.empty:
            hp=puts.iloc[np.argmin(abs(puts.strike/puts.forward-.97))]
            hc=calls_sub.iloc[np.argmin(abs(calls_sub.strike/calls_sub.forward-1.03))]
            mat=np.array([[hp.forward_delta,hc.forward_delta],[hp.vega_per_vol_point,hc.vega_per_vol_point]])
            weights=np.linalg.solve(mat,-np.array([atm.forward_delta,atm.vega_per_vol_point]))
            for label,row,units in [('target',atm,1.),('put_hedge',hp,weights[0]),('call_hedge',hc,weights[1])]:
                # Fractional theoretical sizing; real SPX contracts must be integers.
                execution=row.ask if units>0 else row.bid
                hedges.append(dict(expiry=expiry,role=label,option=row.option,contracts=units,
                                   dollar_mid_value=100*units*row.mid,
                                   dollar_entry_cash_required=100*units*execution,
                                   dollar_halfspread_cost=100*abs(units)*row.spread/2,
                                   dollar_forward_delta=100*units*row.forward_delta,
                                   dollar_vega_per_point=100*units*row.vega_per_vol_point,
                                   dollar_forward_gamma=100*units*row.forward_gamma))
    result.to_csv(OUT/'valuations.csv',index=False)
    pd.DataFrame(forwards).to_csv(OUT/'forwards.csv',index=False)
    pd.DataFrame(pairs_audit).to_csv(OUT/'parity_audit.csv',index=False)
    pd.DataFrame(fit_records).to_csv(OUT/'smile_validation.csv',index=False)
    pd.DataFrame(fit_stats).to_csv(OUT/'smile_scores.csv',index=False)
    pd.DataFrame(checks).to_csv(OUT/'arbitrage_diagnostics.csv',index=False)
    pd.DataFrame(tree).to_csv(OUT/'tree_convergence.csv',index=False)
    pd.DataFrame(hedges).to_csv(OUT/'hedge_baskets.csv',index=False)
    ax.set(xlabel='Strike / inferred forward',ylabel='Implied volatility (%)',title='Observed SPXW quotes and fitted smiles')
    ax.legend(title='Expiry');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'volatility_smiles.png',dpi=160);plt.close(fig)
    summary=dict(snapshot=meta['timestamp'],assumed_timezone='America/New_York',rate_date=str(rate_date.date()),
                 raw_scope_quotes=len(q),accepted_quotes=len(result),expiries=len(forwards),
                 quote_exclusions=q.reason.value_counts().to_dict(),
                 maximum_iv_roundtrip_error=float(abs(result.model_price-result.mid).max()),
                 historical_hedging_status='unavailable_single_snapshot',
                 stale_underlying_last_trade_time=meta['underlying']['last_trade_time'])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    report=f'''# Options pricing and risk research

Snapshot **{summary['snapshot']}**, assumed New York time. Treasury rate date **{summary['rate_date']}**.

## Findings

- {len(result):,} usable observed SPXW quotes across {len(forwards)} selected expiries, from {len(q):,} in-scope source quotes.
- Maximum IV solver repricing error: {summary['maximum_iv_roundtrip_error']:.3g} index points. This is numerical inversion accuracy, not predictive accuracy.
- Four expiry smiles are fitted on 80% of strikes and checked on the remaining 20%. Read `smile_scores.csv` for actual pricing errors and bid/ask coverage.
- `hedge_baskets.csv` sizes two observed options against one target to neutralize forward delta and parallel-volatility vega locally. Entry spread costs use actual bids/asks. Fractional contracts are theoretical sizing, not executable orders.

## What the data can support

Pricing, quote-quality assessment, cross-sectional smile interpolation, numerical convergence, and local hedge sensitivities. The archive contains one snapshot, so **no historical hedge return, Sharpe ratio, or trading-profit claim is made**. The underlying last trade is {summary['stale_underlying_last_trade_time']}; forwards are inferred from paired quotes instead of assuming that last trade is contemporaneous.

## Read the outputs

`valuations.csv` has every accepted observed quote, IV and unit-labelled Greeks. `quote_audit.csv` preserves every in-scope row and the final acceptance/exclusion reason. `parity_audit.csv` checks whether the estimated forward lies within each paired bid/ask interval. `arbitrage_diagnostics.csv` reports raw midpoint shape violations without labelling them tradable opportunities. `tree_convergence.csv` compares an independent CRR lattice with the analytical model. `smile_validation.csv` identifies held-out strikes explicitly.

![Observed smiles](volatility_smiles.png)

See [methodology](../../docs/OPTIONS.md) and [data provenance](../../docs/DATA.md).
'''
    (OUT/'README.md').write_text(report)
    print(json.dumps(summary))

if __name__=='__main__': analyze()
