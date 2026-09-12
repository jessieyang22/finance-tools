"""Official par curves + actual Treasury notes -> valuation, risk and historical shocks."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .ingest import DATA, ROOT
from .curves import TENORS, bootstrap
from .bonds import value, risk, cashflows, auction_price_from_yield

OUT=ROOT/'reports/treasury-risk'

def inputs():
    rates=pd.read_csv(DATA/'normalized/treasury.csv',parse_dates=['date'])
    panel=rates.pivot(index='date',columns='tenor',values='par_yield').reindex(columns=TENORS).sort_index()
    return panel,pd.read_csv(DATA/'normalized/securities.csv')

def analyze():
    OUT.mkdir(parents=True,exist_ok=True)
    panel,bonds=inputs();excluded=panel[panel.isna().any(axis=1)]
    panel=panel.dropna()
    if len(panel)<50: raise ValueError('Insufficient real curve history')
    date=panel.index[-1];curve=bootstrap(panel.iloc[-1].to_numpy())
    excluded.to_csv(OUT/'excluded_curve_dates.csv')
    # Historical shock observations are differences between actual successive published curves.
    curves=[bootstrap(row.to_numpy()) for _,row in panel.iterrows()]
    zeros=np.array([c.zero(c.times[1:]) for c in curves]);shocks=np.diff(zeros,axis=0)
    pd.DataFrame(zeros,index=panel.index,columns=curve.times[1:]).to_csv(OUT/'zero_curve_history.csv',index_label='date')
    pd.DataFrame({'tenor':curve.times[1:],'discount_factor':curve.discounts[1:],'zero_rate':curve.zero(curve.times[1:])}).to_csv(OUT/'latest_curve.csv',index=False)
    risk_rows=[];cfrows=[];auction=[]
    for _,bond in bonds.iterrows():
        val=value(bond,date,curve);r=risk(bond,date,curve)
        row=dict(cusip=bond.cusip,term=bond.securityTerm,coupon_percent=bond.interestRate,maturity=bond.maturityDate[:10],**val)
        row.update({k:v for k,v in r.items() if k!='key_dv01'})
        row.update({f'key_{t:g}y_dv01':v for t,v in zip(TENORS,r['key_dv01'])});risk_rows.append(row)
        dates,t,cfs,accrued=cashflows(bond,date)
        cfrows.extend(dict(cusip=bond.cusip,payment_date=str(d.date()),years=y,cashflow_per_100=c,discount_factor=float(curve.df(y)),present_value=c*curve.df(y)) for d,y,c in zip(dates,t,cfs))
        calculated=auction_price_from_yield(bond)
        auction.append(dict(cusip=bond.cusip,auction_date=bond.auctionDate[:10],reported_clean_price=bond.pricePer100,
                            calculated_clean_price=calculated,absolute_error=abs(calculated-bond.pricePer100)))
    risk_df=pd.DataFrame(risk_rows);risk_df.to_csv(OUT/'bond_risk.csv',index=False)
    pd.DataFrame(cfrows).to_csv(OUT/'cashflows.csv',index=False)
    pd.DataFrame(auction).to_csv(OUT/'auction_price_validation.csv',index=False)
    # Target actual 5y issue, hedges actual 2y and 10y issues; face notionals are portfolio design inputs.
    selected=bonds.set_index('securityTerm').loc[['5-Year','2-Year','10-Year']]
    prices=np.array([value(b,date,curve)['dirty'] for _,b in selected.iterrows()])
    kr=np.array([risk(b,date,curve)['key_dv01'] for _,b in selected.iterrows()])
    dv=kr.sum(axis=1)
    level=np.array([1.,0.,-dv[0]/dv[2]])
    least=np.r_[1.,np.linalg.lstsq(kr[1:].T,-kr[0],rcond=None)[0]]
    baskets={'unhedged':np.array([1.,0.,0.]),'parallel_dv01_hedge':level,'key_rate_least_squares_hedge':least}
    # A base $1m face target is an explicit sizing assumption, never an observed fund position.
    scale=1_000_000/100
    exposures=[]
    for name,weights in baskets.items():
        for (_,b),w in zip(selected.iterrows(),weights):
            exposures.append(dict(strategy=name,cusip=b.cusip,face_dollars=w*1_000_000))
    pd.DataFrame(exposures).to_csv(OUT/'hedge_positions.csv',index=False)
    rows=[]
    for i,shock in enumerate(shocks):
        shocked=curve.bump_zero(shock)
        newprices=np.array([value(b,date,shocked)['dirty'] for _,b in selected.iterrows()])
        for name,weights in baskets.items():
            rows.append(dict(shock_start=str(panel.index[i].date()),shock_end=str(panel.index[i+1].date()),
                             calendar_gap_days=(panel.index[i+1]-panel.index[i]).days,strategy=name,
                             repricing_change_dollars=float((newprices-prices)@weights*scale)))
    scenarios=pd.DataFrame(rows);scenarios.to_csv(OUT/'historical_shock_repricing.csv',index=False)
    stats=[]
    for name,g in scenarios.groupby('strategy'):
        pnl=g.repricing_change_dollars
        stats.append(dict(strategy=name,observed_shocks=len(g),std_dollars=pnl.std(ddof=1),
                          loss_95_quantile_dollars=-pnl.quantile(.05),worst_change_dollars=pnl.min(),
                          residual_parallel_dv01_dollars=float(baskets[name]@dv*scale)))
    stats=pd.DataFrame(stats);stats.to_csv(OUT/'hedge_scores.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for idx,label in [(0,str(panel.index[0].date())),(-1,str(date.date()))]:
        axes[0].plot(TENORS,100*panel.iloc[idx],marker='o',label=label)
    axes[0].set(xlabel='Maturity (years)',ylabel='Official par yield (%)',title='Observed Treasury curves');axes[0].legend();axes[0].grid(alpha=.2)
    labels={'unhedged':'Unhedged','parallel_dv01_hedge':'DV01 hedge','key_rate_least_squares_hedge':'Key-rate hedge'}
    for name,g in scenarios.groupby('strategy'):
        axes[1].hist(g.repricing_change_dollars,bins=40,alpha=.45,label=labels[name])
    axes[1].set(xlabel='Fixed-portfolio repricing change ($)',ylabel='Observed-shock count',title='Historical curve shocks on current holdings');axes[1].legend()
    fig.tight_layout();fig.savefig(OUT/'curve_and_hedges.png',dpi=160);plt.close(fig)
    summary=dict(valuation_date=str(date.date()),first_curve_date=str(panel.index[0].date()),curve_dates=len(panel),
                 observed_shocks=len(shocks),actual_treasury_notes=len(bonds),
                 maximum_auction_price_error=float(max(r['absolute_error'] for r in auction)),
                 results_type='historical_shock_model_repricing_not_realized_trading_pnl')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    table='| Strategy | Shock P&L standard deviation ($) | Residual DV01 ($/bp) |\n|---|---:|---:|\n'+''.join(f'| {r.strategy} | {r.std_dollars:,.2f} | {r.residual_parallel_dv01_dollars:,.4f} |\n' for r in stats.itertuples())
    (OUT/'README.md').write_text(f'''# Treasury curve and bond risk research

Valuation date **{date.date()}**. {len(panel)} official curve dates from {panel.index[0].date()}, {len(shocks)} observed changes, and {len(bonds)} actual Treasury note issues.

## Validation and findings

Cash-flow pricing from published auction yields reproduces actual auction clean prices to a maximum absolute error of **{summary['maximum_auction_price_error']:.6f} per $100 face**. Current curve-derived bond prices are model estimates, not exchange quotes.

{table}

The target is $1 million face of the actual August 2025 five-year note. One hedge offsets parallel DV01 using the ten-year note. The other minimizes squared key-rate exposures using two- and ten-year notes. Positions are selected from current risk exposures, without fitting to historical P&L.

The historical changes are applied to a **fixed current portfolio and valuation date**. These are scenario repricing distributions, not an investment-return backtest. Financing, repo, bid/ask costs, aging, and coupons paid through historical time are excluded from this instantaneous curve-risk exercise. Rate shocks are observed; portfolio notionals and hedge rules are explicit research choices.

## Outputs

`bond_risk.csv` contains clean/dirty prices, accrued interest, parallel DV01, duration, convexity, and nine key-rate sensitivities. `cashflows.csv` traces each payment to its discounted value. `auction_price_validation.csv` compares independent yield pricing with Treasury auction results. `zero_curve_history.csv` contains model-derived rates from observed par curves. `historical_shock_repricing.csv` labels every shock with both actual source dates and its calendar gap.

![Curves and hedge distributions](curve_and_hedges.png)

See [methodology](../../docs/TREASURY.md) and [data provenance](../../docs/DATA.md).
''')
    print(json.dumps(summary))

if __name__=='__main__': analyze()
