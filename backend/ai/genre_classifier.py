
import asyncio
import logging
from google import genai
from google.genai import types
from backend.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()
client = genai.Client(api_key=settings.gemini_api_key)


GENRES = [
    "Pop",
    "Rock",
    "Hip-Hop / Rap",
    "R&B / Soul",
    "Funk / Disco",
    "Electronic / Dance",
    "Reggae",
    "Jazz",
    "Blues",
    "Folk / Acoustic",
    "Country",
    "Classical",
    "Latin",
    "Arabic Pop",
    "Arabic Classical",
    "Rai",
    "Chaabi",
    "Gnawa",
    "Issawa",
    "Khaleeji",
    "Arabic Folk",
    "Arabic / Other",
    "African",
    "Indian",
    "Soundtrack",
    "Metal",
    "Punk",
    "Other",
]


def build_prompt(title, artist, existing):
    existing_text = ", ".join(existing) if existing else "(aucun)"
    genres_text = ", ".join(GENRES)

    return f"""
Tu es un expert en classification musicale.

Classe la chanson suivante dans UN SEUL genre parmi les genres autorisés.

Titre : {title}
Artiste : {artist}

Genres déjà utilisés par cet utilisateur :
{existing_text}

Genres autorisés :
{genres_text}

OBJECTIF :
La classification doit être musicalement pertinente et suffisamment précise,
tout en évitant de créer inutilement de nouvelles catégories.

RÈGLES GÉNÉRALES :

1. Retourne EXACTEMENT un genre présent dans la liste des genres autorisés.

2. Si un genre déjà utilisé convient réellement à la chanson,
   réutilise-le.

3. Ne crée jamais de nouveau genre ou de micro-genre.

4. Base principalement la classification sur les caractéristiques
   musicales réelles de la chanson :
   instrumentation, rythme, structure, production, mélodie,
   tradition musicale et style vocal.

5. Ne déduis pas le genre uniquement à partir :
   - de la nationalité de l'artiste ;
   - de la langue ;
   - du pays ;
   - de l'époque.

6. Pour les genres occidentaux, regroupe les sous-genres dans leur
   grande famille :
   - Trap, Drill, Boom Bap, Gangsta Rap -> Hip-Hop / Rap
   - House, Techno, Trance, EDM -> Electronic / Dance
   - Indie Rock, Alternative Rock, Hard Rock, Progressive Rock -> Rock
   - Neo-Soul, Contemporary R&B -> R&B / Soul
   - Heavy Metal, Thrash Metal -> Metal
   - Punk Rock -> Punk

CLASSIFICATION DE LA MUSIQUE ARABE :

La musique arabe doit être classifiée PLUS PRÉCISEMENT.

Ne classe pas automatiquement toutes les chansons arabophones
dans "Arabic Pop".

Utilise les catégories suivantes lorsqu'elles correspondent réellement :

- Arabic Pop :
  Pop arabe moderne, variété arabe et productions pop contemporaines.

- Arabic Classical :
  musique arabe classique/traditionnelle savante, tarab,
  grandes formes orchestrales ou vocales classiques.

- Rai :
  Raï algérien ou maghrébin, notamment lorsque les caractéristiques
  rythmiques, mélodiques et vocales du Raï sont dominantes.

- Chaabi :
  musique Chaabi, notamment Chaabi marocain, algérien ou maghrébin,
  lorsque ce style est clairement identifiable.

- Gnawa :
  musique Gnawa / Gnaoua, lorsque les caractéristiques musicales
  Gnawa sont dominantes.

- Issawa :
  musique Issawa / Aïssawa, notamment les formes traditionnelles
  et spirituelles marocaines clairement associées à cette tradition.

- Khaleeji :
  musique du Golfe / Khaleeji lorsque ce style est clairement dominant.

- Arabic Folk :
  musique folklorique ou traditionnelle arabe qui ne correspond
  pas spécifiquement à Rai, Chaabi, Gnawa, Issawa ou Khaleeji.

- Arabic / Other :
  musique arabe clairement identifiable mais ne correspondant
  raisonnablement à aucune des catégories arabes précédentes.

IMPORTANT :

Une chanson chantée en arabe n'est PAS automatiquement "Arabic Pop".

Exemples :
- Une chanson pop moderne en arabe -> Arabic Pop
- Une chanson de Raï -> Rai
- Une chanson de Chaabi -> Chaabi
- Une chanson Gnawa -> Gnawa
- Une chanson Issawa -> Issawa
- Une chanson classique arabe -> Arabic Classical
- Une chanson traditionnelle arabe sans catégorie plus précise -> Arabic Folk

Pour une chanson marocaine, algérienne ou autre chanson maghrébine,
ne choisis pas Chaabi ou Rai uniquement à cause de l'origine de l'artiste.
Le style musical doit réellement correspondre.

IMPORTANT :
Ne mélange pas les catégories.

"Rai" doit rester "Rai".
"Chaabi" doit rester "Chaabi".
"Issawa" doit rester "Issawa".
"Gnawa" doit rester "Gnawa".

Ne retourne aucune explication.
Ne retourne ni titre ni artiste.
Retourne uniquement le genre.

Réponse :
""".strip()


async def classify(title, artist, existing):
    prompt = build_prompt(title, artist, existing)

    for attempt in range(3):
        try:
            result = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=20,
                ),
            )

            genre = (
                (result.text or "")
                .strip()
                .splitlines()[0]
                .strip("`* ")
            )

            if not genre:
                raise ValueError("Gemini returned an empty genre")

            if genre not in GENRES:
                aliases = {
                    "Arabic": "Arabic Pop",
                    "Arab Pop": "Arabic Pop",
                    "Arabic Pop Music": "Arabic Pop",
                    "Classical Arabic": "Arabic Classical",
                    "Arabic Classical Music": "Arabic Classical",
                    "Raï": "Rai",
                    "Rai Music": "Rai",
                    "Chaabi Marocain": "Chaabi",
                    "Moroccan Chaabi": "Chaabi",
                    "Gnaoua": "Gnawa",
                    "Gnawa Music": "Gnawa",
                    "Aissawa": "Issawa",
                    "Aïssawa": "Issawa",
                    "Khaleeji Music": "Khaleeji",
                }

                genre = aliases.get(genre, "Other")

            return genre

        except Exception:
            if attempt == 2:
                log.exception(
                    "[AI] classification failed for %s - %s",
                    artist,
                    title,
                )
                raise

            await asyncio.sleep(2 ** attempt)

