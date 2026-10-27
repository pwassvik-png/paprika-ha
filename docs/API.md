# Paprikas synk-API

Anteckningar för den som vill ändra i integrationen. API:t är inte dokumenterat av Paprika; detta är testat mot ett riktigt konto.

- Inloggning: `POST account/login/` med formulärfälten `email` och `password` ger en bearer-token. Apparna skickar också med ett App Store-kvitto (`receipt`), men det behövs inte. API:t vill ha en User-Agent från en officiell Paprika-app.
- Läsa: `GET sync/<resurs>/`, till exempel `groceries/`, `pantry/`, `meals/` och `categories/`. `sync/status/` ger antal per resurs, men siffrorna stämmer inte med listorna, så lita inte på dem.
- Recept: `GET sync/recipes/` ger bara `uid` och `hash` för varje recept. Hela receptet hämtar du med `GET sync/recipe/<uid>/`. `ingredients` och `directions` är fritext med radbrytningar, och `categories` är en lista med kategoriernas uid.
- Skriva: `POST sync/<resurs>/` med en gzippad JSON-array av hela objekt i multipart-fältet `data`, och sedan `POST sync/notify/` så att apparna synkar. Nya objekt behöver ett uid i versaler. Recept skrivs ett i taget, som ett objekt och inte en array, till `POST sync/recipe/<uid>/`. Skicka med en ny `hash` (sha256 av receptet), annars märker apparna inte ändringen. Servern sparar den hash du skickar och returnerar den.
- Ta bort: `"deleted": true` i objektet fungerar för `pantry/` och `recipe/<uid>/`, men inte för `groceries/`. `DELETE` ger 404 eller 405. Ett recept hamnar i papperskorgen med `in_trash: true`.

