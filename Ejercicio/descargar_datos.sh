#!/usr/bin/env bash
# Descarga todos los datos (públicos, sin clave). Correr desde la carpeta del proyecto.
set -e
mkdir -p datos/firms datos/inpe

# NASA FIRMS: archivo anual VIIRS S-NPP del Perú, 2012-2025
for y in $(seq 2012 2025); do
  curl -sf -o datos/firms/viirs-snpp_${y}_Peru.csv \
    "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/$y/viirs-snpp_${y}_Peru.csv"
done
# NASA FIRMS: últimos 7 días, Sudamérica (para calibrar INPE)
curl -sf -o datos/firms/SUOMI_VIIRS_C2_South_America_7d.csv \
  https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_7d.csv

# INPE Queimadas: focos mensuales de Sudamérica, 2026
for m in 01 02 03 04 05 06 07 08 09 10; do
  curl -sf -o datos/inpe/focos_mensal_2026$m.csv \
    "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/America_Sul/focos_mensal_2026$m.csv"
done
# nos quedamos con Perú y el satélite S-NPP (NPP-375 y NPP-375D), comparable con FIRMS
.venv/bin/python - <<'PY'
import glob, pandas as pd
d = pd.concat(pd.read_csv(f, usecols=["lat", "lon", "data_hora_gmt", "satelite", "pais", "estado"])
              for f in sorted(glob.glob("datos/inpe/focos_mensal_2026*.csv")))
d[(d.pais == "Peru") & d.satelite.str.startswith("NPP")].to_csv("datos/inpe_peru_npp_2026.csv", index=False)
PY

# Límites INEI (juaneladio/peru-geojson)
base=https://raw.githubusercontent.com/juaneladio/peru-geojson/master
curl -sfL -o datos/departamentos.geojson $base/peru_departamental_simple.geojson
curl -sfL -o datos/distritos.geojson $base/peru_distrital_simple.geojson
