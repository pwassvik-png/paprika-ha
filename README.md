# Paprika för Home Assistant

Egen integration som kopplar **[Paprika Recipe Manager](https://www.paprikaapp.com/)** till Home Assistant: måltidsplanen som kalender, inköpslistan och köksskåpet som att göra-listor som går att skriva till, och recepten via tjänster.

> **In English:** an unofficial Home Assistant integration for Paprika Recipe Manager 3 – meal plan calendar, read/write grocery and pantry to-do lists, and recipe search/create/update services. Sign in with your Paprika Cloud Sync email and password. The UI is available in English and Swedish.

> ⚠️ **Inofficiell.** Integrationen har ingen koppling till Hindsight Labs. Den använder samma synk-API som Paprika-apparna, som inte är dokumenterat och kan ändras utan förvarning. API:t godtar bara anrop som ser ut att komma från en Paprika-app, så integrationen skickar Mac-appens User-Agent. Använd den på eget ansvar.

## Vad den ger

- Kalender (`calendar.paprika_meal_plan`) med Paprikas måltidsplan.
- Inköpslistan (`todo.paprika_groceries`), läs och skriv.
- Köksskåpet (`todo.paprika_pantry`), läs och skriv.
- Recept via tjänster: sök, hämta, skapa och ändra.
- Sensorer för nästa måltid, antal måltider idag och antal recept (`sensor.recipe_total`; `sensor.recipe_preview` har de 15 senast tillagda recepten som attribut).

## Installation

**HACS:** HACS → ⋮ → *Anpassade förråd* → lägg till `https://github.com/pwassvik-png/paprika-ha` som *Integration* → installera **Paprika Recipe Manager** → starta om Home Assistant.

**Manuellt:** kopiera `custom_components/paprika/` till `config/custom_components/` och starta om Home Assistant.

Lägg sedan till integrationen under **Inställningar → Enheter och tjänster → Lägg till integration → Paprika**. Ange samma e-post och lösenord som du använder för Paprika Cloud Sync. Inloggningen provas direkt, så ett fel lösenord syns i formuläret.

Lösenordet sparas i Home Assistants config entry, som för andra integrationer. Byt lösenord via integrationens meny (⋮ → *Konfigurera om*). Om Paprika slutar godta lösenordet ber Home Assistant om ett nytt.

Kräver Home Assistant 2024.11 eller senare.

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

## Måltidsplanen

Paprika sparar bara ett datum per måltid. I kalendern läggs lunch kl. 12:30 och middag kl. 17:30, och andra måltidstyper på den tid som är inställd för typen i Paprika. Varje måltid blir en timme lång.

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

Integrationen håller en cache med alla recept som sparas i `.storage/paprika_recipes_<entry>`, så att en omstart inte hämtar alla recept igen. Vid varje uppdatering och tjänsteanrop hämtas bara recept vars `hash` har ändrats, högst två åt gången.

**Paprika svarar 429 Too Many Requests** om man hämtar för mycket på kort tid, till exempel vid flera omstarter i rad när cachen är tom. Integrationen startar då inte förrän gränsen har släppt, efter ungefär tio minuter. Om bara recepten inte går att uppdatera loggas en varning, och resten fortsätter med de recept som redan finns i cachen.

## Begränsningar

- Inköpslistan saknar riktig borttagning i API:t (`DELETE` ger 404 och `deleted` ignoreras), så borttagning i HA bockar av varan.
- Köksskåpets platser (`pantrylocations`) stöds inte än.
- Recept: ingen tjänst för att ta bort eller lägga i papperskorgen, inga foton, och nya kategorier kan inte skapas.
- När en tjänst ger ett valideringsfel svarar REST-API:t 500 i stället för 400; meddelandet syns i HA:s gränssnitt och loggen.
- Delta-synk saknas: data hämtas som hela listor vid varje uppdatering.

## API-anteckningar

Paprikas `api/v2` är inofficiellt; detta är vad som har verifierats mot ett riktigt konto.

- Inloggning: `POST account/login/` (formulär med `email` och `password`) ger en bearer-token. Apparna skickar även ett App Store-kvitto (`receipt`), men det behövs inte. API:t kräver en officiell Paprika-`User-Agent`.
- Läsning: `GET sync/<resurs>/`, t.ex. `groceries/`, `pantry/`, `meals/`, `categories/`. `sync/status/` ger antal per resurs, men siffrorna stämmer inte med listorna och går inte att lita på.
- Recept: `GET sync/recipes/` ger bara `uid` och `hash`; hela receptet hämtas med `GET sync/recipe/<uid>/`. `ingredients` och `directions` är fritext med radbrytningar, `categories` en lista med kategori-uid.
- Skrivning: `POST sync/<resurs>/` med en gzippad JSON-**array** av hela objekt i multipart-fältet `data`, följt av `POST sync/notify/` så att apparna synkar. Nya objekt behöver en uid i versaler. Recept skrivs ett i taget som ett **objekt** (inte array) till `POST sync/recipe/<uid>/`, med en ny `hash` (sha256 av receptet) så att apparna ser ändringen; servern sparar och returnerar den hash vi skickar.
- Borttagning: `"deleted": true` i objektet fungerar för `pantry/` och `recipe/<uid>/` men ignoreras för `groceries/`. `DELETE` ger 404 eller 405. För recept lägger `in_trash: true` receptet i papperskorgen.

## Utveckling

Testerna i `tests/` kräver inte att Home Assistant är installerat:

```bash
for t in tests/test_api.py tests/test_recipes.py tests/test_todo_compatibility.py; do python3 "$t"; done
```

`tests/test_util.py` körs med pytest i en miljö där Home Assistant finns.

Vad som har ändrats och varför står i [CHANGELOG.md](CHANGELOG.md).

## Licens

MIT, se [LICENSE](LICENSE).
