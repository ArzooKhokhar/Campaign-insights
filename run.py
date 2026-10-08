"""Run the full pipeline: sector market analysis + campaign audit and analysis -> dashboard."""
import json
from pathlib import Path
import pandas as pd

from audit import run_audit
from analyse import channel_table, weekly, funnel, email_table, ab_test, recommendations
from market import analyse_market

ROOT = Path(__file__).resolve().parent
RAW = ROOT


def main():
    market = analyse_market()

    web = pd.read_csv(RAW / "web_analytics.csv")
    ads = pd.read_csv(RAW / "ad_platform_spend.csv")
    crm = pd.read_csv(RAW / "crm_leads.csv")
    email = pd.read_csv(RAW / "email_automation.csv")
    ab = pd.read_csv(RAW / "ab_test_course_page.csv")

    clean, log, recon = run_audit(web, ads, crm, email)
    ch = channel_table(clean["web"], clean["ads"], clean["crm"])
    wk = weekly(clean["web"], clean["ads"])
    em, em_trend = email_table(clean["email"])
    test = ab_test(ab)
    recs = recommendations(ch, wk, em, test, log)
    for r in recs:
        r["tag"] = "Campaign data (simulated)"

    fun = funnel(clean["crm"])
    totals = {"spend": sum(c["spend"] for c in ch), "leads": fun[0]["count"],
              "applications": fun[1]["count"], "enrolments": fun[3]["count"]}
    unattr = int((clean["crm"]["channel"] == "Unattributed").sum())

    payload = {"market": market, "totals": totals, "channels": ch, "weekly": wk, "funnel": fun,
               "email": em, "email_trend": em_trend, "ab": test, "audit": log + market["checks"],
               "recon": recon, "unattributed": unattr, "recs": recs}
    (ROOT / "insights.json").write_text(json.dumps(payload, indent=2, default=str))
    tpl = (ROOT / "template.html").read_text()
    (ROOT / "index.html").write_text(tpl.replace("__DATA__", json.dumps(payload, default=str)))
    print("Dashboard written to index.html")


if __name__ == "__main__":
    main()
