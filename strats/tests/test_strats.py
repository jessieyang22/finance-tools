"""Numerical and provenance checks using the checked-in observed-data snapshots."""
import gzip,json,unittest,math
import numpy as np
import pandas as pd
from strats.ingest import DATA,ROOT,raw,digest
from strats.pricing import black76,greeks,crr,implied_vol
from strats.curves import TENORS,bootstrap,key_weights
from strats.bonds import value,risk,cashflows,auction_price_from_yield
from strats.treasury_risk import inputs

class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quotes=pd.read_csv(ROOT/'reports/options-pricing/valuations.csv')
        cls.sample=cls.quotes.iloc[(cls.quotes.strike/cls.quotes.forward-1).abs().argsort()[:8]]
        cls.panel,cls.bonds=inputs();cls.date=cls.panel.index[-1];cls.curve=bootstrap(cls.panel.iloc[-1].to_numpy())

    def test_raw_source_integrity(self):
        m=json.loads((DATA/'manifest.json').read_text())
        for source in m['sources']:
            b=raw(source['name']);self.assertEqual(len(b),source['bytes_uncompressed'])
            self.assertTrue(source['url'].startswith('https://'))

    def test_normalized_integrity(self):
        m=json.loads((DATA/'manifest.json').read_text())
        for name,sha in m['normalized_files'].items(): self.assertEqual(digest((DATA/'normalized'/name).read_bytes()),sha)

    def test_accepted_quotes_match_observed_source(self):
        source={r['option']:r for r in json.loads(raw('options.json'))['data']['options']}
        for r in self.quotes.itertuples():
            self.assertEqual(r.bid,source[r.option]['bid']);self.assertEqual(r.ask,source[r.option]['ask'])
            self.assertAlmostEqual(r.mid,(r.bid+r.ask)/2,places=10)

    def test_iv_roundtrip_and_quote_bounds(self):
        for r in self.quotes.itertuples():
            p=black76(r.forward,r.strike,r.t,r.rate,r.iv_mid,r.kind)
            self.assertAlmostEqual(p,r.mid,places=7)
            self.assertTrue(r.bid<=r.mid<=r.ask)

    def test_put_call_parity(self):
        for r in self.sample.itertuples():
            c=black76(r.forward,r.strike,r.t,r.rate,r.iv_mid,'C');p=black76(r.forward,r.strike,r.t,r.rate,r.iv_mid,'P')
            self.assertAlmostEqual(c-p,math.exp(-r.rate*r.t)*(r.forward-r.strike),places=9)

    def test_greeks_against_finite_differences(self):
        for r in self.sample.itertuples():
            f,k,t,rate,v=r.forward,r.strike,r.t,r.rate,r.iv_mid
            g=greeks(f,k,t,rate,v,r.kind);fun=lambda f=f,t=t,rate=rate,v=v:black76(f,k,t,rate,v,r.kind)
            h=f*1e-5
            self.assertAlmostEqual((fun(f=f+h)-fun(f=f-h))/(2*h),g['forward_delta'],places=6)
            self.assertAlmostEqual((fun(f=f+h)+fun(f=f-h)-2*fun())/h**2,g['forward_gamma'],places=6)
            h=1e-5
            self.assertAlmostEqual((fun(v=v+h)-fun(v=v-h))/(2*h)*.01,g['vega_per_vol_point'],places=5)
            self.assertAlmostEqual(-(fun(t=t+h)-fun(t=t-h))/(2*h)/365,g['theta_per_day'],places=5)
            self.assertAlmostEqual((fun(rate=rate+h)-fun(rate=rate-h))/(2*h)*1e-4,g['rho_per_bp_fixed_forward'],places=7)

    def test_tree_convergence_on_real_contracts(self):
        errors=pd.read_csv(ROOT/'reports/options-pricing/tree_convergence.csv')
        for option,g in errors.groupby('option'):
            last=g[g.steps==800].iloc[0]
            self.assertLess(last.abs_error,.15)
            self.assertLess(last.abs_error,g[g.steps==100].iloc[0].abs_error)

    def test_options_local_hedge_exposures_and_spread_cost(self):
        b=pd.read_csv(ROOT/'reports/options-pricing/hedge_baskets.csv')
        for expiry,g in b.groupby('expiry'):
            self.assertAlmostEqual(g.dollar_forward_delta.sum(),0,places=8)
            self.assertAlmostEqual(g.dollar_vega_per_point.sum(),0,places=8)
            self.assertTrue((g.dollar_halfspread_cost>=0).all())
            self.assertAlmostEqual(g.dollar_entry_cash_required.sum()-g.dollar_mid_value.sum(),g.dollar_halfspread_cost.sum(),places=7)

    def test_rates_precede_option_snapshot(self):
        s=json.loads((ROOT/'reports/options-pricing/summary.json').read_text())
        self.assertLess(pd.Timestamp(s['rate_date']),pd.Timestamp(s['snapshot']).normalize())
        self.assertEqual(s['historical_hedging_status'],'unavailable_single_snapshot')

    def test_quote_audit_conservation(self):
        audit=pd.read_csv(ROOT/'reports/options-pricing/quote_audit.csv')
        source=pd.read_csv(DATA/'normalized/options.csv')
        self.assertEqual(set(audit.option),set(source.option))
        self.assertEqual(set(audit[audit.reason=='accepted'].option),set(self.quotes.option))

    def test_bootstrap_reprices_par_instruments(self):
        for i in (0,len(self.panel)//2,len(self.panel)-1):
            ys=self.panel.iloc[i].to_numpy();c=bootstrap(ys)
            for tenor,y in zip(TENORS,ys):
                n=int(tenor*2);pv=y/2*sum(c.discounts[1:n+1])+c.discounts[n]
                self.assertAlmostEqual(pv,1,places=11)
            self.assertTrue((c.discounts>0).all())

    def test_bond_dirty_clean_and_cashflows(self):
        for _,b in self.bonds.iterrows():
            val=value(b,self.date,self.curve);dates,t,cfs,accrued=cashflows(b,self.date)
            self.assertAlmostEqual(val['dirty']-val['clean'],accrued,places=10)
            self.assertAlmostEqual(val['dirty'],sum(cfs*self.curve.df(t)),places=10)
            self.assertEqual(dates[-1],pd.Timestamp(b.maturityDate))
            self.assertTrue((t>0).all())

    def test_real_auction_prices_independent_check(self):
        for _,b in self.bonds.iterrows(): self.assertLess(abs(auction_price_from_yield(b)-b.pricePer100),.0003)

    def test_coupon_date_and_accrued_reset(self):
        b=self.bonds[self.bonds.securityTerm=='5-Year'].iloc[0]
        dates,t,cfs,accrued=cashflows(b,'2026-02-28')
        self.assertEqual(accrued,0.)
        self.assertEqual(dates[0],pd.Timestamp('2026-08-31'))

    def test_key_risk_partition_and_price_direction(self):
        np.testing.assert_allclose(key_weights(self.curve.times[1:]).sum(axis=0),1.)
        for _,b in self.bonds.iterrows():
            r=risk(b,self.date,self.curve)
            self.assertGreater(r['dv01_per_100'],0)
            self.assertAlmostEqual(sum(r['key_dv01']),r['dv01_per_100'],places=6)
            self.assertGreater(r['convexity_zero_parallel'],0)

    def test_historical_shocks_match_observed_curves(self):
        report=pd.read_csv(ROOT/'reports/treasury-risk/historical_shock_repricing.csv')
        group=report[report.strategy=='unhedged']
        self.assertEqual(len(group),len(self.panel)-1)
        self.assertEqual(list(group.shock_end),list(self.panel.index[1:].strftime('%Y-%m-%d')))
        row=group.iloc[-1];prev=bootstrap(self.panel.iloc[-2].to_numpy())
        shock=self.curve.zero(self.curve.times[1:])-prev.zero(prev.times[1:])
        b=self.bonds[self.bonds.securityTerm=='5-Year'].iloc[0]
        change=(value(b,self.date,self.curve.bump_zero(shock))['dirty']-value(b,self.date,self.curve)['dirty'])*10000
        self.assertAlmostEqual(change,row.repricing_change_dollars,places=7)

    def test_parallel_hedge_neutrality(self):
        stats=pd.read_csv(ROOT/'reports/treasury-risk/hedge_scores.csv')
        self.assertLess(abs(stats.set_index('strategy').loc['parallel_dv01_hedge','residual_parallel_dv01_dollars']),1e-6)

    def test_invalid_inputs_fail(self):
        with self.assertRaises(ValueError): implied_vol(-1,**dict(forward=1,strike=1,t=1,rate=.01))
        with self.assertRaises(ValueError): bootstrap([.04])
        with self.assertRaises(ValueError): self.curve.df(31)
        b=self.bonds.iloc[0]
        with self.assertRaises(ValueError): value(b,b.maturityDate,self.curve)

if __name__=='__main__':unittest.main()
