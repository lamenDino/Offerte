# Bot Telegram per Giochi Gratuiti

Bot Telegram che monitora automaticamente giochi gratuiti da diverse piattaforme e li pubblica ogni ora.

## Funzionalità

- **Monitoraggio automatico ogni ora** di:
  - Epic Games Store
  - Steam (tramite IsThereAnyDeal)
  - GamerPower
  - Twitch Prime Gaming
  - GOG
  - Battle.net (placeholder)
  - Riot Games (placeholder)

- **Anti-duplicati**: Traccia i giochi già inviati per evitare spam
- **Validazione link**: Verifica che i link siano accessibili
- **Descrizioni in italiano**: Ogni gioco include una breve descrizione
- **Date di scadenza**: Formattate in stile italiano (dd/mm/yyyy)
- **Health check**: Endpoint per monitorare lo stato del servizio

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

## File generati

- `sent_games.json`: Traccia dei giochi già inviati per evitare duplicati
- `/var/log/cron.log`: Log delle esecuzioni programmate

## Funzionalità anti-spam

Il bot mantiene un file JSON con gli ID univoci dei giochi già inviati. Ogni piattaforma ha un formato ID specifico:
- Epic: `epic_{slug}`
- Steam: `steam_{hash(link)}`
- GamerPower: `gp_{id}`
- Prime Gaming: `prime_{titolo_normalizzato}`
- GOG: `gog_{titolo_normalizzato}`

Questo garantisce che lo stesso gioco non venga mai inviato due volte.

## Scheduling

Il cron job è configurato per eseguire lo script ogni ora (0 * * * *).
Il container rimane attivo grazie al health check server sulla porta 8080.