# Paprika Integration (Custom)

Egen integration som kopplar **Paprika Recipe Manager** till Home Assistant. Vad som har ändrats och varför står i [CHANGELOG.md](CHANGELOG.md). Integrationen ger:

- Sensorer för nästa måltid, antal måltider idag och antal recept (`sensor.recipe_total`; `sensor.recipe_preview` har de 15 senast tillagda recepten som attribut).
- Kalender (`calendar.paprika_meal_plan`) med Paprikas måltidsplan.
- Inköpslistan (`todo.paprika_groceries`), läs och skriv.
- Köksskåpet (`todo.paprika_pantry`), läs och skriv.
- Recept via tjänster: sök, hämta, skapa och ändra.

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

## Recept

Recepten är för många och för långa för en entitet, så de nås via tjänster som returnerar data (`response_variable` i skript och automationer, eller **Utvecklarverktyg → Åtgärder**).

| Tjänst | Gör |
|---|---|
| `paprika.search_recipes` | Söker på namn (`query`), valfritt även i ingredienser (`in_ingredients`). Ger `count` och en kort lista (`uid`, `name`, `categories`, `rating`, `favorite`, `servings`, `total_time`). Tom `query` listar alla. |
| `paprika.get_recipe` | Hela receptet; `ingredients` och `directions` som listor, kategorier som namn. |
| `paprika.create_recipe` | Skapar ett recept. `name` krävs; `ingredients`/`directions` som text med en rad per post eller som lista. |
| `paprika.update_recipe` | Ändrar bara de fält som anges. |

`recipe` kan vara uid, exakt namn eller en del av namnet som bara matchar ett recept; annars får man ett fel som räknar upp träffarna. `categories` anges med namn på befintliga Paprika-kategorier. Recept i papperskorgen döljs i sökningen om inte `include_trash: true`.

```yaml
- action: paprika.search_recipes
  data:
    query: kyckling
    limit: 5
  response_variable: hits
- action: paprika.get_recipe
  data:
    recipe: "{{ hits.recipes[0].uid }}"
  response_variable: recept
```

Integrationen håller en cache med alla recept som sparas i `.storage/paprika_recipes_<entry>`, så att en omstart inte hämtar alla recept igen. Vid varje uppdatering och tjänsteanrop hämtas bara recept vars `hash` har ändrats, högst två åt gången. Paprika svarar **429 Too Many Requests** om man hämtar för mycket på kort tid. Om recepten inte går att uppdatera loggas en varning, och resten av integrationen fortsätter fungera med de recept som redan finns i cachen.

## Begränsningar / TODO

- Inköpslistan saknar riktig borttagning i API:t (`DELETE` ger 404 och `deleted` ignoreras), så borttagning i HA bockar av varan.
- Köksskåpets platser (`pantrylocations`) stöds inte än.
- Recept: ingen tjänst för att ta bort eller lägga i papperskorgen, inga foton, och nya kategorier kan inte skapas.
- REST-API:t svarar 500 i stället för 400 när en tjänst ger ett valideringsfel; meddelandet syns i HA:s gränssnitt och loggen.
- Delta-synk saknas: data hämtas som hel dataset vid varje uppdatering.
- LibreSSL-varning från `urllib3` i development-miljön är känd men påverkar inte funktionalitet.

## API-anteckningar

Paprikas `api/v2` är inofficiellt; detta är vad vi har verifierat mot det riktiga kontot.

- Inloggning: `POST account/login/` (formulär med `email`, `password`, `receipt`) ger en bearer-token. API:t kräver en officiell Paprika-`User-Agent`.
- Läsning: `GET sync/<resurs>/`, t.ex. `groceries/`, `pantry/`, `meals/`, `categories/`. `sync/status/` ger antal per resurs, men siffrorna stämmer inte med listorna (t.ex. `pantry: 255` när listan har 7 varor, `recipes: 674` när de är 233).
- Recept: `GET sync/recipes/` ger bara `uid` och `hash`; hela receptet hämtas med `GET sync/recipe/<uid>/`. `ingredients` och `directions` är fritext med radbrytningar, `categories` en lista med kategori-uid.
- Skrivning: `POST sync/<resurs>/` med en gzippad JSON-**array** av hela objekt i multipart-fältet `data`, följt av `POST sync/notify/` så att apparna synkar. Nya objekt behöver en uid i versaler. Recept skrivs ett i taget som ett **objekt** (inte array) till `POST sync/recipe/<uid>/`, med en ny `hash` (sha256 av receptet) så att apparna ser ändringen; servern sparar och returnerar den hash vi skickar.
- Borttagning: `"deleted": true` i objektet fungerar för `pantry/` och `recipe/<uid>/` men ignoreras för `groceries/`. `DELETE` ger 404 eller 405. För recept lägger `in_trash: true` receptet i papperskorgen.

## Utveckling

Testerna ligger under `custom_components/paprika/tests/`. `test_todo_compatibility.py` och `test_recipes.py` kan köras utan HA installerat, t.ex. `python3 tests/test_recipes.py`.

### Driftsättning

1. Kontrollera att filerna på HA är desamma som i senaste commiten (t.ex. med `md5sum`), så att inget som bara finns på HA skrivs över.
2. Ta en backup: `sudo cp -a /config/custom_components/paprika /config/paprika.bak-<datum>`.
3. Kopiera ändrade filer till `/config/custom_components/paprika/` (`scp -O` till `/tmp`, sedan `sudo cp`).
4. `ha core check && ha core restart`. En custom-integration kräver omstart, inte bara omladdning.
5. Kontrollera att integrationen har läst in (`loaded`, inte `setup_retry`) och att entiteterna har värden.

Starta inte om HA flera gånger i snabb följd och låt bli att köra loopar mot API:t. Paprika svarar då 429, och integrationen startar inte förrän gränsen har släppt. Kontrollera det med ett enda anrop till `sync/status/` innan nästa omstart.
