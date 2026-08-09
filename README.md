# Preservation Evoker – Discord Source Posts

Diese Version enthält bewusst **nur vier Discord-Posts**:

1. Wowhead
2. Icy Veins
3. Method.gg
4. Spiritbloom.pro

Jeder Post zeigt:
- Quelle
- Autor(en)
- letzten bekannten Aktualisierungsstand
- direkten Link zum Guide

## Wichtig beim Umstieg

Die alten Guide-Posts aus der vorherigen Version werden nicht automatisch gelöscht.
Lösche sie einmal manuell in Discord.

Wenn du auch `data/discord_state.json` aus der alten Version im Repository hast,
ersetze sie durch die neue leere Datei aus diesem Paket.

Danach den Workflow einmal manuell starten:

`Actions → Sync Preservation Evoker Sources → Run workflow`

Beim ersten Lauf werden vier neue Posts erstellt. Danach werden dieselben vier
Posts bei Änderungen nur noch aktualisiert.

## Pflege

Alle sichtbaren Informationen liegen in:

`data/sources.json`

Dort kannst du Autor, Datum, Hinweis und Links ändern.
