# Bot Telegram per Giochi Gratuiti

Bot Telegram che monitora automaticamente giochi gratuiti da diverse piattaforme e li pubblica ogni ora con collage di immagini.

## Funzionalità Principali

🎮 **Monitoraggio automatico ogni ora** di:
- Epic Games Store
- GamerPower
- Steam (tramite IsThereAnyDeal)
- GOG
- Twitch Prime Gaming

🚫 **Anti-duplicati cross-platform**: Nightingale da Epic Games e "Nightingale Giveaway" da GamerPower vengono riconosciuti come lo stesso gioco

🖼️ **Collage immagini automatico**: Crea un'immagine unica con tutte le copertine dei giochi

🌍 **Traduzioni automatiche**: Descrizioni sempre in italiano

🎨 **Formattazione professionale**: Con icone e layout accattivante

## Setup

1. **Variabili d'ambiente** (crea un file `.env`):
   ```
   BOT_TOKEN=il_tuo_bot_token_telegram
   CHANNEL_USERNAME=@nome_del_tuo_canale
   FRIENDS_CHAT_ID=id_della_chat_amici  # Opzionale
   ```

2. **Build e run con Docker**:
   ```bash
   docker build -t games-bot .
   docker run -d --env-file .env -p 8080:8080 games-bot
   ```

3. **Deploy su Render**:
   - Collega il repository GitHub
   - Imposta le variabili d'ambiente nel dashboard Render
   - Il servizio si avvierà automaticamente

## Monitoraggio

- **Health check**: `http://localhost:8080/` - Verifica stato servizio
- **Log cron**: `http://localhost:8080/logs` - Visualizza log delle esecuzioni

## Formato Messaggio

```
🎮 Nuovi Giochi Gratuiti 🎮

[COLLAGE IMMAGINI COPERTINE]

🔹 **Nightingale**
📖 _Gioco di sopravvivenza cooperativo in prima persona ambientato nei pericolosi Reami delle Fate._
🏷️ _Sopravvivenza_ • 🏢 _Epic Games_
⏰ _Scade: 09/10/2025 alle 15:00_
▶️ [Scarica Gratis](https://store.epicgames.com/it/p/nightingale)

🔹 **Zomborg**
📖 _Sparatutto dall'alto ambientato in un mondo pieno di zombie con grafica accattivante._
🏷️ _Azione_ • 🏢 _GamerPower_
⏰ _Scade: 06/10/2025 alle 23:59_
▶️ [Scarica Gratis](...)
```

## Funzionalità Anti-Duplicati

Il bot utilizza normalizzazione intelligente dei titoli:

- "Nightingale" (Epic Games) → `game_nightingale`
- "Nightingale Giveaway" (GamerPower) → `game_nightingale`
- "Nightingale (Epic Games)" → `game_nightingale`

Risultato: **Un solo messaggio per gioco**, indipendentemente dalla piattaforma.

## File generati

- `sent_games.json`: Traccia dei giochi già inviati
- `games_collage.png`: Immagine temporanea con copertine (viene eliminata dopo invio)
- `/var/log/cron.log`: Log delle esecuzioni programmate

## Traduzioni Automatiche

Pattern inglese → italiano:
- "free game" → "gioco gratuito"  
- "survival crafting" → "sopravvivenza costruzione"
- "don't miss it" → "non perdertelo"
- "check it out" → "provalo"

## Scheduling

- Cron job ogni ora: `0 * * * *`
- Container sempre attivo con health check su porta 8080
- Invio garantito solo con collage immagini (se collage fallisce, non invia nulla)