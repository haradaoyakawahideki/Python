# %% [markdown]
# # Incendios en el Perú 2026: ¿año récord? y el incendio de Río Tambo
#
# **Pregunta (reto E).** ¿Fue 2026 un año récord de focos de calor en el Perú y en qué
# departamentos? Para cumplir el mínimo, también **medimos el área quemada del incendio de
# Río Tambo (Satipo, Junín) con dNBR de Sentinel-2**.
#
# Plan:
# 1. Focos VIIRS S-NPP 2012–2025 (NASA FIRMS) y 2026 (INPE Queimadas, porque FIRMS aún no
#    publica el archivo anual de 2026 sin clave).
# 2. Calibrar INPE contra FIRMS en los días que ambos cubren.
# 3. Comparar el 1 ene–20 oct de cada año, por departamento.
# 4. Sentinel-2 L2A en la zona de Río Tambo: NBR, dNBR, máscara de nubes con SCL, hectáreas.

# %%
import glob
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import odc.stac
from rasterio import features
from scipy import ndimage

warnings.filterwarnings("ignore")
pd.set_option("display.float_format", lambda v: f"{v:,.1f}")
plt.rcParams.update({"figure.dpi": 110, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})

CORTE = "10-20"          # comparamos cada año del 1 de enero al 20 de octubre
FIG = "figuras"

# %% [markdown]
# ## 1 · Los datos de focos
#
# Las descargas están en `descargar_datos.sh`. FIRMS trae una fila por foco con `type`:
# 0 = vegetación probable, 1 = volcán, 2 = otra fuente fija, 3 = mar. INPE no trae `type`,
# así que para comparar igual con igual usamos **todos** los focos en ambos y luego probamos
# quitar las fuentes fijas de FIRMS como robustez.

# %%
deptos = gpd.read_file("datos/departamentos.geojson")[["NOMBDEP", "geometry"]].to_crs(4326)

firms = pd.concat(
    pd.read_csv(f, usecols=["latitude", "longitude", "acq_date", "type"])
    for f in sorted(glob.glob("datos/firms/viirs-snpp_*_Peru.csv"))
).rename(columns={"latitude": "lat", "longitude": "lon", "acq_date": "fecha"})
firms["fuente"] = "FIRMS"

inpe = pd.read_csv("datos/inpe_peru_npp_2026.csv")
inpe = inpe.assign(fecha=inpe.data_hora_gmt.str[:10], type=np.nan, fuente="INPE")[
    ["lat", "lon", "fecha", "type", "fuente"]]

focos = pd.concat([firms, inpe], ignore_index=True)
focos["anio"] = focos.fecha.str[:4].astype(int)
focos = gpd.GeoDataFrame(focos, geometry=gpd.points_from_xy(focos.lon, focos.lat), crs=4326)
focos = gpd.sjoin(focos, deptos, predicate="within").drop(columns="index_right")

print(f"{len(focos):,} focos dentro del Perú")
print(focos.groupby(["anio", "fuente"]).size().unstack().fillna(0).astype(int).T.to_string())

# %% [markdown]
# ## 2 · Calibración: ¿INPE cuenta lo mismo que FIRMS?
#
# Si 2026 viene de otra fuente, un «récord» podría ser solo un cambio de fuente. FIRMS publica
# sin clave los últimos 7 días (`South America 7d`), así que comparamos día por día.

# %%
f7 = pd.read_csv("datos/firms/SUOMI_VIIRS_C2_South_America_7d.csv",
                 usecols=["latitude", "longitude", "acq_date"])
f7 = gpd.GeoDataFrame(f7, geometry=gpd.points_from_xy(f7.longitude, f7.latitude), crs=4326)
f7 = gpd.sjoin(f7, deptos, predicate="within")

dias = sorted(set(f7.acq_date) & set(inpe.fecha))
foc26 = focos[focos.fuente == "INPE"]
calib = pd.DataFrame({
    "FIRMS": f7.groupby("acq_date").size().reindex(dias),
    "INPE": foc26.groupby("fecha").size().reindex(dias),
}).fillna(0).astype(int)
calib["dif_%"] = 100 * (calib.INPE / calib.FIRMS - 1)
total_dif = 100 * (calib.INPE.sum() / calib.FIRMS.sum() - 1)
print(calib.to_string())
print(f"\ntotal de los {len(dias)} días: INPE {calib.INPE.sum():,} vs FIRMS {calib.FIRMS.sum():,} "
      f"-> diferencia {total_dif:+.1f} %")

# %% [markdown]
# ## 3 · ¿Año récord? Perú, 1 de enero al 20 de octubre

# %%
ventana = focos[focos.fecha.str[5:] <= CORTE]
por_anio = ventana.groupby("anio").size()
historia = por_anio.loc[2012:2025]

fig, ax = plt.subplots(figsize=(8, 3.4))
colores = ["#c1663f" if a == 2026 else "#9aa7b0" for a in por_anio.index]
ax.bar(por_anio.index, por_anio.values, color=colores)
ax.axhline(historia.mean(), color="#3c4a52", lw=1, ls="--")
ax.text(2011.6, historia.mean() * 1.03, f"promedio 2012–2025: {historia.mean():,.0f}", fontsize=8)
ax.set_title("Focos de calor VIIRS S-NPP en el Perú, 1 ene – 20 oct de cada año\n"
             "2012–2025: NASA FIRMS · 2026: INPE Queimadas", fontsize=9.5)
ax.set_ylabel("focos")
ax.set_xticks(por_anio.index, [str(a)[2:] for a in por_anio.index])
plt.tight_layout()
plt.savefig(f"{FIG}/focos_por_anio.png", bbox_inches="tight")
plt.show()

# INPE cuenta más que FIRMS (sección 2): versión de 2026 corregida por esa diferencia
factor = 1 + total_dif / 100
corr_2026 = por_anio[2026] / factor
rk = por_anio.rank(ascending=False).astype(int)
print(f"2026 corregido por calibración: {corr_2026:,.0f} ({100 * (corr_2026 / historia.mean() - 1):+.0f} %)")
print(f"2026: {por_anio[2026]:,} focos | promedio 2012–2025: {historia.mean():,.0f} "
      f"({100 * (por_anio[2026] / historia.mean() - 1):+.0f} %) | "
      f"máximo previo: {historia.max():,} en {historia.idxmax()} | puesto de 2026: {rk[2026]} de {len(rk)}")

# %% [markdown]
# Lo mismo solo para el **1–20 de octubre**, el pico de la temporada:

# %%
octubre = focos[(focos.fecha.str[5:7] == "10") & (focos.fecha.str[8:] <= CORTE[3:])]
oct_anio = octubre.groupby("anio").size()
print(oct_anio.to_string())
print(f"\noctubre 2026 frente al promedio 2012–2025: "
      f"{100 * (oct_anio[2026] / oct_anio.loc[2012:2025].mean() - 1):+.0f} %  "
      f"| máximo previo {oct_anio.loc[2012:2025].max():,} ({oct_anio.loc[2012:2025].idxmax()})")
oct_corr = oct_anio[2026] / factor
print(f"corregido por calibración ({total_dif:+.1f} %): {oct_corr:,.0f} -> "
      f"{'sigue' if oct_corr > oct_anio.loc[2012:2025].max() else 'ya NO es'} récord")

# %% [markdown]
# ### Por departamento

# %%
tab = ventana.groupby(["NOMBDEP", "anio"]).size().unstack(fill_value=0)
dep = pd.DataFrame({
    "focos_2026": tab[2026],
    "prom_2012_25": tab.loc[:, 2012:2025].mean(axis=1),
    "max_previo": tab.loc[:, 2012:2025].max(axis=1),
    "anio_max_previo": tab.loc[:, 2012:2025].idxmax(axis=1),
})
dep["cambio_%"] = 100 * (dep.focos_2026 / dep.prom_2012_25 - 1)
# como con la luz en clase: el log suaviza los extremos y vuelve simétricas subidas y bajadas
# (log_dif = +0,69 es el doble; −0,69, la mitad)
dep["log_dif"] = np.log1p(dep.focos_2026) - np.log1p(dep.prom_2012_25)
dep["record"] = dep.focos_2026 > dep.max_previo
dep["record_corregido"] = dep.focos_2026 / factor > dep.max_previo
dep = dep.sort_values("focos_2026", ascending=False)
print(f"departamentos con récord en 2026: {dep.record.sum()} de {len(dep)}")
dep

# %%
mapa = deptos.merge(dep.reset_index(), on="NOMBDEP")
fig, (izq, der) = plt.subplots(1, 2, figsize=(10, 6.5))
lim = 1.0      # Callao (0 vs 9 focos) daría −2,3 y aplastaría la escala
mapa.plot(column="log_dif", cmap="RdBu_r", vmin=-lim, vmax=lim, ax=izq, edgecolor="white",
          lw=0.4, legend=True,
          legend_kwds={"label": "log(1 + focos 2026) − log(1 + promedio 2012–2025)", "shrink": 0.6})
izq.set_title("Focos 2026 frente al promedio, en logaritmos\n(1 ene – 20 oct; +0,69 = el doble)", fontsize=9.5)
izq.axis("off")
mapa.plot(color="#e8eaec", ax=der, edgecolor="white", lw=0.4)
mapa[mapa.record].plot(color="#c1663f", ax=der, edgecolor="white", lw=0.4)
for _, f in mapa[mapa.record].iterrows():
    p = f.geometry.representative_point()
    der.annotate(f.NOMBDEP.title(), (p.x, p.y), fontsize=6.5, ha="center")
der.set_title(f"Departamentos con récord 2012–2026\n({mapa.record.sum()} de {len(mapa)})", fontsize=9.5)
der.axis("off")
plt.tight_layout()
plt.savefig(f"{FIG}/mapa_departamentos.png", bbox_inches="tight")
plt.show()

# %% [markdown]
# **Robustez.** FIRMS marca algunos focos como fuentes fijas o volcanes (`type` 1–3). INPE no
# los marca, así que no podemos quitarlos en 2026. ¿Cuánto pesan en la historia?

# %%
hist = ventana[ventana.fuente == "FIRMS"]
peso_fijas = 100 * (hist["type"] != 0).mean()   # ojo: hist.type es el tipo de geometría
print(f"focos FIRMS 2012–2025 que no son vegetación (type≠0): {peso_fijas:.1f} %")
sin_fijas = hist[hist["type"] == 0].groupby("anio").size()
print(f"promedio 2012–2025 solo vegetación: {sin_fijas.mean():,.0f} (vs {historia.mean():,.0f} con todo)")

# %% [markdown]
# ## 4 · El incendio de Río Tambo con dNBR
#
# **Zona.** El distrito de Río Tambo (Satipo, Junín) mide más de 10 000 km². Los focos de octubre
# se concentran cerca de −11,87° / −73,86°, así que trabajamos en un recuadro de ~30 × 29 km
# alrededor de ese grupo.
#
# **Fechas.** La nubosidad de una escena entera no sirve: lo que importa es la nube **dentro de la
# zona**. La medimos con la capa SCL antes de elegir.

# %%
BBOX = [-74.0, -12.0, -73.72, -11.74]
distritos = gpd.read_file("datos/distritos.geojson").to_crs(4326)
rio_tambo = distritos[(distritos.NOMBDIST == "RIO TAMBO") & (distritos.NOMBPROV == "SATIPO")]

f_zona = focos.cx[BBOX[0]:BBOX[2], BBOX[1]:BBOX[3]]
f_zona = f_zona[f_zona.anio == 2026]
print("focos 2026 en la zona, por día (sep–oct):")
print(f_zona[f_zona.fecha >= "2026-09-01"].groupby("fecha").size().to_string())

# %%
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                modifier=pc.sign_inplace)
items = cat.search(collections=["sentinel-2-l2a"], bbox=BBOX,
                   datetime="2026-08-25/2026-10-21").item_collection()
scl = odc.stac.load(items, bands=["SCL"], bbox=BBOX, resolution=20, crs="EPSG:32718",
                    groupby="solar_day").SCL

NUBES = [3, 8, 9, 10]            # sombra, nube media, nube alta, cirro
nubes = pd.DataFrame({
    "fecha": [str(t)[:10] for t in scl.time.values],
    "nubes_zona_%": [100 * np.isin(scl.sel(time=t).values, NUBES).mean() for t in scl.time.values],
})
nubes

# %% [markdown]
# Elegimos:
# - **Antes: 23 sep 2026** (6,9 % de nubes en la zona), antes del salto de focos del 4 oct.
# - **Después: 8 oct 2026** (2,3 % de nubes), la imagen más limpia tras el inicio del fuego.
# - **Sensibilidad: 13 oct 2026** (30 % de nubes), que capta el crecimiento posterior.

# %%
ANTES, DESPUES, DESPUES_2 = "2026-09-23", "2026-10-08", "2026-10-13"

def cargar(fecha):
    sel = [i for i in items if i.datetime.strftime("%Y-%m-%d") == fecha]
    ds = odc.stac.load(sel, bands=["B04", "B08", "B12", "SCL"], bbox=BBOX, resolution=20,
                       crs="EPSG:32718", groupby="solar_day").isel(time=0)
    # desde la línea base 04.00 (2022) los niveles digitales traen un desfase de +1000
    refl = {b: (ds[b].astype("float32") - 1000) / 10000 for b in ["B04", "B08", "B12"]}
    valido = ~np.isin(ds.SCL.values, [0, 1, 3, 6, 8, 9, 10, 11])   # sin datos, nube, agua, nieve
    nbr = (refl["B08"] - refl["B12"]) / (refl["B08"] + refl["B12"])
    return ds, refl, nbr.values, valido

ds0, r0, nbr0, ok0 = cargar(ANTES)
ds1, r1, nbr1, ok1 = cargar(DESPUES)
ds2, r2, nbr2, ok2 = cargar(DESPUES_2)

dnbr = np.where(ok0 & ok1, nbr0 - nbr1, np.nan)
dnbr2 = np.where(ok0 & ok2, nbr0 - nbr2, np.nan)
print(f"píxeles válidos en ambas fechas: {np.isfinite(dnbr).mean():.1%} (8 oct) | "
      f"{np.isfinite(dnbr2).mean():.1%} (13 oct)")

# %% [markdown]
# **Severidad** con los umbrales USGS (Key y Benson): <0,10 no quemado; 0,10–0,27 baja;
# 0,27–0,44 moderada-baja; 0,44–0,66 moderada-alta; ≥0,66 alta. Un píxel de 20 m = 0,04 ha.
#
# Un dNBR alto también aparece por cosechas, derrumbes o ríos que cambian de cauce. Por eso damos
# además una versión **sembrada con focos**: solo cuentan las manchas de dNBR ≥ 0,27 que tienen
# al menos un foco VIIRS de octubre dentro o a menos de 500 m.

# %%
HA = 20 * 20 / 1e4
CORTES = [0.10, 0.27, 0.44, 0.66]
NOMBRES = ["baja", "moderada-baja", "moderada-alta", "alta"]

def por_severidad(d):
    d = d[np.isfinite(d)]                      # sin esto, las nubes caerían en «alta»
    clases = np.digitize(d, CORTES)            # 0 = no quemado ... 4 = alta
    return pd.Series({n: (clases == i + 1).sum() * HA for i, n in enumerate(NOMBRES)})

# rejilla de focos en el mismo sistema que el raster
x, y = ds1.x.values, ds1.y.values
transform = ds1.odc.geobox.affine
pts = f_zona[(f_zona.fecha >= "2026-10-01")].to_crs(32718)

def sembrado(d, hasta):
    p = pts[pts.fecha <= hasta]
    semilla = features.rasterize(((g.buffer(500), 1) for g in p.geometry),
                                 out_shape=d.shape, transform=transform).astype(bool)
    etiquetas, _ = ndimage.label(np.nan_to_num(d) >= 0.27)
    vivas = np.unique(etiquetas[semilla & (etiquetas > 0)])
    return np.isin(etiquetas, vivas) & (etiquetas > 0)

quem1 = sembrado(dnbr, DESPUES)
quem2 = sembrado(dnbr2, DESPUES_2)

resumen = pd.DataFrame({
    f"{DESPUES} · toda la zona": por_severidad(dnbr),
    f"{DESPUES} · sembrado con focos": por_severidad(np.where(quem1, dnbr, np.nan)),
    f"{DESPUES_2} · sembrado con focos": por_severidad(np.where(quem2, dnbr2, np.nan)),
}).T
resumen["≥0,27 (ha)"] = resumen[NOMBRES[1:]].sum(axis=1)
resumen["≥0,10 (ha)"] = resumen[NOMBRES].sum(axis=1)
resumen["nubes post %"] = [nubes.set_index("fecha").loc[f, "nubes_zona_%"]
                           for f in [DESPUES, DESPUES, DESPUES_2]]
resumen.round(0)

# %%
# ¿cuánto cae dentro del distrito de Río Tambo y en los vecinos?
cod = features.rasterize(((g, i + 1) for i, g in enumerate(distritos.to_crs(32718).geometry)),
                         out_shape=dnbr.shape, transform=transform)
ids, n = np.unique(cod[quem2], return_counts=True)     # al 13 oct
por_distrito = pd.DataFrame({
    "distrito": distritos.NOMBDIST.values[ids - 1],
    "provincia": distritos.NOMBPROV.values[ids - 1],
    "ha_quemadas": n * HA,
}).sort_values("ha_quemadas", ascending=False)
por_distrito

# %%
def falso_color(r):
    rgb = np.dstack([r["B12"].values, r["B08"].values, r["B04"].values])
    return np.clip(rgb / np.array([0.35, 0.45, 0.15]), 0, 1)

ext = [x.min(), x.max(), y.min(), y.max()]
# zoom: caja de los píxeles quemados (13 oct) más 2 km de margen
filas, cols = np.where(quem2)
zx = [x[cols].min() - 2000, x[cols].max() + 2000]
zy = [y[filas].min() - 2000, y[filas].max() + 2000]

from matplotlib.colors import ListedColormap, BoundaryNorm
cmap = ListedColormap(["#f2f0e6", "#fde725", "#f89540", "#cc4778", "#5c0e74"])
norm = BoundaryNorm([-1] + CORTES + [2], cmap.N)

fig, ejes = plt.subplots(1, 3, figsize=(13, 4.8))
ejes[0].imshow(falso_color(r0), extent=ext)
ejes[0].set_title(f"Antes · {ANTES}\nfalso color B12-B8-B4", fontsize=9)
ejes[1].imshow(falso_color(r2), extent=ext)
ejes[1].set_title(f"Después · {DESPUES_2}\nlo quemado se ve morado-rojizo", fontsize=9)
ejes[2].imshow(dnbr2, cmap=cmap, norm=norm, extent=ext, alpha=0.3)
im = ejes[2].imshow(np.where(quem2, dnbr2, np.nan), cmap=cmap, norm=norm, extent=ext)
pts[pts.fecha <= DESPUES_2].plot(ax=ejes[2], markersize=4, color="black", label="foco VIIRS")
ejes[2].set_title(f"dNBR {ANTES[5:]} → {DESPUES_2[5:]} (zoom)\n"
                  f"≥ {resumen.iloc[2]['≥0,27 (ha)']:,.0f} ha sembradas con focos; tenue = sin foco", fontsize=9)
ejes[2].legend(fontsize=7, loc="lower left")
fig.colorbar(im, ax=ejes[2], shrink=0.7, ticks=[-0.4, 0.18, 0.35, 0.55, 1.3]).ax.set_yticklabels(
    ["no quemado", "baja", "mod.-baja", "mod.-alta", "alta"], fontsize=7)
for a in ejes[:2]:
    a.add_patch(plt.Rectangle((zx[0], zy[0]), zx[1] - zx[0], zy[1] - zy[0], fill=False, ec="white", lw=1))
ejes[2].set_xlim(zx); ejes[2].set_ylim(zy)
for a in ejes:
    a.set_xticks([]); a.set_yticks([])
fig.suptitle("Incendio de Río Tambo (Satipo, Junín), octubre 2026 · Sentinel-2 L2A, 20 m", y=1.0)
plt.tight_layout()
plt.savefig(f"{FIG}/rio_tambo_dnbr.png", bbox_inches="tight")
plt.show()

# %% [markdown]
# ## 5 · Hallazgos (se llenan solos con los números de arriba)

# %%
rec = dep[dep.record].index.str.title().tolist()
rec_c = dep[dep.record_corregido].index.str.title().tolist()
hallazgos = [
    f"1. Del 1 de enero al 20 de octubre de 2026 hubo {por_anio[2026]:,} focos VIIRS S-NPP en el Perú: "
    f"{100 * (por_anio[2026] / historia.mean() - 1):+.0f} % frente al promedio 2012–2025 (puesto {rk[2026]} de {len(rk)}). "
    f"En el acumulado del año, 2026 NO es récord (máximo: {historia.max():,} en {historia.idxmax()}).",
    f"2. Octubre sí es excepcional: {oct_anio[2026]:,} focos del 1 al 20, "
    f"{100 * (oct_anio[2026] / oct_anio.loc[2012:2025].mean() - 1):+.0f} % sobre el promedio. Supera a 2020 "
    f"({oct_anio.loc[2012:2025].max():,}) en bruto, pero al corregir el {total_dif:+.1f} % de INPE frente a FIRMS "
    f"queda en {oct_corr:,.0f}: empate técnico con 2020, no un récord claro.",
    f"3. Récord departamental en el acumulado: {', '.join(rec) or 'ninguno'} "
    f"(tras la corrección: {', '.join(rec_c) or 'ninguno'}). Apurímac duplica su promedio ({dep.loc['APURIMAC', 'cambio_%']:+.0f} %).",
    f"4. Río Tambo: entre el {ANTES} y el {DESPUES} se quemaron {resumen.iloc[1]['≥0,27 (ha)']:,.0f} ha (dNBR ≥ 0,27, "
    f"sembrado con focos, 2 % de nubes); al {DESPUES_2} van al menos {resumen.iloc[2]['≥0,27 (ha)']:,.0f} ha "
    f"(con 30 % de la zona bajo nubes, es un piso).",
]
print("\n".join(hallazgos))
