# Canale Telegram Automatico per Giochi PC Gratuiti

## File inclusi:
- `requirements.txt` - Dipendenze Python
- `.env` - Variabili di ambiente (MODIFICA PRIMA DI USARE)
- `bot_games_channel.py` - Bot principale per il canale
- `Dockerfile` - Configurazione container Docker
- `start.sh` - Script di avvio con cron

## Setup veloce:

### 1. Configura .env
Modifica il file `.env` con:
```
BOT_TOKEN=il_tuo_token_da_botfather
CHANNEL_USERNAME=@iltuocanalename
```

### 2. Crea canale Telegram
- Nuovo canale pubblico
- Aggiungi il bot comme amministratore
- Permessi: "Invia messaggi"

### 3. Deploy su Render
- Carica tutti i file su GitHub
- Connetti repository a Render
- Crea Web Service
- Aggiungi variabili ambiente in Render Dashboard

### 4. Test
Il bot invierà automaticamente:
- **Ogni giovedì alle 18:00** aggiornamenti completi
- Giochi da Epic Games, Steam, GamerPower
- Formattatzione automatica con link

## Fonti automatiche:
- ✅ Epic Games Store (API ufficiale)
- ✅ Steam (via RSS community)  
- ✅ GamerPower (RSS universale)
- ✅ Filtri anti-duplicati
- ✅ Rate limiting per evitare ban

## Schedule:
- **Ogni giovedì 18:00 CEST** = post settimanale
- Modifica cron in `start.sh` per cambiare orari

Tutti i file sono pronti per il deploy immediato!