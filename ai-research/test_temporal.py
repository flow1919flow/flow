"""Meaningful synthetic tests for causal splits and portable inference."""
from datetime import date, timedelta
import unittest
import numpy as np
from train_ml1 import fit_one, splits

class TemporalContract(unittest.TestCase):
    def fixture(self):
        dates=[(date(2024,1,1)+timedelta(days=i)).isoformat() for i in range(242)]
        rows=[dict(day=day,ns=(i+1)*1000,end_ns=(i+1)*1000+90) for i,day in enumerate(dates)]
        return dates,rows

    def test_calendar_gap_and_unknown_outcome_purge(self):
        dates,rows=self.fixture()
        rows[20]['end_ns']=rows[81]['ns']+1
        for start,train,test in splits(rows,dates):
            self.assertNotIn(start-1,train)
            self.assertNotIn(start-1,test)
            self.assertTrue(all(rows[i]['end_ns']<min(rows[j]['ns'] for j in test) for i in train))
            self.assertTrue(all(rows[i]['day']<=dates[start-2] for i in train))
            if start==81:self.assertNotIn(20,train)

    def test_future_changes_do_not_change_earlier_model(self):
        rng=np.random.default_rng(823)
        X=rng.normal(size=(242,5)); y=(X[:,0]+.3*X[:,1]>0).astype(int)
        dates,rows=self.fixture(); _,train,test=next(splits(rows,dates))
        a,b=np.array(train),np.array(test)
        first=fit_one(X[a],y[a]); p=first.predict_proba(X[b])
        future=X.copy(); labels=y.copy()
        future[101:]*=9999;labels[101:]=1-labels[101:]
        second=fit_one(future[a],labels[a])
        np.testing.assert_array_equal(first.named_steps['standardscaler'].mean_,second.named_steps['standardscaler'].mean_)
        np.testing.assert_allclose(p,second.predict_proba(future[b]),rtol=0,atol=0)

    def test_exported_coefficients_match_predictions(self):
        rng=np.random.default_rng(121)
        X=rng.normal(size=(180,5)); y=(X[:,0]>.2*X[:,1]).astype(int)
        model=fit_one(X[:100],y[:100]); scale=model.named_steps['standardscaler']; clf=model.named_steps['logisticregression']
        z=((X[100:]-scale.mean_)/scale.scale_)@clf.coef_[0]+clf.intercept_[0]
        np.testing.assert_allclose(1/(1+np.exp(-z)),model.predict_proba(X[100:])[:,1],rtol=0,atol=1e-12)

if __name__=='__main__':unittest.main()
