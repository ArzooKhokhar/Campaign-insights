"""Create realistic SIMULATED marketing data for a fictional Perth university.

Four sources, exported the way real platforms export them, including the
messiness analysts deal with: inconsistent channel names, duplicate CRM
records, missing UTM tags and impossible email metrics.
"""
from pathlib import Path
import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parent
rng = np.random.default_rng(42)
DAYS = pd.date_range("2026-07-06", periods=84, freq="D")   # 12-week intake campaign

CHANNELS = {
    #                 sessions/day, enquiry rate, spend/day, enquiry->application
    "Paid Search":     (900, 0.026, 1100, 0.30),
    "Paid Social":     (1300, 0.012, 950, 0.15),
    "Email":           (520, 0.036, 0, 0.36),
    "Organic Search":  (1500, 0.019, 0, 0.26),
    "Direct/Referral": (600, 0.022, 0, 0.31),
}
AD_NAMES = {"Paid Search": ["Paid Search", "paid_search", "Google Ads"],
            "Paid Social": ["Paid Social", "paid_social", "Meta"]}
CRM_NAMES = {"Paid Search": ["Paid Search", "google / cpc", "paid search"],
             "Paid Social": ["Paid Social", "facebook / paid", "Facebook"],
             "Email": ["Email", "email", "Marketing Automation"],
             "Organic Search": ["Organic Search", "organic"],
             "Direct/Referral": ["Direct/Referral", "direct", "referral"]}
COURSES = ["Business", "Health", "Engineering & IT", "Education", "Arts & Humanities", "Science"]


def web_and_ads():
    web, ads = [], []
    for i, d in enumerate(DAYS):
        week = i // 7
        weekend = d.dayofweek >= 5
        for ch, (sess, rate, spend, _) in CHANNELS.items():
            s = sess * (0.75 if weekend else 1.05) * rng.normal(1, 0.08)
            r = rate
            if ch == "Paid Social":
                r *= 1 - 0.045 * week               # creative fatigue
            if ch == "Email" and week >= 6:
                s *= 1.35                            # new nurture journey launched
                r *= 1.15
            if week in (8, 9):                       # open day push
                s *= 1.2
            s = int(s)
            web.append({"date": d.date(), "channel": ch, "sessions": s,
                        "enquiries": int(rng.binomial(s, r))})
            if spend:
                sp = spend * rng.normal(1, 0.06) * (1.1 if week in (8, 9) else 1)
                imp = int(sp * rng.uniform(55, 70) * (1.6 if ch == "Paid Social" else 1))
                ads.append({"Date": d.strftime("%d/%m/%Y"),
                            "Channel": rng.choice(AD_NAMES[ch], p=[.6, .25, .15]),
                            "Spend (AUD)": round(sp, 2), "Impressions": imp,
                            "Clicks": int(s * rng.uniform(.92, 1.0))})
    return pd.DataFrame(web), pd.DataFrame(ads)


def crm(web):
    rows, n = [], 0
    for r in web.itertuples():
        app_rate = CHANNELS[r.channel][3]
        for _ in range(r.enquiries):
            n += 1
            stage = rng.random()
            status = ("Enrolled" if stage < app_rate * .45 else "Offer" if stage < app_rate * .7
                      else "Applied" if stage < app_rate else "Enquiry")
            src = rng.choice(CRM_NAMES[r.channel])
            if rng.random() < 0.06:
                src = ""                                   # lost UTM tag
            rows.append({"lead_id": f"L{n:05d}", "email_hash": f"h{n:05d}",
                         "created": str(r.date), "source": src,
                         "course_area": rng.choice(COURSES), "status": status})
    df = pd.DataFrame(rows)
    dupes = df.sample(frac=0.035, random_state=1).copy()   # form submitted twice
    dupes["lead_id"] = [f"L{n + i + 1:05d}" for i in range(len(dupes))]
    return pd.concat([df, dupes]).sample(frac=1, random_state=2).reset_index(drop=True)


def email():
    journeys = {"Welcome nurture": (0.48, 0.062, .0025), "Course explorer": (0.41, 0.051, .003),
                "Open day invite": (0.44, 0.074, .004), "Application reminder": (0.39, 0.083, .0065)}
    rows = []
    for i, d in enumerate(DAYS):
        if d.dayofweek not in (1, 3):                      # sends go out Tue and Thu
            continue
        for j, (open_r, click_r, unsub_r) in journeys.items():
            if j == "Open day invite" and not (6 <= i // 7 <= 9):
                continue
            boost = 1.2 if i // 7 >= 6 else 1             # personalised content from week 7
            sent = int(rng.uniform(5000, 9000))
            deliv = int(sent * rng.uniform(.965, .99))
            opens = int(deliv * open_r * rng.normal(1, .05))
            clicks = int(deliv * click_r * boost * rng.normal(1, .07))
            rows.append({"send_date": str(d.date()), "journey": j, "sent": sent, "delivered": deliv,
                         "unique_opens": opens, "unique_clicks": clicks,
                         "unsubscribes": int(deliv * unsub_r * rng.normal(1, .2))})
    df = pd.DataFrame(rows)
    bad = df.sample(3, random_state=3).index
    df.loc[bad, "unique_clicks"] = df.loc[bad, "unique_opens"] + 250   # platform export glitch
    return df


def ab_test():
    rows = []
    for d in DAYS[28:56]:
        for v, rate in (("A: Enquire now", .034), ("B: Get your course guide", .041)):
            vis = int(rng.normal(430, 40))
            rows.append({"date": str(d.date()), "variant": v, "visitors": vis,
                         "conversions": int(rng.binomial(vis, rate))})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    web, ads = web_and_ads()
    web.to_csv(RAW / "web_analytics.csv", index=False)
    ads.to_csv(RAW / "ad_platform_spend.csv", index=False)
    crm(web).to_csv(RAW / "crm_leads.csv", index=False)
    email().to_csv(RAW / "email_automation.csv", index=False)
    ab_test().to_csv(RAW / "ab_test_course_page.csv", index=False)
    print("Simulated data written to", RAW)
