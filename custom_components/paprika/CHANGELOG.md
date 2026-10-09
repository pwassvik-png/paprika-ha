# Ändringslogg

Hur integrationen fungerar står i [README.md](README.md). Här står vad som har ändrats och varför.

## 2026-10-08 – Recept och rättade receptsensorer (`26eb154`)

**Nytt**
- Tjänsterna `paprika.search_recipes`, `paprika.get_recipe`, `paprika.create_recipe` och `paprika.update_recipe`. Sök- och hämtningstjänsterna returnerar data; skapa och ändra returnerar det sparade receptet om man ber om det.
- `recipes.py` håller logiken utan beroenden till HA (sökning, uppslag på namn, fältmappning, hash, cache), och `services.py` registrerar tjänsterna.
- Receptcache som sparas i `.storage/paprika_recipes_<entry>`. Bara recept vars `hash` har ändrats hämtas om, högst två åt gången.

**Rättat**
- `sensor.recipe_total` visade `status/`-siffran 674, som inte stämmer. Den räknar nu aktiva recept i cachen (227 av 233; 6 ligger i papperskorgen).
- `sensor.recipe_preview` visade tomma namn eftersom `sync/recipes/` bara ger `uid` och `hash`. Den visar nu de 15 senast tillagda recepten med namn, kategorinamn och bild-URL.

**Incident under driftsättningen**
Den första versionen höll cachen bara i minnet, så varje omstart hämtade alla 233 recept. Två omstarter efter varandra, plus utforskningen av API:t samma dag, gav **429 Too Many Requests**. Integrationen hamnade i `setup_retry` och inköpslistan, köksskåpet, måltidsplanen och sensorerna var otillgängliga i ungefär 10 minuter. Därför:
- sparas cachen nu på disk,
- har antalet samtidiga hämtningar sänkts från 8 till 2,
- loggar ett fel vid receptuppdateringen bara en varning; resten av koordinatorns data uppdateras ändå, och recept som hann hämtas sparas.

Backup före ändringen: `/config/paprika.bak-20261008-recept`.

## 2026-10-08 – Dokumentation (`741daf9`)

README:n skrevs om. Den sa att inköpslistan var skrivskyddad, vilket inte stämde efter 2026-10-03. Nu beskriver den listorna, API-anteckningarna och driftsättningen. En hänvisning till `paprika_test.py`, som inte fanns, togs bort.

## 2026-10-08 – Köksskåpet som att göra-lista (`ed4f15c`)

**Nytt**
- `todo.paprika_pantry` speglar Paprikas köksskåp (`sync/pantry/`) och går att läsa och skriva: lägga till, byta namn, bocka av och ta bort.
- Bockad betyder slut (`in_stock: false`), beskrivningen är mängden (`quantity`) och förfallodatumet är bäst före (`expiration_date`).
- Borttagning är riktig (`"deleted": true`), till skillnad från inköpslistan, där API:t ignorerar flaggan.
- Gemensam hjälpfunktion som visar ändringar i HA direkt i stället för efter den debouncade omhämtningen (10 s), för båda listorna.

**Verifierat** genom att lägga till, bocka av och ta bort en testvara via HA:s tjänster och kontrollera varje steg direkt i Paprikas API.

Backup före ändringen: `/config/paprika.bak-20261008`.

## 2026-10-03 – Skrivstöd för inköpslistan (`4df5f1c`)

`todo.paprika_groceries` går att skriva till: lägga till, bocka av och byta namn. Borttagning bockar av varan eftersom API:t saknar riktig borttagning för inköpslistan.

## 2026-10-03 – Import (`f5bad30`)

Integrationen importerades till git som den låg på HA.
