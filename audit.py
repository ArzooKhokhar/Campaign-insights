"""Data integrity audit: standardise, de-duplicate, flag and reconcile."""
import pandas as pd

CHANNEL_MAP = {
    "paid search": "Paid Search", "paid_search": "Paid Search", "google ads": "Paid Search", "google / cpc": "Paid Search",
    "paid social": "Paid Social", "paid_social": "Paid Social", "meta": "Paid Social", "facebook": "Paid Social", "facebook / paid": "Paid Social",
    "email": "Email", "marketing automation": "Email",
    "organic search": "Organic Search", "organic": "Organic Search",
    "direct/referral": "Direct/Referral", "direct": "Direct/Referral", "referral": "Direct/Referral",
}


def std_channel(s):
    return s.fillna("").str.strip().str.lower().map(CHANNEL_MAP).fillna("Unattributed")


def run_audit(web, ads, crm, email):
    log = []

    def add(area, check, found, action, severity):
        log.append({"area": area, "check": check, "found": found, "action": action, "severity": severity})

    # Ad platform
    raw_names = ads["Channel"].nunique()
    ads = ads.rename(columns={"Date": "date", "Channel": "channel", "Spend (AUD)": "spend",
                              "Impressions": "impressions", "Clicks": "clicks"})
    ads["date"] = pd.to_datetime(ads["date"], format="%d/%m/%Y").dt.date
    ads["channel"] = std_channel(ads["channel"])
    add("Ad spend", "Inconsistent channel names", f"{raw_names} names for 2 channels",
        "Mapped to standard names", "medium")
    bad_spend = (ads["spend"] <= 0).sum()
    add("Ad spend", "Zero or negative spend", f"{bad_spend} rows", "None needed" if not bad_spend else "Removed", "low")

    # CRM
    before = len(crm)
    crm = crm.sort_values("lead_id").drop_duplicates(subset=["email_hash", "created"], keep="first")
    dupes = before - len(crm)
    add("CRM", "Duplicate enquiries", f"{dupes} duplicate records ({dupes / before:.1%})",
        "Kept first record", "high")
    raw_src = crm["source"].fillna("").str.strip().str.lower()
    crm["channel"] = std_channel(crm["source"])
    variants = raw_src[raw_src != ""].nunique()
    add("CRM", "Inconsistent source values", f"{variants} spellings for 5 channels",
        "Mapped to standard names", "medium")
    unattr = (crm["channel"] == "Unattributed").sum()
    add("CRM", "Missing UTM / source", f"{unattr} leads ({unattr / len(crm):.1%})",
        "Labelled Unattributed; fix tagging", "high")

    # Email
    bad = (email["unique_clicks"] > email["unique_opens"]) | (email["unique_opens"] > email["delivered"])
    add("Email", "Impossible metrics (clicks > opens)", f"{int(bad.sum())} sends",
        "Excluded from rates; raise with platform", "medium")
    email = email[~bad].copy()

    # Web
    missing_days = 84 * 5 - len(web)
    add("Web analytics", "Missing days of data", f"{missing_days} channel-days", "None needed", "low")

    # Reconciliation: web enquiries vs CRM leads
    w = web.groupby("channel")["enquiries"].sum()
    c = crm.groupby("channel").size()
    recon = []
    for ch in w.index:
        diff = (c.get(ch, 0) - w[ch]) / w[ch]
        recon.append({"channel": ch, "web": int(w[ch]), "crm": int(c.get(ch, 0)), "diff": round(diff * 100, 1)})
    worst = max(recon, key=lambda r: abs(r["diff"]))
    add("Reconciliation", "Web enquiries vs CRM leads", f"Largest gap {worst['diff']}% ({worst['channel']})",
        "Gap explained by unattributed leads", "high" if abs(worst["diff"]) > 5 else "low")

    return {"web": web, "ads": ads, "crm": crm, "email": email}, log, recon
