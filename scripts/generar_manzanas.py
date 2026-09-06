"""
Arma la base de manzanas de los 3 distritos objetivo y le asigna el nivel de
ingreso y la cobertura de empadronamiento.

Fuentes por distrito
--------------------
  ATE y SAN JUAN DE LURIGANCHO
      Manzanas REALES del INEI, con NIVEL DE INGRESO REAL, desde
      "ingresos_ate_sjl_consolidado.shp" (22,318 manzanas, estratificacion
      oficial del INEI). Nada sintetico en el ingreso.

  EL PORVENIR
      Todavia no hay estratificacion del INEI. Las manzanas se construyen con
      el grafo vial de Overture Maps (polygonize) recortado contra la zona
      censal, y el nivel de ingreso queda como "Sin dato".

Unidades
--------
  ZONA CENSAL  unidad oficial del INEI 2017 ("Targeting Criteria/zona_perfiles.gpkg").
               Es la subarea del operativo: la COBERTURA se define a este nivel,
               por eso varias manzanas vecinas comparten color.
               El shapefile de ingresos enlaza con ella por UBIGEO + CODZONA
               (verificado: 248 zonas, 100% de coincidencia, sin huerfanos).

  MANZANA      unidad de dibujo. El NIVEL DE INGRESO se define a este nivel.

COBERTURA
---------
Dato oficial, desde "01_Raw/Zonas Piloto.xlsx" (hoja ZonaCensal, 409 subzonas
censales agregadas a 261 zonas):

    cobertura = hogares en el Registro Integrado / hogares del Censo INEI 2017

Puede pasar del 100%, porque el RI es actual y el censo es de 2017. El cruce
cubre el 100% de las manzanas de Ate y SJL; en El Porvenir el Excel trae 13 de
las 18 zonas y las otras 5 quedan como "Sin dato".

Lo unico sintetico que queda es el nivel de ingreso de El Porvenir.

Corre UNA sola vez, offline. Requiere:
  - ingresos_ate_sjl_consolidado.shp (+ .dbf .shx .prj)
  - Targeting Criteria/zona_perfiles.gpkg
  - 01_Raw/Zonas Piloto.xlsx                             (cobertura oficial)
  - data/raw_buildings/{ate,sjl,porvenir}.parquet        (construcciones Overture)
  - data/raw_buildings/porvenir_roads.parquet            (calles, solo El Porvenir)

Salida:
  data/manzanas.parquet
  data/zonas.parquet
  data/distritos.parquet
"""
import sqlite3
import time
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import polars as pl
import pyarrow.parquet as pq
import pyogrio
import shapely
import shapely.wkb as wkb
from shapely.ops import polygonize, unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_buildings"
GPKG = ROOT / "Targeting Criteria" / "zona_perfiles.gpkg"
SHP_INGRESOS = ROOT / "ingresos_ate_sjl_consolidado.shp"
XLS_COBERTURA = ROOT / "01_Raw" / "Zonas Piloto.xlsx"

MIN_AREA_M2 = 300        # solo El Porvenir: descarta slivers entre calles
MAX_AREA_M2 = 200_000    # solo El Porvenir: descarta poligonos no urbanos
UMBRAL_BAJA_COBERTURA = 100.0

# ~2.2 m. Al zoom de distrito un pixel son ~38 m, asi que es imperceptible.
# Reduce los vertices del shapefile del INEI al 24% sin cambio visible.
TOLERANCIA_SIMPLIFY = 0.00002

SIN_DATO = "Sin dato"
# Orden oficial del INEI: ESTRATO 1..5 de menor a mayor ingreso.
NIVELES = ["Bajo", "Medio bajo", "Medio", "Medio alto", "Alto"]

DISTRITOS = {
    # ubigeo: (nombre, provincia, departamento, slug_overture, fuente_ingreso)
    "150103": ("ATE", "LIMA", "LIMA", "ate", "inei"),
    "150132": ("SAN JUAN DE LURIGANCHO", "LIMA", "LIMA", "sjl", "inei"),
    "130102": ("EL PORVENIR", "TRUJILLO", "LA LIBERTAD", "porvenir", "pendiente"),
}


def gpkg_wkb(blob):
    """Quita la cabecera GeoPackage de un blob para quedarse con el WKB puro."""
    env = (blob[3] >> 1) & 0x07
    return blob[8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[env]:]


def area_m2(poly, lat):
    return poly.area * 111_320 * (111_320 * np.cos(np.radians(lat)))


def a_poligono(g):
    """Devuelve el anillo exterior como lista [lon, lat], o None si no sirve."""
    if g is None or g.is_empty:
        return None
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda p: p.area)
    if g.geom_type != "Polygon" or len(g.exterior.coords) < 4:
        return None
    return [[round(p[0], 5), round(p[1], 5)] for p in g.exterior.coords]


def leer_cobertura():
    """
    Cobertura de empadronamiento por zona censal, desde "01_Raw/Zonas Piloto.xlsx".

    El Excel llega a nivel SUBZONA (IDZONA = UBIGEO[6] + ZONA[3] + SUBZONA[2]) y
    aqui se agrega a nivel ZONA, que es la unidad que dibuja el tablero. Agregar
    es exacto porque hogares y poblacion son conteos, no tasas.

    Se agrega a ZONA y no a SUBZONA porque el esquema de subzonas del Excel NO es
    el de la cartografia censal. Verificado contra la base DNCE 2017 del INEI
    (485,696 manzanas): el shapefile de ingresos reproduce fielmente el SUFZONA
    oficial; el que subdivide distinto es el Excel. P.ej. la zona 035 de Ate
    tiene una sola subzona (00) en la cartografia y tres (01/02/03) en el Excel,
    y la zona 001 de SJL tiene 01/02 en la cartografia y 03..09 en el Excel, o
    sea numeros directamente distintos. Coinciden 227 de 266 zonas.

    A nivel zona el cruce es completo: 90/90 zonas en Ate y 158/158 en SJL, es
    decir el 100% de las manzanas de ambos distritos. Es ademas el mismo nivel
    que uso el gpkg de zonas en su columna ris_cobertura_h, que reproduce esta
    misma cobertura con 0.05 puntos de diferencia (solo redondeo).

    Cobertura = hogares en el Registro Integrado / hogares del Censo INEI 2017.
    Puede superar el 100%: el RI es actual y el censo es de 2017, y estos
    distritos han crecido desde entonces.
    """
    wb = openpyxl.load_workbook(XLS_COBERTURA, data_only=True, read_only=True)
    filas = list(wb["ZonaCensal"].iter_rows(values_only=True))
    col = {n: i for i, n in enumerate(filas[0])}
    acum, sin_denominador = {}, 0

    for f in filas[1:]:
        if f[col["IDZONA"]] is None:
            continue
        # Una subzona de SJL (15013213605) llega sin denominador INEI. Se descarta
        # entera para que numerador y denominador del ratio sigan siendo el mismo
        # conjunto de subzonas; son 64 hogares sobre 248,742 en el distrito.
        if f[col["inei_h_total"]] is None:
            sin_denominador += 1
            continue
        idz = str(f[col["IDZONA"]])
        a = acum.setdefault((idz[:6], idz[6:9]),
                            {"ri": 0, "inei": 0, "pobres": 0, "poblacion": 0, "subzonas": 0})
        a["ri"] += f[col["h_total"]]
        a["inei"] += f[col["inei_h_total"]]
        a["pobres"] += f[col["h_pobre"]] + f[col["h_pobre_ext"]]
        a["poblacion"] += f[col["inei_p_total"]]
        a["subzonas"] += 1

    print(f"Cobertura: {len(filas)-1} subzonas -> {len(acum)} zonas censales"
          + (f" ({sin_denominador} subzona sin denominador INEI, descartada)"
             if sin_denominador else ""))
    return acum


def campos_cobertura(c):
    """Columnas de cobertura de una zona. `c` es None cuando el Excel no la trae."""
    if c is None:
        return {"cobertura_pct": None, "hogares_inei": None, "hogares_ri": None,
                "brecha_hogares": None, "hogares_pobres": None, "baja_cobertura": False}
    pct = round(100 * c["ri"] / c["inei"], 1)
    return {"cobertura_pct": pct,
            "hogares_inei": int(c["inei"]),
            "hogares_ri": int(c["ri"]),
            # Positiva = hogares del censo que el RI todavia no registra.
            "brecha_hogares": int(c["inei"] - c["ri"]),
            "hogares_pobres": int(c["pobres"]),
            "baja_cobertura": bool(pct < UMBRAL_BAJA_COBERTURA)}


def leer_zonas(con, ubigeo):
    """Zonas censales INEI 2017 de un distrito."""
    cur = con.execute(
        "SELECT CODZONA, geom, perfil, inei_poblacion, media_pobreza, area_km2 "
        "FROM zona_perfiles WHERE CODDPTO||CODPROV||CODDIST = ? ORDER BY CODZONA",
        (ubigeo,))
    zonas = []
    for codzona, blob, perfil, pobl, pobreza, akm2 in cur.fetchall():
        g = wkb.loads(gpkg_wkb(blob)).buffer(0)
        if not g.is_empty:
            zonas.append({"codzona": codzona, "geom": g, "perfil": perfil,
                          "inei_poblacion": pobl, "media_pobreza": pobreza,
                          "area_km2": akm2})
    return zonas


def manzanas_inei(ubigeo):
    """Manzanas reales del INEI con su nivel de ingreso, para Ate y SJL."""
    meta, _, geom, campos = pyogrio.raw.read(SHP_INGRESOS)
    df = pd.DataFrame({n: d for n, d in zip(meta["fields"], campos)})
    df["geom"] = shapely.simplify(shapely.from_wkb(geom), TOLERANCIA_SIMPLIFY,
                                  preserve_topology=True)
    df = df[df["UBIGEO"] == ubigeo].reset_index(drop=True)
    # nombres truncados a 10 caracteres por el formato shapefile
    return df.rename(columns={"IDMANZA": "id_manzana", "nvl_ngr": "nivel_ingreso",
                              "dstrt_f": "distrito_fuente"})


def manzanas_overture(slug, zona_geoms, lat_ref):
    """
    Manzanas construidas con el grafo vial (solo El Porvenir, que aun no tiene
    estratificacion del INEI). Cada cara cerrada por calles es una manzana; se
    recorta contra la zona censal que contiene su centroide.
    """
    lineas = [wkb.loads(g) for g in
              pq.read_table(RAW / f"{slug}_roads.parquet").to_pandas()["geometry"]]
    caras = list(polygonize(unary_union(lineas)))
    tree_z = STRtree(zona_geoms)
    prep_z = [prep(g) for g in zona_geoms]

    mzs = []
    for cara in caras:
        a = area_m2(cara, lat_ref)
        if a < MIN_AREA_M2 or a > MAX_AREA_M2:
            continue
        c = cara.centroid
        zi = next((int(k) for k in tree_z.query(c) if prep_z[k].contains(c)), None)
        if zi is None:
            continue
        rec = cara.intersection(zona_geoms[zi])
        rec = shapely.simplify(rec, TOLERANCIA_SIMPLIFY, preserve_topology=True)
        if a_poligono(rec) is not None:
            mzs.append((rec, zi))

    # Si una zona no genero manzanas (sin calles mapeadas, tipico de asentamientos
    # informales), se dibuja completa para que su poblacion no desaparezca del mapa.
    con_mz = {zi for _, zi in mzs}
    rescatadas = 0
    for zi, zg in enumerate(zona_geoms):
        if zi in con_mz:
            continue
        g = shapely.simplify(zg, TOLERANCIA_SIMPLIFY, preserve_topology=True)
        if a_poligono(g) is not None:
            mzs.append((g, zi))
            rescatadas += 1
    return mzs, len(caras), rescatadas


def main():
    t_start = time.time()
    con = sqlite3.connect(GPKG)
    cobertura = leer_cobertura()
    manzana_rows, zona_rows, distrito_rows = [], [], []
    manzana_id = 0

    for ubigeo, (nombre, prov, dep, slug, fuente) in DISTRITOS.items():
        t0 = time.time()
        print(f"\n=== {nombre} ===")

        zonas = leer_zonas(con, ubigeo)
        zona_geoms = [z["geom"] for z in zonas]
        idx_por_codzona = {z["codzona"]: i for i, z in enumerate(zonas)}
        bounds = unary_union(zona_geoms).bounds
        lat_ref = (bounds[1] + bounds[3]) / 2
        print(f"  {len(zonas)} zonas censales INEI 2017 ({time.time()-t0:.1f}s)")

        # --- manzanas + nivel de ingreso
        t1 = time.time()
        if fuente == "inei":
            df = manzanas_inei(ubigeo)
            geoms = list(df["geom"])
            niveles = list(df["nivel_ingreso"])
            ids = list(df["id_manzana"])
            zidx = [idx_por_codzona[c] for c in df["CODZONA"]]
            print(f"  {len(geoms):,} manzanas REALES del INEI con ingreso real "
                  f"({time.time()-t1:.1f}s)")
        else:
            mzs, n_caras, rescatadas = manzanas_overture(slug, zona_geoms, lat_ref)
            geoms = [m[0] for m in mzs]
            zidx = [m[1] for m in mzs]
            niveles = [SIN_DATO] * len(geoms)
            ids = [None] * len(geoms)
            print(f"  {n_caras:,} caras viales -> {len(geoms):,} manzanas Overture "
                  f"({time.time()-t1:.1f}s)")
            if rescatadas:
                print(f"  + {rescatadas} zona(s) sin calles mapeadas dibujadas completas")
            print(f"  nivel de ingreso: '{SIN_DATO}' (falta estratificacion del INEI)")

        # --- construcciones reales por manzana (Overture, todas)
        t2 = time.time()
        edif = [wkb.loads(g) for g in
                pq.read_table(RAW / f"{slug}.parquet").to_pandas()["geometry"]]
        centroides = shapely.centroid(np.array(edif, dtype=object))
        _, idx_m = STRtree(geoms).query(centroides, predicate="within")
        n_constr = np.bincount(idx_m, minlength=len(geoms))
        print(f"  {len(edif):,} construcciones -> {n_constr.sum():,} asignadas "
              f"({time.time()-t2:.1f}s)")

        # --- COBERTURA REAL, POR ZONA CENSAL (Zonas Piloto.xlsx)
        cob_zona = [campos_cobertura(cobertura.get((ubigeo, z["codzona"]))) for z in zonas]
        n_sin = sum(1 for c in cob_zona if c["cobertura_pct"] is None)
        print(f"  cobertura oficial en {len(zonas)-n_sin}/{len(zonas)} zonas"
              + (f", {n_sin} sin dato en el Excel" if n_sin else ""))

        for zi, z in enumerate(zonas):
            zona_rows.append({
                "zona_key": f"{ubigeo}-{z['codzona']}", "distrito": nombre,
                "codzona": z["codzona"], "zona_nombre": f"Zona {z['codzona']}",
                **cob_zona[zi],
                "perfil_inei": z["perfil"], "inei_poblacion": z["inei_poblacion"],
                "media_pobreza": z["media_pobreza"], "area_km2": z["area_km2"],
            })

        descartadas = 0
        for g, zi, niv, idm, nc in zip(geoms, zidx, niveles, ids, n_constr):
            poli = a_poligono(g)
            if poli is None:
                descartadas += 1
                continue
            z = zonas[zi]
            manzana_rows.append({
                "manzana_id": manzana_id, "id_manzana_inei": idm,
                "distrito": nombre, "provincia": prov, "departamento": dep,
                "zona_key": f"{ubigeo}-{z['codzona']}", "codzona": z["codzona"],
                "zona_nombre": f"Zona {z['codzona']}",
                "poligono": poli,
                "nivel_ingreso": niv,
                "n_hogares": int(nc),
                **cob_zona[zi],
            })
            manzana_id += 1
        if descartadas:
            print(f"  {descartadas} manzanas descartadas por geometria invalida")

        distrito_rows.append({"distrito": nombre, "provincia": prov, "departamento": dep,
                              "fuente_ingreso": fuente})
        print(f"  distrito completo en {time.time()-t0:.1f}s")

    df_mz = pl.DataFrame(manzana_rows)
    df_z = pl.DataFrame(zona_rows)

    lim = (df_mz.explode("poligono")
           .with_columns(lon=pl.col("poligono").list.get(0),
                         lat=pl.col("poligono").list.get(1))
           .group_by("distrito")
           .agg(min_lon=pl.col("lon").min(), max_lon=pl.col("lon").max(),
                min_lat=pl.col("lat").min(), max_lat=pl.col("lat").max()))
    df_dist = lim.join(pl.DataFrame(distrito_rows), on="distrito")

    df_mz.write_parquet(ROOT / "data" / "manzanas.parquet", compression="zstd")
    df_z.write_parquet(ROOT / "data" / "zonas.parquet", compression="zstd")
    df_dist.write_parquet(ROOT / "data" / "distritos.parquet", compression="zstd")

    print(f"\nTOTAL: {len(df_mz):,} manzanas en {len(df_z)} zonas censales, "
          f"{time.time()-t_start:.1f}s")
    print("\nManzanas por distrito y nivel de ingreso:")
    print(df_mz.group_by(["distrito", "nivel_ingreso"]).len().sort(["distrito", "len"],
                                                                  descending=[False, True]))


if __name__ == "__main__":
    main()
