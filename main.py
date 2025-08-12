# Génère un ICS minimal valide. On branchera le vrai parseur Celcat ensuite.

from datetime import datetime

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//UVSQ Exporter//FR
CALSCALE:GREGORIAN
METHOD:PUBLISH
NAME:UVSQ DFASM1
X-WR-CALNAME:UVSQ DFASM1
X-WR-TIMEZONE:Europe/Paris
X-ORIGINAL-GENERATED:{stamp}
END:VCALENDAR
""".replace("\n", "\r\n").format(stamp=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"))

with open("emploi.ics", "w", encoding="utf-8") as f:
    f.write(ICS)
