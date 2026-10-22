"""Relieve de Río Tambo (Copernicus DEM 90 m): imagen sombreada para la web y rejilla de altitudes para el cursor."""
import base64
import io
import json

import geopandas as gpd
import matplotlib
import numpy as np
import odc.stac
import planetary_computer as pc
import pystac_client
from matplotlib.colors import LightSource, LinearSegmentedColormap
from rasterio import features

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

d = gpd.read_file("datos/distritos.geojson").to_crs(4326)
rt = d[(d.NOMBDIST == "RIO TAMBO") & (d.NOMBPROV == "SATIPO")]
x0, y0, x1, y1 = rt.total_bounds
x0, y0, x1, y1 = x0 - 0.02, y0 - 0.02, x1 + 0.02, y1 + 0.02

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
items = cat.search(collections=["cop-dem-glo-90"], bbox=[x0, y0, x1, y1]).item_collection()
PASO = 0.004                      # ~450 m: suficiente para la imagen
dem = odc.stac.load(items, bbox=[x0, y0, x1, y1], crs="EPSG:4326", resolution=PASO).data.max("time")
z = dem.values.astype("float32")
lon, lat = dem.longitude.values, dem.latitude.values
dentro = features.rasterize([(rt.geometry.iloc[0], 1)], out_shape=z.shape,
                            transform=dem.odc.geobox.affine).astype(bool)

# relieve sombreado con colores hipsométricos: valles verdes, laderas ocres, cumbres claras
cmap = LinearSegmentedColormap.from_list("hipso", ["#2f6b3a", "#6f9a4a", "#c7b56a", "#a9784a", "#7a5a44", "#e9e4dc"])
ls = LightSource(azdeg=315, altdeg=40)
rgb = ls.shade(z, cmap=cmap, vmin=200, vmax=4000, blend_mode="soft", vert_exag=0.05, dx=PASO * 111000, dy=PASO * 111000)
rgba = np.dstack([rgb[..., :3], dentro.astype(float)])
buf = io.BytesIO()
plt.imsave(buf, rgba, format="png")
img = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# rejilla gruesa (5 píxeles = ~2 km) para leer la altitud con el cursor y para la distribución por altitud
s = 5
zr = z[: z.shape[0] // s * s, : z.shape[1] // s * s].reshape(z.shape[0] // s, s, z.shape[1] // s, s).mean(axis=(1, 3))
dr = dentro[: z.shape[0] // s * s, : z.shape[1] // s * s].reshape(z.shape[0] // s, s, z.shape[1] // s, s).mean(axis=(1, 3)) > 0.5
relieve = {
    "img": img,
    "bbox": [float(lon.min() - PASO / 2), float(lat.min() - PASO / 2), float(lon.max() + PASO / 2), float(lat.max() + PASO / 2)],
    "rejilla": {"lon0": float(lon[0]), "lat0": float(lat[0]), "paso": PASO * s,
                "z": [[int(v) if m else None for v, m in zip(fila, mf)] for fila, mf in zip(zr, dr)]},
    "z_distrito": [int(v) for v in z[dentro][::7]],  # muestra para la distribución de altitudes del distrito
}
open("web/relieve.js", "w").write("const RELIEVE=" + json.dumps(relieve, separators=(",", ":")) + ";")
print("altitud del distrito: min", int(z[dentro].min()), "mediana", int(np.median(z[dentro])), "max", int(z[dentro].max()),
      "| imagen", z.shape, "| kB", len(img) // 1024)

# altitud exacta (90 m remuestreado a ~450 m) de cada foco de los últimos 7 días, en el orden de clima.js
clima = json.loads(open("web/clima.js").read()[len("const CLIMA="):-1])
focos_z = [int(dem.sel(longitude=f[0], latitude=f[1], method="nearest").values) for f in clima["focos7"]]
relieve["focos_z"] = focos_z
open("web/relieve.js", "w").write("const RELIEVE=" + json.dumps(relieve, separators=(",", ":")) + ";")
print("focos: mediana", int(np.median(focos_z)), "m | bajo 1000 m:", round(np.mean(np.array(focos_z) < 1000) * 100), "%",
      "| distrito bajo 1000 m:", round(np.mean(z[dentro] < 1000) * 100), "%")
