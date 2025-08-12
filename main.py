# UVSQ Celcat -> ICS (Europe/Paris)
# Fenêtre: J-30 à J+120. Ecrit emploi.ics

import requests, hashlib, html, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_URL = "https://edt.uvsq.fr/Home/GetCalendarData"

PAYLOAD_BASE = {
    "resType": "103",
    "calView": "month",
    "federationIds[]": "DFASM1",
    "colourScheme": "3",
}

PARIS = ZoneInfo("Europe/Paris")

def fold_ics_line(line: str) -> str:
    # RFC5545: lines ≤75 octets; on plie grossièrement sur 73 chars
    out, chunk = [], line
    while len(chunk.encode("utf-8")) > 75:
        # coupe à ~73 chars (approx. safe pour UTF-8 court)
        cut = 73
        out.append(chunk[:cut])
        chunk = " " + chunk[cut:]
    out.append(chunk)
    return "\r\n".join(out)

def esc(s: str) -> str:
    if s is None:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<br\s*/?>", "\\n", s, flags=re.I)
    s = re.sub(r"<.*?>", "", s)  # retire tags restants
    s = s.replace("\\", "\\\\").replace("\r\n", "\\n").replace("\n", "\\n")
    s = s.replace(",", r"\,").replace(";", r"\;")
    return s.strip()

def iso_to_paris(iso_s: str) -> datetime:
    # Celcat renvoie "YYYY-MM-DDTHH:MM:SS" sans TZ -> on considère Europe/Paris
    dt = datetime.strptime(iso_s, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=PARIS)

def fmt_local(dt: datetime) -> str:
    # format ICS local avec TZID (pas de Z)
    return dt.strftime("%Y%m%dT%H%M%S")

def make_uid(ev: dict) -> str:
    base = f"{ev.get('id')}|{ev.get('start')}|{ev.get('end')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest() + "@uvsq"

def build_event(ev: dict) -> str:
    start = iso_to_paris(ev["start"])
    end = iso_to_paris(ev["end"])

    desc = ev.get("description") or ""
    summary = esc(desc.split("\\n", 1)[0] or "Cours")
    description = esc(desc)

    # Lieu
    sites = ev.get("sites") or []
    if isinstance(sites, list):
        location = esc(", ".join(sites))
    else:
        location = esc(str(sites))

    cat = esc(ev.get("eventCategory") or "")
    dept = esc(ev.get("department") or "")
    fac = esc(ev.get("faculty") or "")
    mods = ev.get("modules")
    if mods:
        try:
            mods = ", ".join([str(m) for m in mods])
        except Exception:
            mods = str(mods)
    extra = []
    if dept: extra.append(f"Département: {dept}")
    if fac: extra.append(f"UFR: {fac}")
    if cat: extra.append(f"Catégorie: {cat}")
    if mods: extra.append(f"Modules: {mods}")
    if extra:
        description = (description + "\\n\\n" + "\\n".join(extra)).strip()

    uid = make_uid(ev)
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;TZID=Europe/Paris:{fmt_local(start)}",
        f"DTEND;TZID=Europe/Paris:{fmt_local(end)}",
        f"SUMMARY:{summary}" if summary else "SUMMARY:Événement",
    ]
    if description:
        lines.append("DESCRIPTION:" + description)
    if location:
        lines.append("LOCATION:" + location)
    if cat:
        lines.append("CATEGORIES:" + cat)
    lines.append("END:VEVENT")

    # pliage des lignes longues
    return "\r\n".join(fold_ics_line(l) for l in lines)

def fetch_events(start_date: datetime, end_date: datetime) -> list[dict]:
    data = {
        **PAYLOAD_BASE,
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d"),
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://edt.uvsq.fr",
        "Referer": "https://edt.uvsq.fr/",
    }
    r = requests.post(BASE_URL, data=data, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    today = datetime.now(PARIS).date()
    start = datetime.combine(today - timedelta(days=30), datetime.min.time()).replace(tzinfo=PARIS)
    end = datetime.combine(today + timedelta(days=120), datetime.min.time()).replace(tzinfo=PARIS)

    events = fetch_events(start, end)

    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UVSQ Exporter//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "NAME:UVSQ DFASM1",
        "X-WR-CALNAME:UVSQ DFASM1",
        "X-WR-TIMEZONE:Europe/Paris",
    ])
    body = []
    for ev in events:
        try:
            body.append(build_event(ev))
        except Exception as e:
            # on ignore l'événement fautif plutôt que de casser tout le flux
            continue

    ics = header + "\r\n" + "\r\n".join(body) + "\r\nEND:VCALENDAR\r\n"

    with open("emploi.ics", "w", encoding="utf-8") as f:
        f.write(ics)

if __name__ == "__main__":
    main()
