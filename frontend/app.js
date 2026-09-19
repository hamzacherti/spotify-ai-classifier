async function load() {
 const r = await fetch("/api/me"); const d = await r.json(); const c = document.getElementById("content");
 if (!d.authenticated) c.innerHTML = '<a class="button" href="/auth/login">Connecter Spotify</a>';
 else c.innerHTML = `<h2>Connecté à Spotify ✅</h2><p>Utilisateur : ${d.display_name}</p>
 <p>Morceaux traités : ${d.processed_tracks}</p><p>Playlists : ${d.playlists}</p>
 <p>Synchronisation automatique : ACTIVE</p><form method="post" action="/auth/logout"><button>Se déconnecter</button></form>`;
} load(); setInterval(load, 30000);