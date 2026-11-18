"""
Verifica que las URLs del sitio respondan como tienen que responder.

Uso:   python verificar_urls.py https://<servicio>.run.app

Comprueba, SIN seguir redirecciones:
- Las 7 páginas responden 200 directo (sin barra final y sin redirección).
- /hierros/ y /hierros.html redirigen (301) a /hierros.
- Una página inexistente devuelve 404.
- sitemap.xml y robots.txt responden 200.
"""
import sys
import urllib.error
import urllib.request
from urllib.parse import quote


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


abrir = urllib.request.build_opener(SinRedireccion).open

PRUEBAS = [
    ("/", 200, None),
    ("/hierros", 200, None),
    ("/tubos", 200, None),
    ("/caños-estructurales", 200, None),
    ("/perfiles", 200, None),
    ("/chapas", 200, None),
    ("/chapa-para-techos", 200, None),
    ("/sitemap.xml", 200, None),
    ("/robots.txt", 200, None),
    ("/hierros/", 301, "/hierros"),
    ("/hierros.html", 301, "/hierros"),
    ("/caños-estructurales.html", 301, "/caños-estructurales"),
    ("/index.html", 301, "/"),
    ("/pagina-que-no-existe", 404, None),
    ("/404", 404, None),
]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    base = sys.argv[1].rstrip("/")
    fallas = 0
    for ruta, esperado, destino in PRUEBAS:
        url = base + quote(ruta)
        try:
            r = abrir(urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 (verificar_urls)"}), timeout=15)
            codigo, location = r.status, r.headers.get("Location")
        except urllib.error.HTTPError as e:
            codigo, location = e.code, e.headers.get("Location")
        ok = codigo == esperado
        if ok and destino is not None:
            ok = location in (destino, quote(destino), base + destino, base + quote(destino))
        fallas += not ok
        extra = f" -> {location}" if location else ""
        print(f"{'OK   ' if ok else 'FALLA'} {codigo} {ruta}{extra}  (esperado {esperado})")
    print("\nTodo bien." if not fallas else f"\n{fallas} prueba(s) fallaron.")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
