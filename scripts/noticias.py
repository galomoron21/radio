# Arma noticias.json para el locutor de Radio Galo & Nake.
# Lo corre GitHub Actions cada hora. Lee los RSS de varios diarios (que traen el titular y la bajada,
# o sea el primer párrafo de la nota) y suma búsquedas de Google Noticias para los 5 grandes.
import html, json, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

# (tema que dice el locutor, url del RSS, cuántas notas tomar)
DIARIOS = [
    ("actualidad", "https://www.clarin.com/rss/lo-ultimo/", 3),
    ("política", "https://www.clarin.com/rss/politica/", 3),
    ("economía", "https://www.clarin.com/rss/economia/", 3),
    ("deportes", "https://www.clarin.com/rss/deportes/", 3),
    ("espectáculos", "https://www.clarin.com/rss/espectaculos/", 3),
    ("el mundo", "https://www.clarin.com/rss/mundo/", 2),
    ("sociedad", "https://www.clarin.com/rss/sociedad/", 2),
    ("tecnología", "https://www.clarin.com/rss/tecnologia/", 2),
    ("fútbol", "https://www.ole.com.ar/rss/ultimas-noticias/", 3),
    ("actualidad", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml", 3),
    ("actualidad", "https://www.infobae.com/arc/outboundfeeds/rss/", 3),
    ("actualidad", "https://www.pagina12.com.ar/rss/portada", 2),
    ("economía", "https://www.ambito.com/rss/pages/economia.xml", 2),
    ("música", "https://www.rollingstone.com.ar/arc/outboundfeeds/rss/", 2),
]
# Google Noticias solo trae el titular, pero sirve para buscar temas puntuales.
BUSQUEDAS = [
    ("fútbol", "River Plate"), ("fútbol", "Boca Juniors"), ("fútbol", "Racing Club"),
    ("fútbol", "Independiente Avellaneda"), ("fútbol", "San Lorenzo de Almagro"),
    ("recitales", "anunció recital en Argentina"), ("música", "rock nacional"),
    ("tránsito", "tránsito Panamericana Acceso Norte General Paz"),
    ("clima", "alerta meteorológica Buenos Aires"),
]
HORAS = 18
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def leer(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return ET.fromstring(r.read())

def texto(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(s or "")))
    return re.sub(r"\s+", " ", s).strip()

def bajada(desc, titulo):
    # Una o dos oraciones, hasta ~320 letras, sin repetir el titular.
    d = texto(desc)
    if not d or d.lower().startswith(titulo.lower()[:40]) or len(d) < 40:
        return ""
    ora, out = re.split(r"(?<=[.!?])\s+", d), ""
    for o in ora:
        if len(out) + len(o) > 320: break
        out += (" " if out else "") + o
    if not out:
        out = d[:300].rsplit(" ", 1)[0] + "."
    if out[-1] not in ".!?": out += "."
    return out

def fecha(it):
    for k in ("pubDate", "{http://purl.org/dc/elements/1.1/}date"):
        v = it.findtext(k)
        if v:
            try: return parsedate_to_datetime(v).timestamp()
            except Exception: pass
    return time.time()

items, vistos = [], set()
def sumar(tema, titulo, cuerpo, fuente, t):
    clave = re.sub(r"\W+", "", titulo.lower())[:50]
    if not titulo or clave in vistos or time.time() - t > HORAS * 3600 or len(titulo) > 200:
        return False
    vistos.add(clave)
    items.append({"tema": tema, "titulo": titulo, "bajada": cuerpo, "fuente": fuente, "t": int(t * 1000)})
    return True

for tema, url, cuantas in DIARIOS:
    try:
        raiz, n = leer(url), 0
        fuente = urllib.parse.urlparse(url).netloc.replace("www.", "")
        for it in raiz.iter("item"):
            titulo = texto(it.findtext("title")).rstrip(".")
            desc = it.findtext("description") or it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            if sumar(tema, titulo, bajada(desc, titulo), fuente, fecha(it)):
                n += 1
                if n >= cuantas: break
        print(fuente, tema, n)
    except Exception as e:
        print("No se pudo leer", url, e)
    time.sleep(0.5)

for tema, q in BUSQUEDAS:
    try:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:1d", "hl": "es-419", "gl": "AR", "ceid": "AR:es-419"})
        n = 0
        for it in leer(url).iter("item"):
            titulo, fuente = texto(it.findtext("title")), texto(it.findtext("source"))
            if fuente and titulo.endswith(" - " + fuente): titulo = titulo[: -len(fuente) - 3]
            if sumar(tema, titulo, "", fuente, fecha(it)):
                n += 1
                if n >= 2: break
    except Exception as e:
        print("No se pudo buscar", q, e)
    time.sleep(1)

items.sort(key=lambda x: -x["t"])
with open("noticias.json", "w", encoding="utf-8") as f:
    json.dump({"t": int(time.time() * 1000), "items": items}, f, ensure_ascii=False, indent=1)
print(len(items), "noticias,", sum(1 for x in items if x["bajada"]), "con bajada")
