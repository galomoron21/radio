# Arma noticias.json para el locutor de Radio Galo & Nake.
# Lo corre GitHub Actions cada hora: busca en Google Noticias los temas que nos interesan
# y guarda solo los titulares (sin el texto de la nota).
import json, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

TEMAS = [
    ("fútbol", "River Plate"), ("fútbol", "Boca Juniors"), ("fútbol", "Racing Club"),
    ("fútbol", "Independiente Avellaneda"), ("fútbol", "San Lorenzo de Almagro"),
    ("recitales", "anunció recital en Argentina"), ("recitales", "show confirmado Buenos Aires rock"),
    ("música", "rock nacional"), ("política", "Presupuesto 2027 Congreso"),
    ("política", "Gobierno nacional anuncio"), ("economía", "dólar hoy"),
    ("tránsito", "tránsito Panamericana Acceso Norte General Paz"),
    ("clima", "alerta meteorológica Buenos Aires"),
]
POR_TEMA = 2
HORAS = 24

def buscar(q):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:1d", "hl": "es-419", "gl": "AR", "ceid": "AR:es-419"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (radio-galo-nake)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raiz = ET.fromstring(r.read())
    for it in raiz.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        fuente = (it.findtext("source") or "").strip()
        try:
            t = parsedate_to_datetime(it.findtext("pubDate")).timestamp()
        except Exception:
            t = time.time()
        if fuente and titulo.endswith(" - " + fuente):
            titulo = titulo[: -len(fuente) - 3]
        yield titulo, fuente, t

items, vistos = [], set()
for tema, q in TEMAS:
    n = 0
    try:
        for titulo, fuente, t in buscar(q):
            clave = titulo.lower()[:60]
            if clave in vistos or time.time() - t > HORAS * 3600 or len(titulo) > 160:
                continue
            vistos.add(clave)
            items.append({"tema": tema, "titulo": titulo, "fuente": fuente, "t": int(t * 1000)})
            n += 1
            if n >= POR_TEMA:
                break
    except Exception as e:
        print("No se pudo buscar", q, e)
    time.sleep(1)

items.sort(key=lambda x: -x["t"])
with open("noticias.json", "w", encoding="utf-8") as f:
    json.dump({"t": int(time.time() * 1000), "items": items}, f, ensure_ascii=False, indent=1)
print(len(items), "noticias")
