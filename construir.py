"""
Arma las páginas completas del sitio a partir de las piezas de `fuente/`.

Uso:   python construir.py            → versión de producción en sitio/
       python construir.py --preview  → versión de prueba en preview/ (servicio aparte)
       python construir.py --preview --base /indartubo-web
                                      → versión de prueba para una subcarpeta (GitHub Pages:
                                        https://<usuario>.github.io/indartubo-web/)

- Lee `fuente/config.json` (ID de GTM, URL del formulario, URL del sitio).
- Junta cada página de `fuente/paginas/` con las piezas de `fuente/_partes/`.
- Copia `fuente/estaticos/` (css, js, img, fuentes) tal cual.
- Escribe todo en `sitio/`, que es lo que se publica. No editar `sitio/` a mano:
  se borra y se vuelve a generar cada vez.

Sintaxis dentro de páginas y piezas:
  {{ nombre }}           valor de config.json o de la cabecera de la página
  {{> pieza }}           inserta fuente/_partes/pieza.html
  {{ asset css/x.css }}  ruta al archivo con ?v=<huella> para que el navegador
                         descargue la versión nueva cuando cambia

Cabecera de cada página (entre líneas ---):
  titulo, descripcion, ruta (ej. /hierros), plantilla (por defecto: base),
  sitemap (si/no, por defecto si) y cualquier otro dato que use la plantilla.
  producto: Hierros   → esa opción queda seleccionada en el formulario.
  ejemplo_consulta: … → reemplaza el ejemplo del campo Consulta (default en config.json).

Versión de prueba (--preview), para el servicio indartubo-preview:
  noindex en todas las páginas (meta + encabezado X-Robots-Tag en su nginx), robots.txt
  con Disallow: /, GTM desactivado, franja "Versión de prueba" arriba y el formulario no
  envía nada (muestra un aviso). Cliengo queda activo. preview/ trae su propio Dockerfile
  y nginx.conf: se deploya con  gcloud run deploy indartubo-preview --source preview

--base /carpeta (solo junto con --preview): para publicar en una subcarpeta. Antepone la
  carpeta a los links internos que empiezan con "/" (ej. /hierros → /indartubo-web/hierros)
  y al <base> de la 404. CSS, JS, fuentes e imágenes ya usan rutas relativas.

Además, en cada página: los links del menú a la página actual llevan
aria-current="page", y en "Otros productos" se quita el producto actual
(bloques marcados en _partes/otros-productos.html).
"""
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

for _flujo in (sys.stdout, sys.stderr):  # acentos bien en la consola de Windows
    if hasattr(_flujo, "reconfigure"):
        _flujo.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent
FUENTE = RAIZ / "fuente"
PARTES = FUENTE / "_partes"
PAGINAS = FUENTE / "paginas"
ESTATICOS = FUENTE / "estaticos"
SALIDA = RAIZ / "sitio"
PREVIEW = "--preview" in sys.argv[1:]
if PREVIEW:
    DIR_PREVIEW = RAIZ / "preview"
    SALIDA = DIR_PREVIEW / "sitio"
FRANJA_PRUEBA = '<div class="franja-prueba" role="note">Versión de prueba</div>'


def _leer_base() -> str:
    """--base /carpeta → "/carpeta" (sin barra final). Vacío si no se pasa."""
    args = sys.argv[1:]
    if "--base" not in args:
        return ""
    i = args.index("--base")
    if i + 1 >= len(args) or not args[i + 1].startswith("/"):
        sys.exit("ERROR: --base necesita una carpeta que empiece con /, ej.: --base /indartubo-web")
    if not PREVIEW:
        sys.exit("ERROR: --base solo se usa junto con --preview (producción va en la raíz del dominio)")
    return args[i + 1].rstrip("/")


BASE = _leer_base()  # ej. "/indartubo-web" para GitHub Pages; "" en producción

RE_PIEZA = re.compile(r"\{\{>\s*([\w-]+)\s*\}\}")
RE_ASSET = re.compile(r"\{\{\s*asset\s+([^\s}]+)\s*\}\}")
RE_VAR = re.compile(r"\{\{\s*([\w]+)\s*\}\}")
RE_FOTO = re.compile(r"\{\{\s*foto\s+([\w-]+)\s+([\d,]+)\s*\}\}")
DIR_FOTOS = "img/fotos"          # copias locales: img/fotos/<nombre>-<ancho>.webp
CARPETA_CLOUDINARY = "indartubo"  # carpeta en Cloudinary: indartubo/<nombre>
CLOUDINARY = ""                  # cloud name (se toma de config.json en main)


def url_foto(nombre: str, ancho: int, origen: str = "") -> str:
    """URL de una foto a un ancho dado: Cloudinary si hay cloud name, si no la copia local."""
    if CLOUDINARY:
        return (f"https://res.cloudinary.com/{CLOUDINARY}/image/upload/"
                f"f_auto,q_auto,c_limit,w_{ancho}/{CARPETA_CLOUDINARY}/{nombre}")
    rel = f"{DIR_FOTOS}/{nombre}-{ancho}.webp"
    if not (ESTATICOS / rel).is_file():
        raise ErrorArmado(f"{origen}: falta la foto local {rel}")
    return rel


def atributos_foto(m, origen: str) -> str:
    nombre, anchos = m.group(1), [int(a) for a in m.group(2).split(",")]
    srcset = ", ".join(f"{url_foto(nombre, a, origen)} {a}w" for a in anchos)
    return f'src="{url_foto(nombre, anchos[-1], origen)}" srcset="{srcset}"'


class ErrorArmado(Exception):
    pass


def leer(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def separar_cabecera(texto: str, origen: str):
    if not texto.startswith("---"):
        raise ErrorArmado(f"{origen}: falta la cabecera entre líneas ---")
    _, cab, cuerpo = texto.split("---", 2)
    datos = {}
    for linea in cab.strip().splitlines():
        if not linea.strip() or linea.strip().startswith("#"):
            continue
        clave, _, valor = linea.partition(":")
        datos[clave.strip()] = valor.strip()
    return datos, cuerpo.strip("\n")


def huella(rel: str) -> str:
    archivo = ESTATICOS / rel
    if not archivo.is_file():
        raise ErrorArmado(f"asset inexistente: {rel}")
    return hashlib.sha1(archivo.read_bytes()).hexdigest()[:8]


def expandir(texto: str, datos: dict, origen: str, pila=()) -> str:
    def pieza(m):
        nombre = m.group(1)
        if PREVIEW and nombre in ("gtm-head", "gtm-body"):
            return "<!-- GTM desactivado en la versión de prueba -->"
        if nombre in pila:
            raise ErrorArmado(f"{origen}: la pieza '{nombre}' se incluye a sí misma")
        archivo = PARTES / f"{nombre}.html"
        if not archivo.is_file():
            raise ErrorArmado(f"{origen}: no existe la pieza _partes/{nombre}.html")
        return expandir(leer(archivo), datos, f"_partes/{nombre}.html", pila + (nombre,))

    texto = RE_PIEZA.sub(pieza, texto)
    texto = RE_ASSET.sub(lambda m: f"{m.group(1)}?v={huella(m.group(1))}", texto)
    texto = RE_FOTO.sub(lambda m: atributos_foto(m, origen), texto)

    def var(m):
        clave = m.group(1)
        if clave not in datos:
            raise ErrorArmado(f"{origen}: la variable '{{{{ {clave} }}}}' no está definida")
        return str(datos[clave])

    return RE_VAR.sub(var, texto)


def archivo_de_ruta(ruta: str) -> str:
    if not ruta.startswith("/"):
        raise ErrorArmado(f"ruta inválida '{ruta}': tiene que empezar con /")
    if ruta == "/":
        return "index.html"
    return ruta.strip("/") + ".html"


def meta_extra(cab: dict, datos: dict, sitio_url: str, origen: str) -> str:
    """Etiquetas del <head> que dependen de la página: canonical o noindex,
    imagen para redes (og:image) y preconnect a Cloudinary."""
    lineas = []
    if PREVIEW:
        lineas.append('<meta name="robots" content="noindex, nofollow">')
    elif cab.get("noindex") == "si":
        lineas.append('<meta name="robots" content="noindex">')
    if cab.get("base"):  # 404: se sirve en cualquier ruta (/a/b/c): rutas relativas desde la raíz
        lineas.append(f'<base href="{cab["base"]}">')  # con --base, ajustes_por_pagina le antepone la carpeta
    else:
        lineas.append('<link rel="canonical" href="%s">' % datos["url_canonica"])
    if cab.get("foto_redes"):
        nombre = cab["foto_redes"]
        if CLOUDINARY:
            img = (f"https://res.cloudinary.com/{CLOUDINARY}/image/upload/"
                   f"f_jpg,q_auto,c_fill,w_1200,h_630/{CARPETA_CLOUDINARY}/{nombre}")
        else:
            img = f"{sitio_url}/{url_foto(nombre, 800, origen)}"
        lineas.append(f'<meta property="og:image" content="{img}">')
        lineas.append(f'<meta name="twitter:image" content="{img}">')
    if CLOUDINARY:
        lineas.append('<link rel="preconnect" href="https://res.cloudinary.com">')
    return "\n".join(lineas)


RE_OTRO = re.compile(r"[ \t]*<!-- otro:(\S+) -->(.*?)<!-- /otro -->\n?", re.S)


def ajustes_por_pagina(html: str, cab: dict, origen: str) -> str:
    """Retoques que dependen de la página (funcionan sin JS en el navegador):
    - cabecera 'producto: X' → esa opción queda seleccionada en el formulario;
    - links del menú a la página actual → aria-current="page";
    - bloques <!-- otro:/ruta --> ... <!-- /otro --> → se quita el de la página actual;
    - sin formulario en la página: href="#presupuesto" pasa a "/#presupuesto".
    """
    ruta = cab["ruta"]
    producto = cab.get("producto")
    if producto:
        opcion = f"<option>{producto}</option>"
        if opcion not in html:
            raise ErrorArmado(f"{origen}: el producto '{producto}' no está entre las opciones del formulario")
        html = html.replace(opcion, f"<option selected>{producto}</option>", 1)
    if ruta != "/":
        html = html.replace(f'<a href="{ruta}">', f'<a href="{ruta}" aria-current="page">')
    if "<form" not in html:  # página sin formulario (ej. 404): los "presupuesto" van al de la home
        html = html.replace('href="#presupuesto"', 'href="/#presupuesto"')
    if BASE:  # subcarpeta (GitHub Pages): links internos "/x" → "/carpeta/x" (no toca "//dominio")
        html = re.sub(r'href="/(?!/)', f'href="{BASE}/', html)
    if PREVIEW:  # franja arriba y formulario que no envía (main.js muestra un aviso)
        html = html.replace("<body>\n", "<body>\n" + FRANJA_PRUEBA + "\n", 1)
        html = html.replace('<form class="formulario"', '<form class="formulario" data-prueba="si"')
    return RE_OTRO.sub(lambda m: "" if m.group(1) == ruta else m.group(2).strip("\n") + "\n", html)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    global CLOUDINARY
    config = json.loads(leer(FUENTE / "config.json"))
    sitio_url = config["sitio_url"].rstrip("/")
    CLOUDINARY = config.get("cloudinary_cloud_name", "").strip()
    if PREVIEW:
        config["form_endpoint"] = ""  # la versión de prueba nunca envía datos

    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    shutil.copytree(ESTATICOS, SALIDA)

    urls_sitemap = []
    for pagina in sorted(PAGINAS.glob("*.html")):
        cab, cuerpo = separar_cabecera(leer(pagina), pagina.name)
        for obligatorio in ("titulo", "descripcion", "ruta"):
            if obligatorio not in cab:
                raise ErrorArmado(f"{pagina.name}: falta '{obligatorio}' en la cabecera")
        ruta = cab["ruta"]
        datos = {
            **{k: v for k, v in config.items() if not k.startswith("_")},
            **cab,
            "anio": date.today().year,
            "url_canonica": sitio_url + quote(ruta),  # la ñ va codificada (%C3%B1)
        }
        datos["meta_extra"] = meta_extra(cab, datos, sitio_url, pagina.name)
        datos["contenido"] = expandir(cuerpo, datos, pagina.name)
        plantilla = PARTES / f"{cab.get('plantilla', 'base')}.html"
        html = expandir(leer(plantilla), datos, pagina.name)
        html = ajustes_por_pagina(html, cab, pagina.name)
        destino = SALIDA / archivo_de_ruta(ruta)
        destino.write_text(html, encoding="utf-8", newline="\n")
        if cab.get("sitemap", "si") != "no":
            urls_sitemap.append(sitio_url + quote(ruta))
        print(f"  {ruta:<24} -> {destino.relative_to(RAIZ).as_posix()}")

    hoy = date.today().isoformat()
    filas = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{hoy}</lastmod></url>" for u in urls_sitemap
    )
    (SALIDA / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{filas}\n</urlset>\n",
        encoding="utf-8",
        newline="\n",
    )
    robots = ("User-agent: *\nDisallow: /\n" if PREVIEW
              else f"User-agent: *\nAllow: /\n\nSitemap: {sitio_url}/sitemap.xml\n")
    (SALIDA / "robots.txt").write_text(robots, encoding="utf-8", newline="\n")

    if PREVIEW:
        # Carpeta autosuficiente para Cloud Run: Dockerfile + nginx.conf con noindex por encabezado.
        shutil.copy2(RAIZ / "Dockerfile", DIR_PREVIEW / "Dockerfile")
        conf = leer(RAIZ / "nginx.conf")
        marca = "    server_tokens off;\n"
        if marca not in conf:
            raise ErrorArmado("nginx.conf: no encuentro 'server_tokens off;' para sumar X-Robots-Tag")
        conf = conf.replace(marca, marca + '    add_header X-Robots-Tag "noindex, nofollow" always;  # versión de prueba\n', 1)
        (DIR_PREVIEW / "nginx.conf").write_text(conf, encoding="utf-8", newline="\n")
        print("Listo: versión de PRUEBA en preview/ (abrí preview/sitio/index.html para verla).")
        print("Deploy: gcloud run deploy indartubo-preview --source preview  (ver CLAUDE.md)")
    else:
        print(f"Listo: {len(urls_sitemap)} páginas en el sitemap. Abrí sitio/index.html para verlo.")


if __name__ == "__main__":
    try:
        main()
    except ErrorArmado as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
