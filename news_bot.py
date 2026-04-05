#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  news_bot.py  —  Radar IA Empresarial                   ║
║  Busca en 15 sitios top de IA, resume las 5 mejores     ║
║  noticias en español y las envía por email SMTP.         ║
╚══════════════════════════════════════════════════════════╝
"""

import os, sys, re, time, html, json
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup
import trafilatura
from groq import Groq

# ══════════════════════════════════════════════════════════
# CONFIGURACIÓN  ← Edita estas variables o usa env vars
# ══════════════════════════════════════════════════════════
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")   # console.groq.com
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")  # resend.com

DESTINATARIO  = os.environ.get("DESTINATARIO", "vicente.dominguez@maindset.cl")

DIAS_ATRAS     = 7
TOP_N          = 5
TIMEOUT_HTTP   = 12   # segundos por request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}

# ══════════════════════════════════════════════════════════
# FUENTES  (15 sitios top de IA)
# ══════════════════════════════════════════════════════════
FUENTES = [
    {"nombre": "MIT Technology Review",  "rss": "https://www.technologyreview.com/feed/",                          "peso": 10},
    {"nombre": "Harvard Business Review","rss": "https://hbr.org/rss/topic/technology",                            "peso": 10},
    {"nombre": "VentureBeat AI",         "rss": "https://venturebeat.com/category/ai/feed/",                       "peso": 9},
    {"nombre": "TechCrunch AI",          "rss": "https://techcrunch.com/category/artificial-intelligence/feed/",   "peso": 9},
    {"nombre": "Forbes Tech",            "rss": "https://www.forbes.com/innovation/feed2/",                         "peso": 9},
    {"nombre": "Wired",                  "rss": "https://www.wired.com/feed/rss",                                   "peso": 8},
    {"nombre": "The Verge AI",           "rss": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml","peso": 8},
    {"nombre": "Ars Technica",           "rss": "https://feeds.arstechnica.com/arstechnica/technology-lab",         "peso": 7},
    {"nombre": "ZDNet AI",               "rss": "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",      "peso": 7},
    {"nombre": "AI News",                "rss": "https://www.artificialintelligence-news.com/feed/",                "peso": 8},
    {"nombre": "InfoWorld AI",           "rss": "https://www.infoworld.com/category/artificial-intelligence/index.rss", "peso": 7},
    {"nombre": "TechRepublic AI",        "rss": "https://www.techrepublic.com/rssfeeds/topic/artificial-intelligence/", "peso": 7},
    {"nombre": "The Register AI",        "rss": "https://www.theregister.com/ai/headlines.atom",                    "peso": 7},
    {"nombre": "Analytics Insight",      "rss": "https://www.analyticsinsight.net/feed/",                           "peso": 6},
    {"nombre": "Towards Data Science",   "rss": "https://towardsdatascience.com/feed",                              "peso": 6},
]

# Palabras clave para puntuar relevancia empresarial
KW_EMPRESA = [
    "enterprise", "company", "business", "corporate", "organization", "firm",
    "deploy", "implement", "adopt", "transform", "productivity", "workforce",
    "startup", "investment", "billion", "million", "revenue", "market",
    "employee", "executive", "CEO", "CTO", "strategy", "ROI", "industry",
    "sector", "client", "customer", "solution", "platform", "tool"
]
KW_IA = [
    "artificial intelligence", "machine learning", "LLM", "GPT", "Claude",
    "Gemini", "generative AI", "ChatGPT", "automation", "deep learning",
    "foundation model", "large language model", "agentic", "copilot",
    "neural network", "AI model", "AI system", "AI tool", "AI adoption"
]


# ══════════════════════════════════════════════════════════
# PASO 1 — Recolectar noticias de los últimos N días
# ══════════════════════════════════════════════════════════
def fecha_entry(entry):
    """Extrae datetime aware de un entry feedparser."""
    for campo in ("published", "updated", "created"):
        raw = entry.get(campo + "_parsed") or entry.get(campo)
        if raw is None:
            continue
        if hasattr(raw, "tm_year"):                        # time.struct_time
            try:
                return datetime(*raw[:6], tzinfo=timezone.utc)
            except Exception:
                continue
        if isinstance(raw, str):
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            except Exception:
                continue
    return None


def recolectar_noticias():
    cutoff = datetime.now(timezone.utc) - timedelta(days=DIAS_ATRAS)
    articulos = []
    print(f"\n{'='*58}")
    print(f"  Buscando noticias de los últimos {DIAS_ATRAS} días...")
    print(f"{'='*58}")

    for fuente in FUENTES:
        nombre = fuente["nombre"]
        try:
            feed = feedparser.parse(fuente["rss"])
            count = 0
            for entry in feed.entries:
                fecha = fecha_entry(entry)
                if fecha and fecha < cutoff:
                    continue                    # demasiado antiguo
                titulo = entry.get("title", "").strip()
                link   = entry.get("link", "").strip()
                resumen = BeautifulSoup(
                    entry.get("summary", entry.get("description", "")), "html.parser"
                ).get_text(" ", strip=True)[:600]
                if not titulo or not link:
                    continue
                articulos.append({
                    "fuente": nombre,
                    "peso_fuente": fuente["peso"],
                    "titulo": titulo,
                    "link": link,
                    "resumen_rss": resumen,
                    "fecha": fecha,
                    "puntuacion": 0,
                })
                count += 1
            print(f"  ✓ {nombre:30s} → {count} artículos recientes")
        except Exception as e:
            print(f"  ✗ {nombre:30s} → Error: {e}")

    print(f"\n  Total recolectado: {len(articulos)} artículos\n")
    return articulos


# ══════════════════════════════════════════════════════════
# PASO 2 — Puntuar y seleccionar los TOP 5
# ══════════════════════════════════════════════════════════
def puntuar(art):
    texto = (art["titulo"] + " " + art["resumen_rss"]).lower()
    score = art["peso_fuente"] * 2

    # Recencia (más reciente = más puntos)
    if art["fecha"]:
        horas = (datetime.now(timezone.utc) - art["fecha"]).total_seconds() / 3600
        score += max(0, 20 - horas / 8)   # hasta +20 pts si es muy reciente

    # Palabras clave empresariales
    for kw in KW_EMPRESA:
        if kw.lower() in texto:
            score += 2

    # Palabras clave de IA
    for kw in KW_IA:
        if kw.lower() in texto:
            score += 3

    art["puntuacion"] = round(score, 2)
    return art


def seleccionar_top(articulos, n=TOP_N):
    puntuados = [puntuar(a) for a in articulos]
    # Deduplicar por dominio base para variedad
    vistos = set()
    seleccion = []
    for art in sorted(puntuados, key=lambda x: -x["puntuacion"]):
        dominio = re.sub(r"https?://(www\.)?", "", art["link"]).split("/")[0]
        if dominio not in vistos:
            vistos.add(dominio)
            seleccion.append(art)
        if len(seleccion) >= n:
            break
    return seleccion


# ══════════════════════════════════════════════════════════
# PASO 3 — Obtener contenido completo del artículo
# ══════════════════════════════════════════════════════════
def obtener_contenido(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_HTTP)
        resp.raise_for_status()
        texto = trafilatura.extract(resp.text, include_comments=False,
                                    include_tables=False, no_fallback=False)
        if texto and len(texto) > 200:
            return texto[:3000]
    except Exception:
        pass
    return None   # fallback al resumen RSS


# ══════════════════════════════════════════════════════════
# PASO 4 — Resumir y analizar con Groq
# ══════════════════════════════════════════════════════════
def resumir_con_groq(articulos):
    if not GROQ_API_KEY:
        print("\n  ⚠ GROQ_API_KEY no configurada. Usando resúmenes RSS como fallback.")
        for art in articulos:
            art["titulo_es"]  = art["titulo"]
            art["resumen_es"] = art["resumen_rss"] or "Contenido no disponible."
            art["analisis"]   = "Configura GROQ_API_KEY para obtener análisis automático."
        return articulos

    client = Groq(api_key=GROQ_API_KEY)
    print("  Enviando articulos a Groq (llama-3.3-70b) para resumen y analisis...\n")

    bloques = []
    for i, art in enumerate(articulos, 1):
        contenido = art.get("contenido_completo") or art["resumen_rss"] or art["titulo"]
        bloques.append(
            f"ARTICULO {i}\n"
            f"Fuente: {art['fuente']}\n"
            f"Titulo original: {art['titulo']}\n"
            f"URL: {art['link']}\n"
            f"Contenido:\n{contenido}\n"
        )

    prompt = (
        "Eres un analista estratégico senior especializado en inteligencia artificial empresarial. "
        "A continuacion tienes 5 articulos recientes sobre uso de IA en empresas a nivel mundial.\n\n"
        + "\n---\n".join(bloques)
        + "\n\n"
        "Responde con un objeto JSON que tenga una clave 'articles' con un array de 5 elementos. "
        "Para CADA articulo incluye:\n"
        "- num: numero del articulo (1 al 5)\n"
        "- titulo_es: titulo traducido al espanol (claro y natural)\n"
        "- resumen: resumen en espanol de 4-5 oraciones con los puntos clave, cifras y contexto\n"
        "- analisis: comentario analitico de 3-4 oraciones sobre implicancias estrategicas para "
        "empresas que adoptan IA: que significa, que oportunidad o riesgo representa, "
        "y que deberian considerar los ejecutivos\n\n"
        "Formato exacto: {\"articles\": [{\"num\": 1, \"titulo_es\": \"...\", "
        "\"resumen\": \"...\", \"analisis\": \"...\"}, ...]}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        resultados = data.get("articles", data.get("articulos", []))
        for r in resultados:
            idx = r["num"] - 1
            if 0 <= idx < len(articulos):
                articulos[idx]["titulo_es"]  = r.get("titulo_es", articulos[idx]["titulo"])
                articulos[idx]["resumen_es"] = r.get("resumen", "")
                articulos[idx]["analisis"]   = r.get("analisis", "")
        print("  ✓ Groq completo resumenes y analisis.")
    except Exception as e:
        print(f"  ✗ Error con Groq API: {e}")
        for art in articulos:
            if "resumen_es" not in art:
                art["titulo_es"]  = art["titulo"]
                art["resumen_es"] = art["resumen_rss"]
                art["analisis"]   = "Analisis no disponible."

    return articulos


# ══════════════════════════════════════════════════════════
# PASO 5 — Construir email HTML
# ══════════════════════════════════════════════════════════
COLORES_FUENTE = [
    ("#58a6ff", "#0d1117"),
    ("#bc8cff", "#0d1117"),
    ("#f0883e", "#0d1117"),
    ("#3fb950", "#0d1117"),
    ("#f85149", "#0d1117"),
]

def construir_html(articulos):
    fecha_str = datetime.now().strftime("%d de %B de %Y").replace(
        "January","enero").replace("February","febrero").replace("March","marzo"
        ).replace("April","abril").replace("May","mayo").replace("June","junio"
        ).replace("July","julio").replace("August","agosto").replace("September","septiembre"
        ).replace("October","octubre").replace("November","noviembre").replace("December","diciembre")

    def fmt_fecha(dt):
        if not dt:
            return ""
        return dt.strftime("%d/%m/%Y %H:%M UTC")

    tarjetas_html = ""
    for i, art in enumerate(articulos):
        color, texto_color = COLORES_FUENTE[i % len(COLORES_FUENTE)]
        fecha_pub = fmt_fecha(art.get("fecha"))
        titulo_safe   = html.escape(art.get("titulo_es", art["titulo"]))
        resumen_safe  = html.escape(art.get("resumen_es", art.get("resumen_rss", "")))
        analisis_safe = html.escape(art.get("analisis", ""))
        link   = art["link"]
        fuente = html.escape(art["fuente"])

        tarjetas_html += f"""
        <div class="card">
          <div class="card-bar" style="background:{color};">
            <span class="card-num" style="color:{texto_color};">#{i+1} · {fuente}</span>
            <span class="card-fecha" style="color:{texto_color};">{fecha_pub}</span>
          </div>
          <div class="card-body">
            <a href="{link}" class="card-titulo">{titulo_safe}</a>
            <p class="card-resumen">{resumen_safe}</p>
            <div class="card-analisis" style="background:{color}18;border-left:3px solid {color};">
              <p class="analisis-label" style="color:{color};">💡 Análisis estratégico</p>
              <p class="analisis-texto">{analisis_safe}</p>
            </div>
            <a href="{link}" class="card-link" style="color:{color};">Leer artículo completo →</a>
          </div>
        </div>
        """

    html_email = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Radar IA Empresarial</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #0d1117;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #e6edf3;
      padding: 24px 16px;
    }}

    .wrapper {{
      max-width: 860px;
      margin: 0 auto;
    }}

    /* ── HEADER ── */
    .header {{
      background: linear-gradient(135deg, #161b22, #1c2128);
      border: 1px solid #30363d;
      border-radius: 16px;
      overflow: hidden;
      margin-bottom: 24px;
    }}
    .header-inner {{
      background: linear-gradient(90deg, #58a6ff22, #bc8cff22);
      padding: 28px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .header-eyebrow {{
      font-size: 11px;
      font-weight: 700;
      color: #58a6ff;
      letter-spacing: 2px;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .header-title {{
      font-size: clamp(20px, 4vw, 28px);
      font-weight: 800;
      color: #e6edf3;
      line-height: 1.2;
      margin-bottom: 6px;
    }}
    .header-sub {{
      font-size: 13px;
      color: #8b949e;
    }}
    .header-icon {{
      width: 56px;
      height: 56px;
      min-width: 56px;
      background: linear-gradient(135deg, #58a6ff, #bc8cff);
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
    }}
    .stats-bar {{
      background: #21262d;
      border-top: 1px solid #30363d;
      padding: 12px 32px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px 24px;
    }}
    .stat {{
      font-size: 11px;
      font-weight: 700;
    }}

    /* ── CARDS ── */
    .card {{
      background: #1c2128;
      border: 1px solid #30363d;
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 24px;
    }}
    .card-bar {{
      padding: 10px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 4px;
    }}
    .card-num {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}
    .card-fecha {{
      font-size: 11px;
      opacity: .75;
    }}
    .card-body {{
      padding: 20px 24px;
    }}
    .card-titulo {{
      display: block;
      font-size: clamp(15px, 2.5vw, 17px);
      font-weight: 700;
      color: #e6edf3;
      text-decoration: none;
      line-height: 1.4;
      margin-bottom: 12px;
    }}
    .card-titulo:hover {{ text-decoration: underline; }}
    .card-resumen {{
      font-size: 14px;
      color: #8b949e;
      line-height: 1.7;
      margin-bottom: 16px;
    }}
    .card-analisis {{
      border-radius: 0 8px 8px 0;
      padding: 14px 16px;
      margin-bottom: 16px;
    }}
    .analisis-label {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .8px;
      margin-bottom: 6px;
    }}
    .analisis-texto {{
      font-size: 13px;
      color: #c9d1d9;
      line-height: 1.65;
    }}
    .card-link {{
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
    }}
    .card-link:hover {{ text-decoration: underline; }}

    /* ── FOOTER ── */
    .footer {{
      border-top: 1px solid #21262d;
      padding-top: 24px;
      text-align: center;
      font-size: 12px;
      color: #484f58;
      line-height: 1.6;
    }}
    .footer strong {{ color: #58a6ff; }}

    /* ── RESPONSIVE ── */
    @media (max-width: 600px) {{
      body {{ padding: 16px 12px; }}
      .header-inner {{ padding: 20px; flex-direction: column; align-items: flex-start; }}
      .header-icon {{ display: none; }}
      .stats-bar {{ padding: 12px 20px; }}
      .card-body {{ padding: 16px; }}
      .card-bar {{ padding: 8px 16px; }}
    }}

    @media (min-width: 601px) and (max-width: 900px) {{
      body {{ padding: 24px 20px; }}
      .header-inner {{ padding: 24px; }}
    }}
  </style>
</head>
<body>
<div class="wrapper">

  <!-- HEADER -->
  <div class="header">
    <div class="header-inner">
      <div>
        <p class="header-eyebrow">Radar IA Empresarial</p>
        <h1 class="header-title">Las 5 noticias de IA más relevantes</h1>
        <p class="header-sub">{fecha_str} &nbsp;·&nbsp; Últimos {DIAS_ATRAS} días &nbsp;·&nbsp; {len(FUENTES)} fuentes monitoreadas</p>
      </div>
      <div class="header-icon">🤖</div>
    </div>
    <div class="stats-bar">
      <span class="stat" style="color:#58a6ff;">✦ {len(FUENTES)} sitios analizados</span>
      <span class="stat" style="color:#bc8cff;">✦ IA seleccionó las más relevantes</span>
      <span class="stat" style="color:#3fb950;">✦ Resúmenes y análisis en español</span>
    </div>
  </div>

  <!-- ARTÍCULOS -->
  {tarjetas_html}

  <!-- FOOTER -->
  <div class="footer">
    Generado automáticamente por <strong>News Bot IA</strong> · MAindset &nbsp;·&nbsp; {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/>
    Resúmenes y análisis generados con Groq / Llama 3.3
  </div>

</div>
</body>
</html>"""
    return html_email


# ══════════════════════════════════════════════════════════
# PASO 6 — Enviar con Resend
# ══════════════════════════════════════════════════════════
def enviar_email(html_body, articulos):
    fecha_asunto = datetime.now().strftime("%d %b %Y")
    asunto = f"Radar IA Empresarial - {fecha_asunto}"

    if not RESEND_API_KEY:
        print("\n  ⚠ RESEND_API_KEY no configurada.")
        ruta_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ultimo_reporte.html")
        with open(ruta_html, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  ✓ Reporte guardado como: {ruta_html}")
        return

    print(f"\n  Enviando correo a {DESTINATARIO} via Resend...")
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from":    "Radar IA Empresarial <onboarding@resend.dev>",
                "to":      [DESTINATARIO],
                "subject": asunto,
                "html":    html_body,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            print(f"  ✓ Correo enviado exitosamente a {DESTINATARIO}")
        else:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"  ✗ Error al enviar email: {e}")
        ruta_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ultimo_reporte.html")
        with open(ruta_html, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  ✓ Reporte guardado como fallback: {ruta_html}")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    inicio = time.time()
    print("\n" + "="*58)
    print("  [BOT]  RADAR IA EMPRESARIAL  --  News Bot")
    print("="*58)

    # 1. Recolectar
    articulos = recolectar_noticias()
    if not articulos:
        print("  ✗ No se encontraron artículos. Revisa conexión a internet.")
        sys.exit(1)

    # 2. Seleccionar top 5
    top = seleccionar_top(articulos)
    print(f"  Top {TOP_N} seleccionados por relevancia:\n")
    for i, art in enumerate(top, 1):
        print(f"  {i}. [{art['fuente']}] {art['titulo'][:65]}…")
        print(f"     Puntuación: {art['puntuacion']}  |  {art.get('fecha','')}\n")

    # 3. Obtener contenido completo
    print("\n  Obteniendo contenido completo de artículos...")
    for art in top:
        contenido = obtener_contenido(art["link"])
        art["contenido_completo"] = contenido
        estado = "✓" if contenido else "~ (usando resumen RSS)"
        print(f"  {estado} {art['fuente']}: {art['titulo'][:55]}…")

    # 4. Resumir y analizar con Groq
    print("\n  Procesando con Groq API...")
    top = resumir_con_groq(top)

    # 5. Construir HTML
    html_email = construir_html(top)

    # 6. Enviar
    enviar_email(html_email, top)

    elapsed = round(time.time() - inicio, 1)
    print(f"\n{'='*58}")
    print(f"  OK  Completado en {elapsed} segundos")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    main()
