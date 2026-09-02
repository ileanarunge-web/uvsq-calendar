# UVSQ Celcat -> ICS (Europe/Paris)
# Fenêtre: J-30 à J+120.
# Usage :
#   python main.py DFASM1 emploi_dfasm1.ics
#   python main.py DFASM2 emploi_dfasm2.ics
#
# Sans argument : DFASM1 / emploi.ics (comportement historique)

import sys
import requests, hashlib, html, re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE_URL = "https://edt.uvsq.fr/Home/GetCalendarData"

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



def parse_description(raw_desc: str, category: str) -> tuple[list[str], str]:
    """
    Le champ 'description' brut de Celcat encode plusieurs infos dans un
    seul bloc de texte HTML, séparées par des <br />, dans un ordre fixe :
    [catégorie, salle(s)..., (vide), "GROUPE [GROUPE]", titre/notes, (vide)]
    Cette fonction extrait la liste des salles et le titre/notes utile.
    """
    if not raw_desc:
        return [], ""

    text = html.unescape(raw_desc)
    blocks = [b.replace("\r", "").replace("\n", "").strip() for b in text.split("<br />")]

    idx = 0
    if blocks and blocks[0].lower() == (category or "").lower():
        idx = 1

    rooms = []
    while idx < len(blocks) and blocks[idx] != "":
        rooms.append(blocks[idx])
        idx += 1

    while idx < len(blocks) and blocks[idx] == "":
        idx += 1

    if idx < len(blocks) and re.match(r"^.+\[.+\]$", blocks[idx]):
        idx += 1

    while idx < len(blocks) and blocks[idx] == "":
        idx += 1

    title_parts = [b for b in blocks[idx:] if b]
    title = " – ".join(title_parts)

    return rooms, title


def build_event(ev: dict) -> str:
    start = iso_to_paris(ev["start"])
    end = iso_to_paris(ev["end"])

    category = ev.get("eventCategory") or ""
    rooms, title = parse_description(ev.get("description"), category)

    # Si Celcat ne renvoie pas de description exploitable, on se rabat
    # sur le champ structuré 'sites' quand il existe.
    if not rooms:
        sites = ev.get("sites") or []
        rooms = sites if isinstance(sites, list) else [str(sites)]

    location = ", ".join(rooms)

    if category and title:
        summary = f"{category} – {title}"
    elif title:
        summary = title
    elif category:
        summary = category
    else:
        summary = "Cours"

    dept = ev.get("department") or ""
    fac = ev.get("faculty") or ""
    mods = ev.get("modules")
    if mods:
        try:
            mods = ", ".join(str(m) for m in mods)
        except Exception:
            mods = str(mods)

    desc_lines = []
    if title:
        desc_lines.append(title)
    if location:
        desc_lines.append(f"Salle(s) : {location}")
    if dept:
        desc_lines.append(f"Département : {dept}")
    if fac:
        desc_lines.append(f"UFR : {fac}")
    if category:
        desc_lines.append(f"Catégorie : {category}")
    if mods:
        desc_lines.append(f"Modules : {mods}")

    description = esc("\n".join(desc_lines))
    summary = esc(summary)
    location = esc(location)
    category = esc(category)

    uid = make_uid(ev)
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;TZID=Europe/Paris:{fmt_local(start)}",
        f"DTEND;TZID=Europe/Paris:{fmt_local(end)}",
        f"SUMMARY:{summary}",
    ]
    if description:
        lines.append("DESCRIPTION:" + description)
    if location:
        lines.append("LOCATION:" + location)
    if category:
        lines.append("CATEGORIES:" + category)
    lines.append("END:VEVENT")

    # pliage des lignes longues
    return "\r\n".join(fold_ics_line(l) for l in lines)


def fetch_events(group: str, start_date: datetime, end_date: datetime) -> list[dict]:
    data = {
        "resType": "103",
        "calView": "month",
        "federationIds[]": group,
        "colourScheme": "3",
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
    group = sys.argv[1] if len(sys.argv) > 1 else "DFASM1"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "emploi.ics"
    
    today = datetime.now(PARIS).date()
    start = datetime.combine(today - timedelta(days=30), datetime.min.time()).replace(tzinfo=PARIS)
    end = datetime.combine(today + timedelta(days=120), datetime.min.time()).replace(tzinfo=PARIS)

    events = fetch_events(group, start, end)

    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UVSQ Exporter//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"NAME:UVSQ {group}",
        f"X-WR-CALNAME:UVSQ {group}",
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

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ics)
        print(f"OK : {len(events)} événements écrits dans {output_file} (groupe {group})")

if __name__ == "__main__":
    main()
