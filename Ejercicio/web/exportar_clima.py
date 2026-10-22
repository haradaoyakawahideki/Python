"""Escribe web/clima.js: lluvia ERA5 por celda y año, viento horario y focos FIRMS de los últimos 7 días."""
import json

import geopandas as gpd
import pandas as pd

c = json.load(open("datos/clima/open_meteo.json"))
d = gpd.read_file("datos/distritos.geojson").to_crs(4326)
rt = d[(d.NOMBDIST == "RIO TAMBO") & (d.NOMBPROV == "SATIPO")]

f = pd.read_csv("datos/firms/SUOMI_VIIRS_C2_South_America_7d.csv")
f["local"] = (pd.to_datetime(f.acq_date + " " + f.acq_time.astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
              - pd.Timedelta(hours=5))
g = gpd.GeoDataFrame(f, geometry=gpd.points_from_xy(f.longitude, f.latitude), crs=4326)
g = gpd.sjoin(g, rt[["geometry"]], predicate="within")
focos7 = [[round(r.longitude, 4), round(r.latitude, 4), r.local.strftime("%Y-%m-%dT%H:%M"), round(r.frp, 1)]
          for r in g.itertuples()]

v = c["viento"]
clima = {
    "lluvia": {"celdas": c["lluvia_celdas"], "paso": 0.25, "mm": c["lluvia"]},
    "lluvia7": {"celdas": c["viento_celdas"], "paso": 0.15, "horas": v["horas"], "pp": v["pp"]},
    "focos7": focos7,
}
open("web/clima.js", "w").write("const CLIMA=" + json.dumps(clima, separators=(",", ":")) + ";")
print(len(focos7), "focos en 7 días")
