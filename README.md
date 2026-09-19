# Spotify AI Classifier

Application FastAPI multi-utilisateur qui récupère les morceaux likés Spotify, classe chaque morceau avec Gemini (1 requête Gemini par morceau), crée une playlist par genre et synchronise les nouveaux likes en arrière-plan.

## 1. Prérequis
- Python 3.11+
- Compte Spotify for Developers
- Clé Gemini API
- PostgreSQL en production (SQLite en local)

## 2. Créer l'application Spotify
1. Ouvrir https://developer.spotify.com/dashboard.
2. Créer une application.
3. Copier le Client ID et le Client Secret.
4. Ajouter exactement `http://localhost:8000/auth/callback` dans Redirect URIs en local.
5. En production, utiliser l'URL HTTPS publique, par exemple `https://votre-domaine.fr/auth/callback`.
6. Utiliser les scopes `user-library-read`, `playlist-modify-private` et `playlist-modify-public`.

L'application utilise les endpoints actuels `/me/tracks`, `/me/playlists` et `/playlists/{id}/items`.

## 3. Gemini
1. Ouvrir https://aistudio.google.com/.
2. Créer une clé API.
3. Copier la clé dans `GEMINI_API_KEY`.
4. Définir le modèle dans `GEMINI_MODEL`, sans le coder en dur.

## 4. Windows
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Modifier .env
uvicorn backend.main:app --reload
```
Puis ouvrir http://localhost:8000.

## 5. Production VPS
Installer Python, PostgreSQL et Nginx:
```bash
sudo apt update
sudo apt install -y python3 python3-venv postgresql nginx
git clone VOTRE_DEPOT
cd spotify-ai-classifier
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Créer une base PostgreSQL et renseigner:
```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
SESSION_SECRET=une_valeur_aleatoire_longue
SPOTIFY_REDIRECT_URI=https://votre-domaine.fr/auth/callback
```

Service systemd `/etc/systemd/system/spotify-ai.service`:
```ini
[Unit]
Description=Spotify AI Classifier
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/spotify-ai-classifier
EnvironmentFile=/home/ubuntu/spotify-ai-classifier/.env
ExecStart=/home/ubuntu/spotify-ai-classifier/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now spotify-ai
sudo systemctl status spotify-ai
journalctl -u spotify-ai -f
```

Configurer Nginx comme reverse proxy vers `127.0.0.1:8000`, puis activer HTTPS avec Certbot:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d votre-domaine.fr
```

## 6. Multi-utilisateur
- Chaque utilisateur est identifié par son `spotify_id`.
- Les tokens restent côté serveur et ne sont jamais envoyés au frontend.
- Toutes les requêtes de traitement sont liées à `user_id`.
- La contrainte `(user_id, spotify_track_id)` empêche le double traitement.
- La contrainte `(user_id, genre)` empêche les playlists dupliquées pour un utilisateur.
- Les playlists et morceaux de deux comptes sont donc indépendants.

## 7. Remarques opérationnelles
- Le worker tourne dans le même processus que FastAPI et redémarre avec le service systemd.
- Pour quelques utilisateurs, cette architecture est simple et suffisante.
- Pour une croissance importante, il faudra séparer le worker du serveur web et ajouter une file de tâches.
- Les erreurs d'un morceau ou d'un utilisateur sont journalisées puis le traitement continue.
