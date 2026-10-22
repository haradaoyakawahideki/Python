"""Lluvia (ERA5, 1-15 oct 2012-2026) y viento (últimos 7 días) de Open-Meteo para Río Tambo."""
import json
import time

import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import box

distritos = gpd.read_file("datos/distritos.geojson").to_crs(4326)
rt = distritos[(distritos.NOMBDIST == "RIO TAMBO") & (distritos.NOMBPROV == "SATIPO")].geometry.iloc[0]
x0, y0, x1, y1 = rt.bounds


def rejilla(paso, sobre=0.0):
    """Centros de celda que tocan el distrito."""
    xs = np.arange(np.floor(x0 / paso) * paso, x1 + paso, paso)
    ys = np.arange(np.floor(y0 / paso) * paso, y1 + paso, paso)
    return [(round(float(x), 3), round(float(y), 3)) for y in ys for x in xs
            if box(x - paso / 2, y - paso / 2, x + paso / 2, y + paso / 2).buffer(sobre).intersects(rt)]


def pedir(url, celdas, **params):
    out = []
    for i in range(0, len(celdas), 50):
        lote = celdas[i:i + 50]
        r = requests.get(url, params={"latitude": ",".join(str(c[1]) for c in lote),
                                      "longitude": ",".join(str(c[0]) for c in lote), **params}, timeout=120)
        r.raise_for_status()
        j = r.json()
        out += j if isinstance(j, list) else [j]
        time.sleep(1)
    return out


# ERA5 tiene celdas de 0,25°: pedimos los centros de esas celdas
lluvia_celdas = rejilla(0.25)
lluvia = {}
for anio in range(2012, 2027):
    res = pedir("https://archive-api.open-meteo.com/v1/archive", lluvia_celdas, models="era5",
                start_date=f"{anio}-10-01", end_date=f"{anio}-10-15", daily="precipitation_sum",
                timezone="America/Lima")
    lluvia[anio] = [round(sum(v or 0 for v in r["daily"]["precipitation_sum"]), 1) for r in res]
    print(anio, "mm promedio:", round(np.mean(lluvia[anio]), 1))

viento_celdas = rejilla(0.15)
res = pedir("https://api.open-meteo.com/v1/forecast", viento_celdas, past_days=7, forecast_days=1,
            hourly="wind_speed_10m,wind_direction_10m,relative_humidity_2m,precipitation",
            timezone="America/Lima")
viento = {
    "horas": res[0]["hourly"]["time"],
    "vel": [r["hourly"]["wind_speed_10m"] for r in res],
    "dir": [r["hourly"]["wind_direction_10m"] for r in res],
    "hr": [r["hourly"]["relative_humidity_2m"] for r in res],
    "pp": [r["hourly"]["precipitation"] for r in res],
}
print("viento:", len(viento_celdas), "celdas,", viento["horas"][0], "->", viento["horas"][-1])

json.dump({"lluvia_celdas": lluvia_celdas, "lluvia": lluvia,
           "viento_celdas": viento_celdas, "viento": viento},
          open("datos/clima/open_meteo.json", "w"))
