# Paprika för Home Assistant

Vi planerar maten och skriver inköpslistan i [Paprika Recipe Manager](https://www.paprikaapp.com/), men resten av huset sköts i Home Assistant. Den här integrationen kopplar ihop dem. Veckans måltider hamnar i en kalender, inköpslistan och köksskåpet blir att göra-listor som går att ändra från HA, och recepten går att söka i, hämta och skapa med tjänster.

*In English: an unofficial Home Assistant integration for Paprika Recipe Manager 3. It adds the meal plan as a calendar, the grocery list and pantry as editable to-do lists, and services to search, read, create and update recipes. You sign in with your Paprika Cloud Sync email and password. The setup form and services are translated to English and Swedish; this README is in Swedish.*

Integrationen är inofficiell och har ingen koppling till Hindsight Labs, som gör Paprika. Den pratar med samma synk-API som apparna använder. API:t är inte dokumenterat och kan ändras när som helst, och det svarar bara på anrop som ser ut att komma från en Paprika-app, så integrationen skickar Mac-appens User-Agent.

## Det här får du

- `calendar.paprika_meal_plan` med måltidsplanen.
- `todo.paprika_groceries`, inköpslistan. Den går att läsa och ändra.
- `todo.paprika_pantry`, köksskåpet. Den går också att läsa och ändra.
- Fyra tjänster för recept: sök, hämta, skapa och ändra.
- Sensorer för nästa måltid, antal måltider i dag och antal recept. `sensor.recipe_preview` har de 15 senast tillagda recepten som attribut.

## Installation

Med HACS: öppna HACS, välj ⋮ och *Anpassade förråd*, lägg till `https://github.com/pwassvik-png/paprika-ha` som typen *Integration*, installera *Paprika Recipe Manager* och starta om Home Assistant.

Utan HACS: kopiera mappen `custom_components/paprika/` till `config/custom_components/` och starta om.

Lägg sedan till integrationen under Inställningar → Enheter och tjänster → Lägg till integration → Paprika. Du loggar in med samma e-post och lösenord som för Paprika Cloud Sync. Formuläret provar inloggningen direkt, så du får veta på en gång om lösenordet är fel.

Lösenordet sparas i integrationens inställningar i Home Assistant, precis som för andra integrationer. Vill du byta det väljer du ⋮ → *Konfigurera om* på integrationen. Om Paprika slutar godta lösenordet frågar Home Assistant efter ett nytt.

Du behöver Home Assistant 2024.11 eller senare.

## Inköpslistan och köksskåpet

Båda listorna dyker upp under Att göra i sidomenyn. De fungerar med todo-kortet (`type: todo-list`) och med Assist, och du kan styra dem med `todo.add_item`, `todo.update_item` och `todo.remove_item`. En ändring i HA syns i Paprika-apparna nästan direkt, eftersom integrationen ber apparna synka (`sync/notify/`). I HA syns den med en gång, utan att vänta på nästa hämtning.

### Inköpslistan (`todo.paprika_groceries`)

| I HA | I Paprika |
|---|---|
| Vara | `name` |
| Bocka av | `purchased: true`, och varan försvinner ur listan i HA |
| Ta bort | Samma sak som att bocka av (se nedan) |

Nya varor hamnar på samma lista som de som redan finns (`list_uid`).

### Köksskåpet (`todo.paprika_pantry`)

| I HA | I Paprika |
|---|---|
| Vara | `ingredient` |
| Bockad | Slut, `in_stock: false` |
| Beskrivning | Mängd, `quantity` |
| Förfallodatum | Bäst före, `expiration_date` och `has_expiration` |
| Ta bort | Tas bort på riktigt, `deleted: true` |

En ny vara läggs in som "finns hemma", med dagens datum som inköpsdatum. Det som finns hemma visas först, i bokstavsordning. Platser (`location_uid`) och anteckningar (`notes`) visas inte i HA, men de skrivs inte över när du ändrar en vara.

## Måltidsplanen

Paprika sparar bara datum för en måltid, ingen tid. I kalendern lägger integrationen därför lunch kl. 12.30 och middag kl. 17.30. Andra måltidstyper får den tid som är inställd för typen i Paprika. Alla måltider blir en timme långa.

## Recept

Det finns för många recept, och de är för långa, för att få plats i en entitet. Därför når du dem via tjänster som returnerar data. Använd `response_variable` i skript och automationer, eller prova dem under Utvecklarverktyg → Åtgärder.

| Tjänst | Vad den gör |
|---|---|
| `paprika.search_recipes` | Söker på namn (`query`) och, om du vill, i ingredienserna (`in_ingredients`). Svarar med `count` och en kort lista med `uid`, `name`, `categories`, `rating`, `favorite`, `servings` och `total_time`. En tom `query` listar alla recept. |
| `paprika.get_recipe` | Hämtar ett helt recept. `ingredients` och `directions` kommer som listor och kategorierna som namn. |
| `paprika.create_recipe` | Skapar ett recept. Bara `name` krävs. `ingredients` och `directions` kan vara text med en rad per post, eller en lista. |
| `paprika.update_recipe` | Ändrar de fält du anger och låter resten vara. |

I fältet `recipe` kan du skriva receptets uid, hela namnet eller en del av namnet. Om delen matchar flera recept får du ett fel som räknar upp dem. `categories` anges med namnen på kategorier som redan finns i Paprika. Recept i papperskorgen kommer inte med i sökningen om du inte sätter `include_trash: true`.

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

Integrationen sparar alla recept i en cache (`.storage/paprika_recipes_<entry>`), så en omstart behöver inte hämta allt igen. Vid varje uppdatering hämtas bara de recept som har ändrats sedan sist, högst två åt gången.

Paprika svarar `429 Too Many Requests` om man frågar för mycket på kort tid. Det hände mig när jag startade om HA två gånger i rad innan cachen fanns: integrationen kom inte igång förrän spärren släppte, efter ungefär tio minuter. Om det bara är recepten som inte går att uppdatera loggas en varning, och allt annat fortsätter fungera med de recept som redan finns i cachen.

## Det här fungerar inte än

- Det går inte att ta bort en vara från inköpslistan på riktigt. API:t svarar 404 på `DELETE` och bryr sig inte om `deleted`, så när du tar bort en vara i HA bockas den av i stället.
- Köksskåpets platser (`pantrylocations`) stöds inte.
- Recept går inte att ta bort eller lägga i papperskorgen via tjänsterna. Foton stöds inte, och det går inte att skapa nya kategorier.
- När en tjänst får fel indata svarar HA:s REST-API med 500 i stället för 400. Felmeddelandet syns ändå i gränssnittet och i loggen.
- Integrationen hämtar hela listorna vid varje uppdatering, inte bara det som har ändrats.

## Om Paprikas API

Det här har jag testat mot ett riktigt konto. Inget av det är dokumenterat av Paprika.

- Inloggning: `POST account/login/` med formulärfälten `email` och `password` ger en bearer-token. Apparna skickar också med ett App Store-kvitto (`receipt`), men det behövs inte. API:t vill ha en User-Agent från en officiell Paprika-app.
- Läsa: `GET sync/<resurs>/`, till exempel `groceries/`, `pantry/`, `meals/` och `categories/`. `sync/status/` ger antal per resurs, men siffrorna stämmer inte med listorna, så lita inte på dem.
- Recept: `GET sync/recipes/` ger bara `uid` och `hash` för varje recept. Hela receptet hämtar du med `GET sync/recipe/<uid>/`. `ingredients` och `directions` är fritext med radbrytningar, och `categories` är en lista med kategoriernas uid.
- Skriva: `POST sync/<resurs>/` med en gzippad JSON-array av hela objekt i multipart-fältet `data`, och sedan `POST sync/notify/` så att apparna synkar. Nya objekt behöver ett uid i versaler. Recept skrivs ett i taget, som ett objekt och inte en array, till `POST sync/recipe/<uid>/`. Skicka med en ny `hash` (sha256 av receptet), annars märker apparna inte ändringen. Servern sparar den hash du skickar och returnerar den.
- Ta bort: `"deleted": true` i objektet fungerar för `pantry/` och `recipe/<uid>/`, men inte för `groceries/`. `DELETE` ger 404 eller 405. Ett recept hamnar i papperskorgen med `in_trash: true`.

## Utveckling

Testerna i `tests/` går att köra utan att Home Assistant är installerat:

```bash
for t in tests/test_api.py tests/test_recipes.py tests/test_todo_compatibility.py; do python3 "$t"; done
```

`tests/test_util.py` behöver Home Assistant och körs med pytest.

Vad som har ändrats, och varför, står i [CHANGELOG.md](CHANGELOG.md).

## Licens

MIT. Se [LICENSE](LICENSE).
