import json, requests
from ics import Calendar

# Charger la config
with open("config.json") as f:
    config = json.load(f)

url = config["uvsq_url"]

# Récupérer la page HTML (ici simplifié, le vrai script doit parser Celcat)
# Dans une vraie version, on extraierait les événements et on les transformerait en .ics
# Pour ce pack, on met un exemple minimal

cal = Calendar()
# TODO: Ajouter la logique de parsing de Celcat ici

with open("emploi.ics", "w") as f:
    f.writelines(cal)