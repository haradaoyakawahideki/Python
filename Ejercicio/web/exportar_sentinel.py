"""Mosaico Sentinel-2 L2A sin nubes de Río Tambo (sep-oct 2026), en color real y falso color, para la web."""
import base64
import io
import json

import geopandas as gpd
import matplotlib
import numpy as np
import odc.stac
import planetary_computer as pc
import pystac_client
from rasterio import features

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

d = gpd.read_file("datos/distritos.geojson").to_crs(4326)
rt = d[(d.NOMBDIST == "RIO TAMBO") & (d.NOMBPROV == "SATIPO")]
x0, y0, x1, y1 = rt.total_bounds
x0, y0, x1, y1 = x0 - 0.02, y0 - 0.02, x1 + 0.02, y1 + 0.02

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
items = cat.search(collections=["sentinel-2-l2a"], bbox=[x0, y0, x1, y1], datetime="2026-09-01/2026-10-20",
                   query={"eo:cloud_cover": {"lt": 60}}).item_collection()
print(len(items), "escenas")
PASO = 0.002                     # ~220 m por píxel
ds = odc.stac.load(items, bands=["B02", "B03", "B04", "B08", "B12", "SCL"], bbox=[x0, y0, x1, y1],
                   crs="EPSG:4326", resolution=PASO, groupby="solar_day", chunks={"x": 1024, "y": 1024})
limpio = ds.SCL.isin([2, 4, 5, 6, 7])                 # sin nubes, sombras ni nieve
refl = {b: ((ds[b].astype("float32") - 1000) / 10000).where(limpio & (ds[b] > 0)) for b in ["B02", "B03", "B04", "B08", "B12"]}
med = {b: v.median("time").compute().values for b, v in refl.items()}

dentro = features.rasterize([(rt.geometry.iloc[0], 1)], out_shape=med["B04"].shape,
                            transform=ds.odc.geobox.affine).astype(bool)
print("píxeles del distrito sin dato:", round(np.isnan(med["B04"][dentro]).mean() * 100, 1), "%")


def png(r, g, b, escalas):
    rgb = np.dstack([np.clip(np.nan_to_num(c) / e, 0, 1) ** 0.8 for c, e in zip((r, g, b), escalas)])
    rgba = np.dstack([rgb, (dentro & ~np.isnan(r)).astype(float)])
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


lon, lat = ds.longitude.values, ds.latitude.values
s2 = {
    "real": png(med["B04"], med["B03"], med["B02"], (0.12, 0.11, 0.10)),
    "falso": png(med["B12"], med["B08"], med["B04"], (0.30, 0.45, 0.12)),
    "bbox": [float(lon.min() - PASO / 2), float(lat.min() - PASO / 2), float(lon.max() + PASO / 2), float(lat.max() + PASO / 2)],
    "fechas": sorted({i.datetime.strftime("%Y-%m-%d") for i in items}),
}
open("web/sentinel.js", "w").write("const S2=" + json.dumps(s2, separators=(",", ":")) + ";")
print("kB:", (len(s2["real"]) + len(s2["falso"])) // 1024, "| fechas:", s2["fechas"])
