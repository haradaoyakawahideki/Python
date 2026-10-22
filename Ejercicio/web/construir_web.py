"""Arma la página: exporta los focos de Río Tambo (datos.js) y une plantilla + datos en web/index.html y docs/index.html.

Requiere haber corrido antes exportar_clima.py, exportar_relieve.py y exportar_sentinel.py.
Correr desde la carpeta Ejercicio/.
"""
import base64
import glob
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

d = gpd.read_file("datos/distritos.geojson").to_crs(4326)
satipo = d[d.NOMBPROV == "SATIPO"]
rt = satipo[satipo.NOMBDIST == "RIO TAMBO"]

# focos S-NPP del 1 al 20 de octubre de cada año dentro de Río Tambo
firms = pd.concat(pd.read_csv(f, usecols=["latitude", "longitude", "acq_date", "acq_time", "frp"])
                  for f in sorted(glob.glob("datos/firms/viirs-snpp_*_Peru.csv")))
firms = firms.rename(columns={"latitude": "lat", "longitude": "lon", "acq_date": "fecha", "acq_time": "hora"})
inpe = pd.read_csv("datos/inpe_peru_npp_2026.csv")
inpe = inpe.assign(fecha=inpe.data_hora_gmt.str[:10], hora=inpe.data_hora_gmt.str[11:16].str.replace(":", ""),
                   frp=np.nan)[["lat", "lon", "fecha", "hora", "frp"]]
focos = pd.concat([firms, inpe])
focos = focos[(focos.fecha.str[5:7] == "10") & (focos.fecha.str[8:] <= "20")]
focos = gpd.GeoDataFrame(focos, geometry=gpd.points_from_xy(focos.lon, focos.lat), crs=4326)
focos = gpd.sjoin(focos, rt[["geometry"]], predicate="within")


def anillos(geom):
    geom = geom.simplify(0.002)
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return [[[round(x, 4), round(y, 4)] for x, y in p.exterior.coords] for p in polys]


datos = {
    "rt": anillos(rt.geometry.iloc[0]),
    "vecinos": [{"n": r.NOMBDIST.title(), "r": anillos(r.geometry)} for r in satipo[satipo.NOMBDIST != "RIO TAMBO"].itertuples()],
    "pts": [[round(r.lon, 4), round(r.lat, 4), int(r.fecha[:4]), int(r.fecha[8:]), str(r.hora).zfill(4),
             None if pd.isna(r.frp) else round(r.frp, 1)] for r in focos.itertuples()],
}
Path("web/datos.js").write_text("const DATOS=" + json.dumps(datos, separators=(",", ":")) + ";")

# la imagen de relieve no se usa en la página (el fondo es Sentinel-2): se quita para aligerarla
relieve = json.loads(Path("web/relieve.js").read_text()[len("const RELIEVE="):-1])
relieve.pop("img", None)

html = (Path("web/plantilla.html").read_text()
        .replace("/*DATOS*/", Path("web/datos.js").read_text())
        .replace("/*CLIMA*/", Path("web/clima.js").read_text())
        .replace("/*RELIEVE*/", "const RELIEVE=" + json.dumps(relieve, separators=(",", ":")) + ";")
        .replace("/*S2*/", Path("web/sentinel.js").read_text())
        .replace("/*DNBR*/", "data:image/png;base64," + base64.b64encode(Path("figuras/rio_tambo_dnbr.png").read_bytes()).decode()))
Path("web/index.html").write_text(html)

# GitHub Pages publica la carpeta docs/ de la raíz del repositorio
docs = Path("../docs")
docs.mkdir(exist_ok=True)
# la plantilla no trae doctype ni metas (el artifact de Claude los agrega); para Pages se los ponemos
pagina = ("<!doctype html>\n<html lang=\"es\">\n<meta charset=\"utf-8\">\n"
          "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
          + html + "\n</html>\n")
(docs / "index.html").write_text(pagina)
print(f"{len(datos['pts'])} focos · web/index.html {len(html) // 1024} kB · docs/index.html listo")
