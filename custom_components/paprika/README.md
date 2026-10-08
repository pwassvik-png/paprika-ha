# Paprika Integration (Custom)

This custom integration syncs data from **Paprika Recipe Manager** into Home Assistant. It currently exposes:

- Sensors for nästa måltid, antal måltider idag och totalt antal recept.
- Kalender (`calendar.paprika_meal_plan`) med Paprikas måltidsplan.
- Inköpslistan (`todo.paprika_groceries`), läs och skriv.
- Köksskåpet (`todo.paprika_pantry`), läs och skriv.

## Att göra-listor

Båda listorna syns under **Att göra** i sidomenyn, fungerar med todo-kortet (`type: todo-list`) och Assist, och kan styras med `todo.add_item`, `todo.update_item` och `todo.remove_item`. Ändringar syns i Paprika-apparna direkt (integrationen anropar `sync/notify/`) och i HA utan att vänta på nästa hämtning.

### Inköpslistan – `todo.paprika_groceries`

| I HA | I Paprika |
|---|---|
| Vara | `name` |
| Bocka av | `purchased: true` (varan döljs i HA) |
| Ta bort | samma som bocka av, se nedan |

Nya varor hamnar på samma lista som de befintliga (`list_uid`).

### Köksskåpet – `todo.paprika_pantry`

| I HA | I Paprika |
|---|---|
| Vara | `ingredient` |
| Bockad | slut, `in_stock: false` |
| Beskrivning | mängd, `quantity` |
| Förfallodatum | bäst före, `expiration_date` + `has_expiration` |
| Ta bort | tas bort på riktigt, `deleted: true` |

Nya varor läggs in som i lager med dagens datum som inköpsdatum. Varor i lager visas först, i bokstavsordning. Paprikas platser (`location_uid`) och anteckningar (`notes`) visas inte men bevaras vid ändringar.

## Installation

1. Lägg katalogen `custom_components/paprika/` i Home Assistants `config/`.
2. Lägg in Paprika-inloggningen i `secrets.yaml` (inkl. kvittosträngen från App Store):

   ```yaml
   paprika_email: din@epost.se
   paprika_password: ditt_lösen
   paprika_receipt: <långa kvittosträngen från macOS/iOS>
   ```

3. Starta om Home Assistant och lägg till integrationen via **Inställningar → Enheter & tjänster → Lägg till integration → Paprika**.

> 💡 **Var hittar jag `paprika_receipt`?**  
> Kvittot är den Base64-sträng som Paprika skickar med när appen verifierar ditt Mac/iOS-köp. Hämta den genom att köra Paprika via en MITM-proxy (t.ex. `mitmdump`) och kopiera `receipt`-fältet från `POST /api/v2/account/login/`, eller exportera den via Apples kvittogränssnitt. Spara strängen i `secrets.yaml` så att integrationen kan logga in mot Paprikas `api/v2`-endpoints.

## Begränsningar / TODO

- Inköpslistan saknar riktig borttagning i API:t (`DELETE` ger 404 och `deleted` ignoreras), så borttagning i HA bockar av varan.
- Köksskåpets platser (`pantrylocations`) stöds inte än.
- Delta-synk saknas: data hämtas som hel dataset vid varje uppdatering.
- LibreSSL-varning från `urllib3` i development-miljön är känd men påverkar inte funktionalitet.

## API-anteckningar

Paprikas `api/v2` är inofficiellt; detta är vad vi har verifierat mot det riktiga kontot.

- Inloggning: `POST account/login/` (formulär med `email`, `password`, `receipt`) ger en bearer-token. API:t kräver en officiell Paprika-`User-Agent`.
- Läsning: `GET sync/<resurs>/`, t.ex. `groceries/`, `pantry/`, `meals/`, `recipes/`. `sync/status/` ger antal per resurs, men siffrorna stämmer inte med listorna (t.ex. `pantry: 255` när listan har 7 varor).
- Skrivning: `POST sync/<resurs>/` med en gzippad JSON-**array** av hela objekt i multipart-fältet `data`, följt av `POST sync/notify/` så att apparna synkar. Nya objekt behöver en uid i versaler.
- Borttagning: `"deleted": true` i objektet fungerar för `pantry/` men ignoreras för `groceries/`. `DELETE` ger 404 för båda.

## Utveckling

Testerna ligger under `custom_components/paprika/tests/`. `test_todo_compatibility.py` stubbar HA och kan köras utan HA installerat: `python3 tests/test_todo_compatibility.py`.

### Driftsättning

Ändrade filer kopieras till `/config/custom_components/paprika/` på HA (`scp -O` till `/tmp`, sedan `sudo cp`), följt av `ha core check && ha core restart`. En custom-integration kräver omstart, inte bara omladdning.
