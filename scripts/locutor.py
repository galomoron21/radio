# Fabrica los audios del locutor de Radio Galo & Nake con una voz neural argentina (Microsoft "Tomás").
# Lo corre GitHub Actions cada hora. Los audios quedan en la rama "voz" del repo, con un indice.json.
# Cada frase es una oración entera (no pedacitos pegados), así suena natural.
import asyncio, random, datetime, hashlib, json, os, re, time, urllib.request, zoneinfo
import edge_tts

VOZ = "es-AR-TomasNeural"
CARPETA = "voz"
BA = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
FS = "https://firestore.googleapis.com/v1/projects/radio-galo-nake/databases/(default)/documents/config/"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
NUM = ["doce", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once"]
CIELOS = {0: "cielo despejado", 1: "algunas nubes", 2: "algunas nubes", 3: "cielo nublado", 45: "niebla", 48: "niebla",
          51: "llovizna", 53: "llovizna", 55: "llovizna", 61: "lluvia", 63: "lluvia", 65: "lluvia fuerte", 80: "chaparrones",
          81: "chaparrones", 82: "chaparrones fuertes", 95: "tormenta", 96: "tormenta", 99: "tormenta"}
GRANDES = ["River Plate", "Boca Juniors", "Racing Club", "Independiente", "San Lorenzo"]

def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "radio-galo-nake"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def valor(v):  # Firestore REST -> Python
    if "stringValue" in v: return v["stringValue"]
    if "integerValue" in v: return int(v["integerValue"])
    if "doubleValue" in v: return v["doubleValue"]
    if "booleanValue" in v: return v["booleanValue"]
    if "nullValue" in v: return None
    if "mapValue" in v: return {k: valor(x) for k, x in v["mapValue"].get("fields", {}).items()}
    if "arrayValue" in v: return [valor(x) for x in v["arrayValue"].get("values", [])]
    return None

def canciones():
    # Si Firebase no responde (cupo diario agotado), se usa la copia de la vez anterior.
    copia = os.path.join(CARPETA, "catalogo.json")
    try:
        meta = bajar(FS + "mp3-meta")
        n = valor(meta["fields"]["n"])
        todas = []
        for i in range(n):
            d = bajar(FS + f"mp3-{i}")
            todas += valor(d["fields"]["items"])
        if todas:
            os.makedirs(CARPETA, exist_ok=True)
            with open(copia, "w", encoding="utf-8") as f: json.dump(todas, f, ensure_ascii=False)
        return todas
    except Exception as e:
        print("Firebase no respondió, uso la copia del catálogo:", e)
        return json.load(open(copia, encoding="utf-8"))

RUIDO = re.compile(r"\s*[\(\[][^\)\]]*(remaster|official|oficial|video|audio|lyric|letra|hd|hq|4k|full|version|versión|mono|stereo|edit|mix|live at|bonus|deluxe|explicit)[^\)\]]*[\)\]]", re.I)
def limpio(t):
    t = re.sub(r"\[[^\]]*\]", "", str(t or ""))
    t = RUIDO.sub("", t)
    t = re.sub(r"\s+-\s+(\d{4}\s+)?(digital\s+)?remaster.*$", "", t, flags=re.I)
    t = re.sub(r"\s+-\s+(single|radio|album)\s+(version|edit).*$", "", t, flags=re.I)
    t = re.sub(r"\b(full\s*hd|hd|hq|4k|video\s*oficial|official\s*(music\s*)?video|lyrics?)\b", "", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip(" -–·") or str(t)

def hora_texto(h, m):
    base = NUM[h % 12]
    art = "Es la" if h % 12 == 1 else "Son las"
    mins = {0: "en punto", 15: "y cuarto", 30: "y media"}.get(m) or f"y {m}"
    if h == 0: per = "de la noche"
    elif h < 6: per = "de la madrugada"
    elif h < 12: per = "de la mañana"
    elif h == 12: per = "del mediodía"
    elif h < 20: per = "de la tarde"
    else: per = "de la noche"
    return f"{art} {base} {mins} {per}"

def clave_archivo(texto):
    return hashlib.sha1((VOZ + "|" + texto).encode()).hexdigest()[:16] + ".mp3"

frases = {}  # clave -> texto
ahora = datetime.datetime.now(BA)

# Radios
frases["radio-nacional"] = "Estás escuchando Rock Nacional, en Radio Galo y Nake."
frases["radio-internacional"] = "Estás escuchando Rock Internacional, en Radio Galo y Nake."

# Hora exacta (minuto a minuto) y clima para las próximas 6 horas (GitHub a veces se atrasa con la acción horaria)
try:
    w = bajar("https://api.open-meteo.com/v1/forecast?latitude=-34.61&longitude=-58.38&hourly=temperature_2m,weather_code,precipitation_probability&forecast_hours=18&timezone=America%2FArgentina%2FBuenos_Aires")
    clima = {t[:13]: (round(tt), CIELOS.get(c, "tiempo tranquilo"), p) for t, tt, c, p in zip(w["hourly"]["time"], w["hourly"]["temperature_2m"], w["hourly"]["weather_code"], w["hourly"]["precipitation_probability"])}
except Exception as e:
    print("Sin clima", e); clima = {}
inicio = ahora.replace(second=0, microsecond=0)
for k in range(6 * 60):
    t = inicio + datetime.timedelta(minutes=k)
    texto = f"{hora_texto(t.hour, t.minute)} de este {DIAS[t.weekday()]} en Buenos Aires."
    c = clima.get(t.strftime("%Y-%m-%dT%H"))
    if c: texto += f" Hacen {c[0]} grados, con {c[1]}."
    frases["hora-" + t.strftime("%Y%m%d-%H%M")] = texto

# Lluvia en las próximas horas
lluvia = [(k, v) for k, v in sorted(clima.items()) if v[2] is not None and v[2] >= 60 and k >= ahora.strftime("%Y-%m-%dT%H")]
if lluvia:
    h = int(lluvia[0][0][11:13])
    momento = "a la mañana" if h < 12 else "a la tarde" if h < 20 else "a la noche"
    frases["lluvia-" + lluvia[0][0][:10] + "-" + momento.split()[-1]] = f"Ojo, que se pronostican lluvias {momento}, a eso de las {h}. Si salís, llevá paraguas."

# Temas (y dedicatorias de los últimos 3 días)
try:
    for s in canciones():
        if not s.get("id") or not s.get("titulo"): continue
        banda = str(s.get("banda") or "").split(",")[0].strip()
        frases["tema-" + s["id"]] = f"Se viene {limpio(s['titulo'])}, de {banda}."
        cur = re.sub(r"\s+", " ", str(s.get("curio") or "")).strip()
        if len(cur) > 30:
            frases["cur-" + s["id"]] = random.Random(s["id"]).choice(["Un dato de este tema:", "Un datito:", "¿Sabías esto?", "Dato de color:"]) + " " + cur
        if s.get("dedica") and s.get("creada") and time.time() * 1000 - s["creada"] < 3 * 86400000:
            frases["ded-" + s["id"]] = f"Este tema va dedicado a {s['dedica']}, de parte de {s.get('pidio') or 'un oyente'}. Suena {limpio(s['titulo'])}, de {banda}."
except Exception as e:
    print("Sin canciones", e)

# Noticias (las arma noticias.py)
try:
    for n in json.load(open("noticias.json", encoding="utf-8"))["items"]:
        k = hashlib.sha1(n["titulo"].encode()).hexdigest()[:12]
        intro = random.Random(k).choice([f"Noticias de {n['tema']}:", f"Pasamos a {n['tema']}:", f"En {n['tema']}:", f"Un repaso de {n['tema']}:", f"Les cuento algo de {n['tema']}:"])
        frases["noti-" + k] = f"{intro} {n['titulo']}. {n.get('bajada') or ''}".strip()
except Exception as e:
    print("Sin noticias", e)

# Fútbol: los 5 grandes, hoy y ayer
for dias in (0, 1):
    f = (ahora - datetime.timedelta(days=dias)).strftime("%Y%m%d")
    try:
        for e in bajar(f"https://site.api.espn.com/apis/site/v2/sports/soccer/arg.1/scoreboard?dates={f}").get("events", []):
            if not e.get("status", {}).get("type", {}).get("completed"): continue
            x, y = e["competitions"][0]["competitors"]
            nombres = x["team"]["displayName"] + " " + y["team"]["displayName"]
            if not any(g in nombres for g in GRANDES): continue
            nx, ny = x["team"].get("shortDisplayName") or x["team"]["displayName"], y["team"].get("shortDisplayName") or y["team"]["displayName"]
            gx, gy = int(x.get("score") or 0), int(y.get("score") or 0)
            cuando = "Hoy" if dias == 0 else "Ayer"
            t = f"{cuando} {nx} y {ny} empataron {gx} a {gy}." if gx == gy else f"{cuando} {nx if gx > gy else ny} le ganó {max(gx, gy)} a {min(gx, gy)} a {ny if gx > gy else nx}."
            frases["fut-" + str(e["id"])] = "En el fútbol: " + t
    except Exception as ex:
        print("Sin fútbol", ex)

# Datos de las bandas
try:
    for d in json.load(open("datos-chistes.json", encoding="utf-8")):
        if d.get("d"):
            frases["dato-" + hashlib.sha1((d["b"] + d["d"]).encode()).hexdigest()[:12]] = f"Un dato sobre {d['b']}: {d['d']}"
except Exception as e:
    print("Sin datos", e)

# Fabricar lo que falta
os.makedirs(CARPETA, exist_ok=True)
indice = {k: {"f": clave_archivo(t), "t": t} for k, t in frases.items()}
faltan = {v["f"]: v["t"] for v in indice.values() if not os.path.exists(os.path.join(CARPETA, v["f"]))}
print(len(indice), "frases,", len(faltan), "para fabricar")

async def fabricar(sem, archivo, texto):
    async with sem:
        for intento in range(3):
            try:
                await edge_tts.Communicate(texto, VOZ, rate="+4%").save(os.path.join(CARPETA, archivo))
                return
            except Exception as e:
                print("Reintento", archivo, e); await asyncio.sleep(3 * (intento + 1))

async def main():
    sem = asyncio.Semaphore(6)
    await asyncio.gather(*(fabricar(sem, a, t) for a, t in faltan.items()))
asyncio.run(main())

# Solo quedan los audios que se usan
usados = {v["f"] for v in indice.values()}
for a in os.listdir(CARPETA):
    if a.endswith(".mp3") and a not in usados:
        os.remove(os.path.join(CARPETA, a))
indice = {k: v for k, v in indice.items() if os.path.exists(os.path.join(CARPETA, v["f"]))}
with open(os.path.join(CARPETA, "indice.json"), "w", encoding="utf-8") as f:
    json.dump({"t": int(time.time() * 1000), "voz": VOZ, "frases": indice}, f, ensure_ascii=False)
print("Listo:", len(indice), "audios")
