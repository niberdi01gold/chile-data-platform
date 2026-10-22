"""Genera la página de estado pública (site/index.html) a partir de la base de datos.

Uso:
    python src/estado.py
Lee data/warehouse.duckdb y escribe site/index.html y site/estado.json.
"""

import html
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
BD = RAIZ / "data" / "warehouse.duckdb"
SALIDA = RAIZ / "site"
CHILE = ZoneInfo("America/Santiago")

NOMBRES = {
    "dolar": "Dólar observado", "euro": "Euro", "uf": "UF", "libra_cobre": "Cobre (USD/lb)",
    "tpm": "Tasa de Política Monetaria", "utm": "UTM", "ipc": "IPC (variación mensual)",
    "imacec": "IMACEC (variación anual)", "tasa_desempleo": "Tasa de desempleo",
}


def leer_datos():
    con = duckdb.connect(str(BD), read_only=True)
    filas = con.sql("""
        select r.indicador, r.unidad_medida, r.fecha_ultimo_valor, r.ultimo_valor,
               r.tipo_variacion, r.variacion_30d, r.variacion_12m,
               g.frecuencia, g.max_dias_sin_datos,
               current_date - r.fecha_ultimo_valor as dias_sin_datos
        from resumen_indicadores r
        join reglas_indicadores g using (indicador)
        order by g.frecuencia, r.indicador
    """).fetchall()
    columnas = ["indicador", "unidad", "fecha", "valor", "tipo_variacion", "var_30d",
                "var_12m", "frecuencia", "max_dias", "dias_sin_datos"]
    indicadores = [dict(zip(columnas, f)) for f in filas]

    for ind in indicadores:
        serie = con.execute("""
            select valor from historico_indicadores
            where indicador = ? and fecha <= current_date
            order by fecha desc limit ?
        """, [ind["indicador"], 90 if ind["frecuencia"] == "diaria" else 24]).fetchall()
        ind["serie"] = [v[0] for v in reversed(serie)]
        ind["al_dia"] = ind["dias_sin_datos"] <= ind["max_dias"]
    con.close()
    return indicadores


def minigrafico(valores, ancho=160, alto=40):
    """Dibuja la serie como una línea SVG (sin JavaScript)."""
    if len(valores) < 2:
        return ""
    minimo, maximo = min(valores), max(valores)
    rango = (maximo - minimo) or 1
    puntos = " ".join(
        f"{i * ancho / (len(valores) - 1):.1f},{alto - 4 - (v - minimo) / rango * (alto - 8):.1f}"
        for i, v in enumerate(valores)
    )
    return (f'<svg viewBox="0 0 {ancho} {alto}" class="spark" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{puntos}" /></svg>')


def formato(valor, unidad):
    if unidad == "Porcentaje":
        return f"{valor:.2f} %".replace(".", ",")
    if unidad == "Dólar":
        return f"US$ {valor:.2f}".replace(".", ",")
    return "$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def variacion(valor, tipo):
    if valor is None:
        return "—"
    signo = "+" if valor > 0 else ""
    sufijo = " pts" if tipo == "puntos" else " %"
    return f"{signo}{valor:.2f}{sufijo}".replace(".", ",")


def generar_html(indicadores, generado, url_run):
    todos_ok = all(i["al_dia"] for i in indicadores)
    atrasados = [NOMBRES[i["indicador"]] for i in indicadores if not i["al_dia"]]
    resumen = ("Todos los indicadores están al día" if todos_ok
               else f"Atrasados: {', '.join(atrasados)}")

    tarjetas = []
    for i in indicadores:
        estado = "ok" if i["al_dia"] else "atrasado"
        tarjetas.append(f"""
        <article class="tarjeta {estado}">
          <header>
            <span class="punto" title="{'Al día' if i['al_dia'] else 'Atrasado'}"></span>
            <h2>{html.escape(NOMBRES[i['indicador']])}</h2>
          </header>
          <p class="valor">{formato(i['valor'], i['unidad'])}</p>
          {minigrafico(i['serie'])}
          <dl>
            <div><dt>30 días</dt><dd>{variacion(i['var_30d'], i['tipo_variacion'])}</dd></div>
            <div><dt>12 meses</dt><dd>{variacion(i['var_12m'], i['tipo_variacion'])}</dd></div>
          </dl>
          <p class="fecha">Último dato: {i['fecha']:%d-%m-%Y} · {i['frecuencia']} ·
             {i['dias_sin_datos']} de {i['max_dias']} días permitidos</p>
        </article>""")

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado · Chile Data Platform</title>
<style>
  :root {{ --fondo:#f6f7f9; --tarjeta:#fff; --texto:#1b1f24; --suave:#5b6470; --borde:#e2e5e9;
          --ok:#1a7f37; --mal:#cf222e; --linea:#3b5bdb; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fondo:#0d1117; --tarjeta:#161b22; --texto:#e6edf3; --suave:#8b949e; --borde:#30363d;
            --ok:#3fb950; --mal:#f85149; --linea:#79a1ff; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--fondo); color:var(--texto);
         font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  main {{ max-width:1100px; margin:0 auto; padding:32px 16px 48px; }}
  h1 {{ margin:0 0 4px; font-size:26px; }}
  .sub {{ color:var(--suave); margin:0 0 20px; }}
  .banner {{ padding:14px 18px; border-radius:10px; font-weight:600; margin-bottom:24px;
            border:1px solid var(--borde); background:var(--tarjeta); }}
  .banner.ok {{ border-left:6px solid var(--ok); }} .banner.mal {{ border-left:6px solid var(--mal); }}
  .grilla {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); }}
  .tarjeta {{ background:var(--tarjeta); border:1px solid var(--borde); border-radius:10px; padding:16px; }}
  .tarjeta header {{ display:flex; align-items:center; gap:8px; }}
  .tarjeta h2 {{ font-size:14px; margin:0; color:var(--suave); font-weight:600; }}
  .punto {{ width:10px; height:10px; border-radius:50%; background:var(--ok); flex:none; }}
  .atrasado .punto {{ background:var(--mal); }}
  .valor {{ font-size:24px; font-weight:700; margin:8px 0 4px; font-variant-numeric:tabular-nums; }}
  .spark {{ width:100%; height:40px; }} .spark polyline {{ fill:none; stroke:var(--linea); stroke-width:1.6; vector-effect:non-scaling-stroke; }}
  dl {{ display:flex; gap:20px; margin:8px 0; }} dl div {{ display:flex; flex-direction:column; }}
  dt {{ font-size:12px; color:var(--suave); }} dd {{ margin:0; font-weight:600; font-variant-numeric:tabular-nums; }}
  .fecha {{ font-size:12px; color:var(--suave); margin:6px 0 0; }}
  footer {{ margin-top:28px; color:var(--suave); font-size:13px; }}
  a {{ color:var(--linea); }}
</style>
</head>
<body>
<main>
  <h1>Chile Data Platform · Estado</h1>
  <p class="sub">Indicadores económicos oficiales del Banco Central de Chile, actualizados y validados cada día.</p>
  <div class="banner {'ok' if todos_ok else 'mal'}">{'🟢' if todos_ok else '🔴'} {html.escape(resumen)}</div>
  <section class="grilla">{''.join(tarjetas)}
  </section>
  <footer>
    Generado el {generado:%d-%m-%Y %H:%M} (hora de Chile){f' · <a href="{url_run}">ver ejecución</a>' if url_run else ''} ·
    <a href="https://chile-data-platform.onrender.com/docs">API</a> ·
    <a href="https://github.com/niberdi01gold/chile-data-platform">código</a><br>
    Un indicador está "al día" si su último dato no supera los días permitidos por su calendario de publicación.
  </footer>
</main>
</body>
</html>"""


def main():
    indicadores = leer_datos()
    generado = datetime.now(CHILE)
    url_run = None
    if os.getenv("GITHUB_RUN_ID"):        # dentro de GitHub Actions: enlace a la ejecución
        url_run = (f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}"
                   f"/actions/runs/{os.getenv('GITHUB_RUN_ID')}")

    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "index.html").write_text(generar_html(indicadores, generado, url_run), encoding="utf-8")
    estado = {
        "generado": generado.isoformat(),
        "todos_al_dia": all(i["al_dia"] for i in indicadores),
        "indicadores": [{k: (str(v) if k == "fecha" else v) for k, v in i.items() if k != "serie"}
                        for i in indicadores],
    }
    (SALIDA / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Página generada en {SALIDA / 'index.html'} · {len(indicadores)} indicadores")


if __name__ == "__main__":
    main()
