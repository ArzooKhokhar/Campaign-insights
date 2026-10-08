"""Channel ROI, funnel, email automation, A/B test and written recommendations."""
import math
import pandas as pd

APPLIED = {"Applied", "Offer", "Enrolled"}


def channel_table(web, ads, crm):
    sess = web.groupby("channel")[["sessions", "enquiries"]].sum()
    spend = ads.groupby("channel")["spend"].sum()
    leads = crm.groupby("channel").size()
    apps = crm[crm["status"].isin(APPLIED)].groupby("channel").size()
    enrol = crm[crm["status"] == "Enrolled"].groupby("channel").size()
    rows = []
    for ch in sess.index:
        sp = float(spend.get(ch, 0))
        a = int(apps.get(ch, 0))
        rows.append({"channel": ch, "sessions": int(sess.loc[ch, "sessions"]), "leads": int(leads.get(ch, 0)),
                     "applications": a, "enrolments": int(enrol.get(ch, 0)), "spend": round(sp),
                     "conv": round(sess.loc[ch, "enquiries"] / sess.loc[ch, "sessions"] * 100, 2),
                     "cpl": round(sp / leads.get(ch, 1), 2) if sp else None,
                     "cpa": round(sp / a, 2) if sp and a else None})
    return sorted(rows, key=lambda r: -r["leads"])


def weekly(web, ads):
    w = web.copy()
    w["week"] = (pd.to_datetime(w["date"]) - pd.Timestamp("2026-07-06")).dt.days // 7 + 1
    a = ads.copy()
    a["week"] = (pd.to_datetime(a["date"]) - pd.Timestamp("2026-07-06")).dt.days // 7 + 1
    enq = w.pivot_table(index="week", columns="channel", values="enquiries", aggfunc="sum")
    sp = a.pivot_table(index="week", columns="channel", values="spend", aggfunc="sum")
    cpl = (sp / enq[sp.columns]).round(2)
    return {"weeks": [int(x) for x in enq.index],
            "enquiries": {c: enq[c].astype(int).tolist() for c in enq.columns},
            "cpl": {c: cpl[c].tolist() for c in cpl.columns}}


def funnel(crm):
    total = len(crm)
    order = ["Enquiry", "Applied", "Offer", "Enrolled"]
    reached = {"Enquiry": total,
               "Applied": int(crm["status"].isin(APPLIED).sum()),
               "Offer": int(crm["status"].isin({"Offer", "Enrolled"}).sum()),
               "Enrolled": int((crm["status"] == "Enrolled").sum())}
    return [{"stage": s, "count": reached[s]} for s in order]


def email_table(email):
    g = email.groupby("journey")[["sent", "delivered", "unique_opens", "unique_clicks", "unsubscribes"]].sum()
    rows = []
    for j, r in g.iterrows():
        rows.append({"journey": j, "sends": int(r["sent"]),
                     "open": round(r["unique_opens"] / r["delivered"] * 100, 1),
                     "ctr": round(r["unique_clicks"] / r["delivered"] * 100, 2),
                     "ctor": round(r["unique_clicks"] / r["unique_opens"] * 100, 1),
                     "unsub": round(r["unsubscribes"] / r["delivered"] * 100, 2)})
    e = email.copy()
    e["week"] = (pd.to_datetime(e["send_date"]) - pd.Timestamp("2026-07-06")).dt.days // 7 + 1
    wk = e.groupby("week")[["delivered", "unique_clicks"]].sum()
    trend = {"weeks": [int(x) for x in wk.index], "ctr": (wk["unique_clicks"] / wk["delivered"] * 100).round(2).tolist()}
    return sorted(rows, key=lambda r: -r["ctr"]), trend


def ab_test(ab):
    g = ab.groupby("variant")[["visitors", "conversions"]].sum()
    (na, ca), (nb, cb) = g.iloc[0].tolist(), g.iloc[1].tolist()
    pa, pb = ca / na, cb / nb
    pool = (ca + cb) / (na + nb)
    z = (pb - pa) / math.sqrt(pool * (1 - pool) * (1 / na + 1 / nb))
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    lo, hi = (pb - pa - 1.96 * se), (pb - pa + 1.96 * se)
    ab = ab.sort_values("date")
    cum = ab.groupby("variant").apply(lambda d: (d["conversions"].cumsum() / d["visitors"].cumsum() * 100).round(2).tolist(),
                                      include_groups=False)
    return {"a": {"name": g.index[0], "visitors": int(na), "conv": int(ca), "rate": round(pa * 100, 2)},
            "b": {"name": g.index[1], "visitors": int(nb), "conv": int(cb), "rate": round(pb * 100, 2)},
            "lift": round((pb / pa - 1) * 100, 1), "p": round(p, 4), "z": round(z, 2),
            "ci": [round(lo * 100, 2), round(hi * 100, 2)], "significant": p < 0.05,
            "days": sorted(ab["date"].unique().tolist()), "cum": {k: v for k, v in cum.items()},
            "monthly_visitors": int((na + nb) / 28 * 30)}


def recommendations(channels, wk, emails, test, log):
    recs = []
    paid = [c for c in channels if c["cpa"]]
    best, worst = min(paid, key=lambda c: c["cpa"]), max(paid, key=lambda c: c["cpa"])
    recs.append({"title": f"Shift budget toward {best['channel']}",
                 "body": f"{best['channel']} costs ${best['cpa']:.0f} per application versus ${worst['cpa']:.0f} for {worst['channel']}. "
                         f"Moving 20% of {worst['channel']} budget would buy more applications for the same spend.",
                 "impact": "High"})
    s = wk["cpl"]["Paid Social"]
    first, last = sum(s[:4]) / 4, sum(s[-4:]) / 4
    recs.append({"title": "Refresh Paid Social creative",
                 "body": f"Paid Social cost per lead rose {((last / first) - 1) * 100:.0f}% from weeks 1–4 (${first:.0f}) to weeks 9–12 (${last:.0f}), "
                         "a typical sign of ad fatigue. Rotate new creative every 3–4 weeks.",
                 "impact": "High"})
    if test["significant"]:
        extra = test["monthly_visitors"] * (test["b"]["rate"] - test["a"]["rate"]) / 100
        recs.append({"title": f"Roll out course page variant B",
                     "body": f"'{test['b']['name'].split(': ')[1]}' converted at {test['b']['rate']}% vs {test['a']['rate']}% "
                             f"(+{test['lift']}%, p = {test['p']}). At current traffic that is about {extra:.0f} extra enquiries a month.",
                     "impact": "High"})
    hi = max(emails, key=lambda e: e["unsub"])
    recs.append({"title": f"Review frequency of {hi['journey']}",
                 "body": f"{hi['journey']} drives strong clicks ({hi['ctr']}% click rate) but has the highest unsubscribe rate ({hi['unsub']}%). "
                         "Test fewer sends or a preference centre to protect the database.",
                 "impact": "Medium"})
    unattr = next(l for l in log if l["check"] == "Missing UTM / source")
    recs.append({"title": "Fix UTM tagging on enquiry forms",
                 "body": f"{unattr['found']} have no source, so their campaign impact can't be measured. "
                         "Add a shared UTM naming convention and a hidden source field on every form.",
                 "impact": "Medium"})
    return recs
