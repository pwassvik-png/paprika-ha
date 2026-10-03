# Paprika Integration (Custom)

This custom integration syncs data from **Paprika Recipe Manager** into Home Assistant. It currently exposes:

- Sensors for nästa måltid, antal måltider idag och totalt antal recept.
- Kalender (`calendar.paprika_meal_plan`) med Paprikas måltidsplan.
- To-do list entity (`todo.paprika_groceries`) som visar aktiva inköpsposter (read-only i nuläget).

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

- Paprikas inofficiella API dokumenterar inte skrivoperationer. To-do entiteten är därför read-only tills vi kan sniffa korrekt payload.
- Delta-synk saknas: data hämtas som hel dataset vid varje uppdatering.
- LibreSSL-varning från `urllib3` i development-miljön är känd men påverkar inte funktionalitet.

## Utveckling

Följ `paprika_test.py` för ett fristående röktest (läser Paprika-kontot från `secrets.yaml` om miljövariabler saknas). Testerna ligger under `custom_components/paprika/tests/`.
