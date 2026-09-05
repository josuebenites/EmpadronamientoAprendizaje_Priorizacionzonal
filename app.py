"""
Tablero "Piloto de Aprendizaje: priorizacion de zonas" (SISFOH / OFIS).
Streamlit + pydeck/deck.gl + Polars. Identidad visual de IPA.

DOS PAGINAS
-----------
  1. Instructivo   que es el tablero, que significa cada dato y hasta donde
                   llega. Es la pagina de entrada a proposito: el mapa se
                   interpreta mal si no se sabe que es la cobertura ni de que
                   ano es el censo.
  2. Mapa dinamico un solo mapa con todas las zonas del distrito.

FUENTE UNICA DE VERDAD
----------------------
`data/zonas_ofis_dashboard.parquet`, la salida del pipeline de priorizacion en
R (3_zonas_subzonas). Una fila por ZONA, indexada por IDZONA, con su geometria
en WKT, su perfil, su cobertura y su brecha en los dos escenarios, las dos
exclusiones y la asignacion de bloque del piloto.

Es la MISMA unidad y el MISMO perfil que el .R usa para plotear, asi que el
tablero y los mapas de R muestran lo mismo. No se agrega, no se promedia y no
se recalcula nada.

`data/manzanas.parquet` se usa SOLO como capa de bordes. Se filtran las
manzanas de las zonas que ya no existen: El Porvenir se dividio y la
cartografia anterior incluia territorio que paso a otro distrito.

`zonas.parquet` y `distritos.parquet` ya no se leen. Venian de esa cartografia
anterior y su perfil era de otra anada del clustering.

MODO CLARO
----------
El tema vive en `.streamlit/config.toml` con base = "light". Sin ese archivo,
un equipo configurado en modo oscuro renderiza el tablero con fondo negro y la
paleta de IPA pierde contraste. Los colores del CSS de abajo son explicitos por
la misma razon: no dependen de que el tema cargue.

Ver DOCUMENTACION.md para fuentes, limites y decisiones tecnicas.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pydeck as pdk
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# ===========================================================================
# PALETA IPA
# ===========================================================================
# Colores oficiales de Innovations for Poverty Action. No se aproximan ni se
# sustituyen.
IPA_VERDE        = "#49ac57"   # primario de marca
IPA_VERDE_OSCURO = "#155240"   # emfasis secundario, fondos oscuros
IPA_AZUL_CLARO   = "#84d0d4"
IPA_AZUL_OSCURO  = "#2b4085"
IPA_NARANJA      = "#f26529"   # color de alerta de la marca
IPA_GRIS_CLARO   = "#f1f2f2"   # fondos de panel
IPA_GRIS         = "#c9c9c8"   # bordes, elementos apagados
IPA_CARBON       = "#414042"   # texto
IPA_LAVANDA      = "#be9ffa"   # categorica 4
IPA_ORO          = "#f5cb57"   # categorica 5
IPA_VINO         = "#730000"   # divergente 6, para el cruce de exclusiones

# La identidad del tablero usa la combinacion recomendada para diseños con
# mucho dato: IPA Green, grises y carbon sobre blanco.

# --- Paletas de datos -------------------------------------------------------
# COBERTURA. Ocho clases, con cortes mas finos entre 70 y 100 porque ahi se
# decide el operativo.
#
# DE 0 A 100% VA EN VERDE, de muy claro a Dark Green. Arranca en un tinte claro
# de IPA Green para que las ocho clases se distingan: partir del verde pleno
# dejaba los primeros tres tramos casi identicos entre si. Los dos anclajes de
# la marca, IPA Green y Dark Green, se conservan dentro de la rampa.
#
# DE 100% EN ADELANTE VA EN AZUL, tambien de claro a oscuro. Por encima de 100%
# el registro ya tiene mas hogares que los que conto el censo, asi que no es
# "mas cobertura": es otra cosa. Seguir oscureciendo el verde sugeriria que
# 130% es mejor que 95%, cuando en realidad indica que el censo se quedo corto
# o que la cartografia no calza. El corte de color en 100% marca ese cambio de
# naturaleza, y dentro del azul se sigue oscureciendo porque el exceso si tiene
# orden: 130% desvia mas que 110%.
ESCALA_COBERTURA = [
    "#e9f5eb",   # 0 a 20%      tinte claro de IPA Green
    "#bfe2c4",   # 20 a 50%
    "#92cd9a",   # 50 a 70%
    "#49ac57",   # 70 a 80%     IPA Green
    "#307d4c",   # 80 a 90%
    "#155240",   # 90 a 100%    Dark Green
    "#84d0d4",   # 100 a 120%   Light Blue
    "#2b4085",   # 120% o mas   Dark Blue
]
CORTES_COBERTURA = [20, 50, 70, 80, 90, 100, 120]
ETIQUETAS_COBERTURA = ["0 a 20%", "20 a 50%", "50 a 70%", "70 a 80%",
                       "80 a 90%", "90 a 100%", "100 a 120%", "120% o más"]

# Perfil: paleta CATEGORICA de IPA, disenada para daltonismo.
#
# El reparto de colores sigue una regla: las EXCLUSIONES se pintan encima del
# relleno, asi que su color no puede coincidir con ninguno de los colores que
# el relleno pueda estar usando en ese momento. Cobertura y perfil, en cambio,
# nunca se muestran a la vez, asi que si pueden compartir color entre si.
#
#   relleno cobertura -> verdes y azules
#   relleno perfil    -> celeste, azul oscuro, oro
#   exclusiones       -> naranja, lavanda, vino  (ninguno aparece en un relleno)
PALETA_PERFIL = [IPA_AZUL_CLARO, IPA_AZUL_OSCURO, IPA_ORO, IPA_VERDE]

COLOR_RIESGO       = IPA_NARANJA        # alerta de criminalidad
COLOR_INGRESO_ALTO = IPA_LAVANDA        # presencia de ingreso alto
COLOR_AMBOS        = IPA_VINO           # cae en las dos exclusiones
COLOR_SIN_DATO     = IPA_GRIS

BORDE_ZONA    = [201, 201, 200, 190]    # IPA_GRIS
BORDE_MANZANA = [201, 201, 200, 110]
BORDE_PILOTO  = [21, 82, 64, 255]       # IPA_VERDE_OSCURO
COLOR_PUNTO   = [65, 64, 66, 235]       # IPA_CARBON

ALTO_BARRA   = 120
ALTO_MAPA_PX = 620

# Cuanto del mapa ocupa el distrito al reencuadrar (1.0 = pegado a los bordes).
MARGEN_VISTA = 0.62
MARGEN_POR_DISTRITO = {"El Porvenir": 0.50}

# Rango plausible de coordenadas para Peru. Sirve para detectar el error mas
# comun al pegar: lon/lat en vez de lat/lon.
LAT_PERU = (-18.5, 0.0)
LON_PERU = (-81.5, -68.5)

st.set_page_config(page_title="Piloto de Aprendizaje: priorización de zonas",
                   page_icon="🗺️", layout="wide",
                   initial_sidebar_state="collapsed")

# Tipografia de IPA para documentos: Georgia en titulares, Arial en cuerpo.
st.markdown(f"""
<style>
  /* color-scheme explicito: aunque .streamlit/config.toml fija el tema claro,
     esto evita que el navegador aplique su propio ajuste oscuro a los
     controles nativos (desplegables, campos de texto). */
  :root {{ color-scheme: light; }}
  html, body, [data-testid="stAppViewContainer"] {{
      background: #ffffff !important;
      color: {IPA_CARBON};
  }}

  /* Se oculta la cabecera propia de Streamlit para que la barra del tablero
     ocupe ese espacio. */
  [data-testid="stHeader"] {{ display: none !important; }}
  section[data-testid="stSidebar"] {{ display: none !important; }}

  .st-key-barra_principal {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 999991;
      background: #ffffff; border-bottom: 3px solid {IPA_VERDE};
      box-shadow: 0 2px 8px rgba(65,64,66,.10); padding: 0 18px 6px 18px;
  }}
  .titulo-barra {{
      background: {IPA_VERDE_OSCURO}; color: #ffffff;
      margin: 0 -18px 6px -18px; padding: 10px 20px;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 1.20rem; font-weight: 400; letter-spacing: .2px;
  }}
  .titulo-barra .marca {{
      display: block; font-family: Arial, Helvetica, sans-serif;
      font-size: .68rem; font-weight: 700; letter-spacing: .14em;
      text-transform: uppercase; color: {IPA_AZUL_CLARO}; margin-bottom: 3px;
  }}
  .titulo-barra .sub {{
      font-family: Arial, Helvetica, sans-serif;
      font-weight: 400; opacity: .78; font-size: .84rem;
  }}

  .grupo {{
      display: block; font-family: Arial, Helvetica, sans-serif;
      font-size: .68rem; font-weight: 700; letter-spacing: .10em;
      text-transform: uppercase; color: {IPA_VERDE_OSCURO};
      line-height: 1.25; min-height: 17px; padding: 0 0 4px 2px;
      border-bottom: 1px solid {IPA_GRIS}; margin: 0 0 9px 0;
  }}
  /* El contenedor del rotulo no debe encogerse ni solaparse con el control que
     va debajo: sin esto el desplegable de Distrito tapaba la palabra. */
  .st-key-barra_principal [data-testid="stMarkdownContainer"] {{ overflow: visible; }}
  .st-key-barra_principal [data-testid="stVerticalBlock"] {{ gap: .30rem; }}

  .block-container {{ padding-top: {ALTO_BARRA + 8}px !important; padding-bottom: 1.5rem; }}

  h1, h2, h3, h4 {{
      font-family: Georgia, 'Times New Roman', serif !important;
      color: {IPA_VERDE_OSCURO} !important; font-weight: 400 !important;
  }}
  /* El documento ocupa el ancho disponible. El tope de 1720px evita que en
     monitores muy anchos las tarjetas se estiren hasta perder proporcion.
     La medida de lectura comoda se controla en los parrafos sueltos, no en el
     contenedor: si se limita aca, las reticulas tampoco se expanden y queda
     medio lienzo vacio. */
  .doc {{
      font-family: Arial, Helvetica, sans-serif; color: {IPA_CARBON};
      font-size: .95rem; line-height: 1.62;
      max-width: 1720px; margin: 0 auto;
  }}
  /* Solo los parrafos de nivel superior llevan medida de lectura. Dentro de
     una tarjeta el ancho ya lo da la tarjeta. */
  .doc > p {{ max-width: 92ch; }}
  .doc h2 {{
      font-size: 1.35rem; margin: 26px 0 10px 0;
      border-bottom: 2px solid {IPA_VERDE}; padding-bottom: 5px;
  }}
  .doc h3 {{ font-size: 1.05rem; margin: 20px 0 6px 0; color: {IPA_VERDE_OSCURO}; }}
  .doc p {{ margin: 0 0 12px 0; }}
  /* Banda de apertura, a todo el ancho. Las cifras de resumen que antes iban
     al lado se quitaron: meta y potencial ya aparecen en "La meta del
     proyecto", y el numero de zonas y de distritos en "Que unidad usa".
     Repetirlas arriba solo alargaba la pagina antes del primer contenido. */
  .doc .entrada {{
      font-size: 1.08rem; color: {IPA_VERDE_OSCURO};
      border-left: 4px solid {IPA_VERDE}; background: {IPA_GRIS_CLARO};
      padding: 20px 26px; margin: 0 0 26px 0; line-height: 1.6;
  }}
  /* Bloque de dos columnas: fichas de texto a la izquierda y un grafico a la
     derecha, para que la cifra y la imagen se lean juntas. */
  .doc .escenarios {{
      display: grid; grid-template-columns: minmax(300px, 1fr) minmax(340px, 1.25fr);
      gap: 16px; margin: 0 0 8px 0; align-items: start;
  }}
  .doc .escenarios .fichas {{ display: grid; gap: 14px; }}
  .doc .cierre {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px; margin: 0 0 10px 0; align-items: start;
  }}
  .doc table {{ border-collapse: collapse; width: 100%; margin: 6px 0 16px 0;
                font-size: .90rem; }}
  .doc th {{ background: {IPA_VERDE_OSCURO}; color: #fff; text-align: left;
             padding: 7px 10px; font-size: .80rem; letter-spacing: .02em; }}
  .doc td {{ padding: 7px 10px; border-bottom: 1px solid {IPA_GRIS};
             vertical-align: top; }}
  .doc td.muestra {{ width: 26px; }}

  /* --- Retícula del instructivo -----------------------------------------
     Se usa CSS grid y no columnas de Streamlit porque el contenido es un
     documento, no controles: la retícula refluye sola en pantallas chicas y
     todo el bloque se mantiene con un solo estilo. */
  .doc .grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                 gap: 14px; margin: 0 0 18px 0; }}
  .doc .grid3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
                 gap: 14px; margin: 0 0 18px 0; }}
  .doc .grid4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
                 gap: 12px; margin: 0 0 22px 0; }}
  /* Los limites llevan parrafos largos, asi que necesitan columnas mas anchas
     que las tarjetas cortas: tres por fila en pantalla grande, no cinco. */
  .doc .grid-lim {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
                    gap: 14px; margin: 0 0 18px 0; }}

  .doc .tarjeta {{
      background: #ffffff; border: 1px solid {IPA_GRIS};
      border-top: 3px solid {IPA_VERDE}; border-radius: 3px;
      padding: 14px 16px 12px 16px;
  }}
  .doc .tarjeta h4 {{
      font-family: Georgia, serif; font-size: 1.02rem; margin: 0 0 7px 0;
      color: {IPA_VERDE_OSCURO}; font-weight: 400;
  }}
  .doc .tarjeta p {{ margin: 0 0 8px 0; font-size: .90rem; }}
  .doc .tarjeta p:last-child {{ margin-bottom: 0; }}
  .doc .tarjeta .icono {{ font-size: 1.15rem; margin-right: 6px; }}

  /* Paso numerado del procedimiento de selección. */
  .doc .paso {{ display: flex; gap: 11px; align-items: flex-start;
                background: #ffffff; border: 1px solid {IPA_GRIS};
                padding: 12px 14px; border-radius: 3px; }}
  .doc .paso .num {{
      flex: 0 0 26px; height: 26px; border-radius: 50%;
      background: {IPA_VERDE}; color: #fff; font-weight: 700;
      font-size: .85rem; display: flex; align-items: center;
      justify-content: center;
  }}
  .doc .paso p {{ margin: 0; font-size: .88rem; }}
  .doc .paso b {{ color: {IPA_VERDE_OSCURO}; }}

  /* Fila de leyenda: muestra el color y explica qué significa. Reproduce los
     colores reales del mapa para que se aprendan antes de abrirlo. */
  .doc .ley {{ display: flex; align-items: center; gap: 9px; margin: 0 0 6px 0;
               font-size: .86rem; }}
  .doc .ley .sw {{ flex: 0 0 22px; height: 14px;
                   border: 1px solid rgba(65,64,66,.25); }}
  .doc .rampa {{ display: flex; height: 15px; margin: 2px 0 5px 0; }}
  .doc .rampa div {{ flex: 1; }}
  .doc .rampa-et {{ display: flex; font-size: .70rem; color: #6b6b6d;
                    margin-bottom: 12px; }}
  .doc .rampa-et div {{ flex: 1; text-align: center; }}

  /* Barras del comparativo de escenarios. Sin leyenda: la etiqueta va sobre
     la barra, que es lo que pide la guía de visualización. */
  .doc .barras {{ margin: 4px 0 6px 0; }}
  .doc .barras .fila {{ display: grid; grid-template-columns: 190px 1fr;
                        gap: 10px; align-items: center; margin-bottom: 5px; }}
  .doc .barras .et {{ font-size: .84rem; text-align: right; color: {IPA_CARBON}; }}
  .doc .barras .b {{ height: 19px; display: flex; align-items: center;
                     padding-left: 7px; color: #fff; font-size: .78rem;
                     font-weight: 700; min-width: 26px; }}
  .doc .fuente {{ font-size: .78rem; color: #7C7A7F; margin-top: 6px; }}

  .doc .limite {{
      background: {IPA_GRIS_CLARO}; border-left: 4px solid {IPA_NARANJA};
      padding: 12px 15px; margin: 0;
  }}
  .doc .limite b {{ color: {IPA_CARBON}; }}
  .doc .limite p {{ margin: 6px 0 0 0; font-size: .88rem; }}

  table.resumen {{
      width: 100%; border-collapse: collapse; font-size: .86rem;
      font-family: Arial, Helvetica, sans-serif;
      margin: 0 0 10px 0; background: #ffffff;
  }}
  table.resumen th {{
      background: {IPA_VERDE_OSCURO}; color: #fff; font-weight: 700;
      padding: 7px 10px; text-align: right; font-size: .76rem;
      letter-spacing: .04em; text-transform: uppercase;
  }}
  table.resumen th:first-child {{ text-align: left; }}
  table.resumen td {{
      padding: 7px 10px; text-align: right; border-bottom: 1px solid {IPA_GRIS};
      font-variant-numeric: tabular-nums; color: {IPA_CARBON};
  }}
  table.resumen td:first-child {{ text-align: left; font-weight: 700; }}
  table.resumen tr.piloto td {{ background: {IPA_GRIS_CLARO}; }}
  /* Subfilas de la desagregacion por tipo de zona: sangradas y en gris, para
     que se lean como parte de la fila de arriba y no como otro ambito. */
  table.resumen tr.sub td {{
      background: {IPA_GRIS_CLARO}; color: #5c5b5e; font-size: .82rem;
      border-bottom: 1px solid #e4e5e5;
  }}
  table.resumen tr.sub td:first-child {{
      font-weight: 400; padding-left: 26px;
  }}
  table.resumen tr.total td {{ font-weight: 700;
                               border-top: 2px solid {IPA_VERDE_OSCURO}; }}
  table.resumen .nota {{ font-weight: 400; color: #6b6b6d; font-size: .78rem; }}

  .panel {{
      background: {IPA_GRIS_CLARO}; border: 1px solid {IPA_GRIS};
      border-radius: 4px; padding: 12px 14px; font-size: .80rem;
      line-height: 1.45; font-family: Arial, Helvetica, sans-serif;
      color: {IPA_CARBON};
  }}
  .panel h4 {{ margin: 0 0 8px 0; font-size: .95rem; }}
  .recordatorios .rec {{
      display: flex; gap: 8px; align-items: flex-start;
      padding: 7px 0; border-top: 1px solid {IPA_GRIS};
  }}
  .recordatorios .rec span {{ flex: 0 0 18px; font-size: 1.0rem;
                              line-height: 1.25; }}
  .recordatorios .rec-pie {{
      margin-top: 9px; padding-top: 7px; border-top: 1px solid {IPA_GRIS};
      color: {IPA_VERDE_OSCURO}; font-weight: 700;
  }}
  .disclaimer {{
      background: {IPA_GRIS_CLARO}; border-left: 4px solid {IPA_VERDE};
      padding: 8px 13px; font-size: .82rem; color: {IPA_CARBON};
      margin-bottom: 10px; font-family: Arial, Helvetica, sans-serif;
  }}
  /* Meta del distrito: va pegada a la tabla porque es lo que da escala a la
     brecha que se muestra encima. */
  .meta-linea {{
      font-family: Arial, Helvetica, sans-serif; font-size: .84rem;
      color: {IPA_CARBON}; background: #ffffff;
      border-left: 4px solid {IPA_VERDE_OSCURO}; padding: 7px 13px;
      margin: -6px 0 10px 0;
  }}
  .meta-linea .et {{
      text-transform: uppercase; letter-spacing: .06em; font-size: .70rem;
      font-weight: 700; color: {IPA_VERDE_OSCURO}; margin-right: 9px;
  }}
  .meta-linea .v {{ font-weight: 700; color: {IPA_VERDE_OSCURO};
                    font-variant-numeric: tabular-nums; }}
  .pie {{
      margin-top: 26px; padding-top: 12px; border-top: 1px solid {IPA_GRIS};
      font-family: Arial, Helvetica, sans-serif; font-size: .78rem;
      color: #6b6b6d;
  }}
</style>
""", unsafe_allow_html=True)


def _compactar_json_pydeck():
    """
    pydeck serializa con `indent=2` fijo (pydeck/bindings/json_tools.py), asi que
    el JSON que viaja al navegador va indentado: medido en San Juan de
    Lurigancho, 12.0 MB de los cuales 8.0 MB eran espacios y saltos de linea.
    Streamlit llama a `Deck.to_json()`, asi que basta reemplazar el serializador
    por uno compacto. Mismo contenido, un tercio del peso.
    """
    from pydeck.bindings import json_tools

    def serialize_compacto(serializable):
        return json.dumps(serializable, sort_keys=True,
                          default=json_tools.default_serialize,
                          separators=(",", ":"))

    json_tools.serialize = serialize_compacto
    json_tools.JSONMixin.to_json = lambda self: serialize_compacto(self)


_compactar_json_pydeck()

ARCHIVOS = ("zonas_ofis_dashboard.parquet", "manzanas.parquet")


def firma_datos():
    """
    Fecha de modificacion y tamano de cada parquet. Se pasa como argumento a las
    funciones cacheadas para que el cache se invalide solo cuando los datos
    cambian: st.cache_data no vigila el disco, asi que sin esto una corrida
    nueva del pipeline en R dejaba al servidor sirviendo la version anterior.
    """
    firmas = []
    for nombre in ARCHIVOS:
        f = DATA / nombre
        if not f.exists():
            st.error(f"Falta el archivo de datos **{nombre}**.\n\n"
                     f"Ruta esperada: `{f}`")
            st.stop()
        s = f.stat()
        firmas.append((nombre, s.st_mtime_ns, s.st_size))
    return tuple(firmas)


# ===========================================================================
# CARGA
# ===========================================================================

def anillos_de_geometria(g):
    """
    Geometria de shapely -> lista de poligonos, cada uno como lista de anillos
    [exterior, hueco1, ...] en el formato que espera PolygonLayer de deck.gl.
    Un MultiPolygon devuelve varias entradas: deck.gl no acepta multipoligonos
    en una sola fila, asi que cada parte va como fila propia con los mismos
    atributos.
    """
    partes = g.geoms if g.geom_type == "MultiPolygon" else [g]
    salida = []
    for p in partes:
        if p.is_empty:
            continue
        anillos = [[[round(x, 6), round(y, 6)] for x, y in p.exterior.coords]]
        anillos += [[[round(x, 6), round(y, 6)] for x, y in h.coords]
                    for h in p.interiors]
        salida.append(anillos)
    return salida


COLS_MINIMAS = ["IDZONA", "distrito", "nombre_distrito", "perfil",
                "geometry_wkt", "h_total",
                "cobertura_op_ofis", "brecha_meta_ofis", "inei_h_tot_op_ofis",
                "cobertura_op_pro", "brecha_meta_pro", "inei_h_tot_op_pro",
                "zona_ofis", "zona_ofis_pro",
                "alerta_criminalidad_extrema", "sin_ingreso_alto"]


@st.cache_data(show_spinner="Cargando zonas…")
def cargar(firma):
    """
    Devuelve las zonas con su geometria de shapely, las manzanas vigentes para
    la capa de bordes, el encuadre por distrito y un diagnostico de la carga.
    """
    from shapely import wkt

    z = pl.read_parquet(DATA / "zonas_ofis_dashboard.parquet").to_pandas()

    falt = [c for c in COLS_MINIMAS if c not in z.columns]
    if falt:
        st.error("El parquet del pipeline no trae columnas necesarias: "
                 + ", ".join(f"`{c}`" for c in falt)
                 + ". Vuelve a correr `3_zonas_subzonas` y regenéralo.")
        st.stop()

    z["IDZONA"] = z["IDZONA"].astype(str)
    z["geom"] = z["geometry_wkt"].apply(
        lambda w: wkt.loads(w) if isinstance(w, str) and w else None)

    # Etiqueta legible. IDZONA (11) = ubigeo(6) + zona(3) + subzona(2).
    z["etiqueta"] = np.where(
        z["IDZONA"].str.len() == 11,
        "Zona " + z["IDZONA"].str[6:9] + "-" + z["IDZONA"].str[9:],
        z["IDZONA"])

    # Exclusiones, en positivo. `sin_ingreso_alto` viene en TRUE tambien cuando
    # el estrato es desconocido, porque el pipeline conserva esos casos a
    # proposito. Negarla marca solo las zonas con presencia comprobada.
    z["riesgo_seguridad"] = z["alerta_criminalidad_extrema"].fillna(False).astype(bool)
    z["ingreso_alto"] = ~z["sin_ingreso_alto"].fillna(True).astype(bool)

    # --- Manzanas: solo bordes ----------------------------------------------
    # Se filtran contra las zonas vigentes. Sin esto, El Porvenir seguiria
    # dibujando las manzanas de las zonas que pasaron a otro distrito.
    mz = pl.read_parquet(DATA / "manzanas.parquet")
    manz = mz.select(["zona_key"]).to_pandas()
    manz["poligono"] = mz["poligono"].to_list()
    vigentes = set(z["IDZONA"].str[:6] + "-" + z["IDZONA"].str[6:9])
    n_manz_antes = len(manz)
    manz = manz[manz["zona_key"].isin(vigentes)].copy()
    manz["ubigeo"] = manz["zona_key"].str[:6]

    # --- Encuadre por distrito ----------------------------------------------
    # Del bounding box de la geometria vigente, no de un archivo aparte: si el
    # pipeline cambia el universo, el encuadre lo sigue solo.
    vista = {}
    for ubi, grp in z.dropna(subset=["geom"]).groupby("distrito"):
        b = np.array([g.bounds for g in grp["geom"]])
        vista[ubi] = dict(min_lon=b[:, 0].min(), min_lat=b[:, 1].min(),
                          max_lon=b[:, 2].max(), max_lat=b[:, 3].max(),
                          nombre=grp["nombre_distrito"].iloc[0])

    diag = dict(n_zonas=len(z), n_sin_geom=int(z["geom"].isna().sum()),
                manz_total=n_manz_antes, manz_usadas=len(manz))
    return z, manz, vista, diag


@st.cache_data(show_spinner=False)
def filas_poligono(firma, ubigeo):
    """
    Explota la geometria a filas dibujables (una por parte del multipoligono).
    Cacheado por distrito porque la conversion a listas de Python es lo caro y
    no cambia al mover un control.
    """
    z, _, _, _ = cargar(firma)
    sub = z[(z["distrito"] == ubigeo) & z["geom"].notna()]
    filas = []
    for _, r in sub.iterrows():
        for anillos in anillos_de_geometria(r["geom"]):
            filas.append({"IDZONA": r["IDZONA"], "p": anillos})
    return pd.DataFrame(filas)


# ===========================================================================
# COLOR
# ===========================================================================

def hex_to_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def clasificar_cortes(vals, escala, cortes, alpha=210):
    """
    Clasificacion por cortes fijos, para porcentajes. `cortes` son los limites
    INTERIORES: la ultima clase queda abierta. Las zonas sin dato salen en gris,
    no en la clase mas baja.
    """
    v = np.asarray(vals, dtype=float)
    idx = np.clip(np.digitize(v, cortes), 0, len(escala) - 1)
    rgb = [hex_to_rgb(c) + [alpha] for c in escala]
    gris = hex_to_rgb(COLOR_SIN_DATO) + [alpha]
    return [gris if np.isnan(x) else rgb[i] for x, i in zip(v, idx)]


def leyenda_html(pares):
    celdas = "".join(
        f'<div style="flex:1;min-width:78px;text-align:center">'
        f'<div style="background:{c};height:13px;'
        f'border:1px solid rgba(65,64,66,.18)"></div>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:10px;'
        f'color:{IPA_CARBON};margin-top:3px">{t}</div></div>'
        for c, t in pares)
    return (f'<div style="display:flex;gap:3px;margin:2px 0 8px 0;'
            f'flex-wrap:wrap">{celdas}</div>')


# ===========================================================================
# VISTA
# ===========================================================================

def calcular_vista(v, nombre, ancho_px, alto_px):
    """
    Encuadre automatico: centro y zoom desde el bounding box del distrito, para
    que SIEMPRE entre completo. Se toma el minimo entre el zoom que hace calzar
    el ancho y el que hace calzar el alto, porque los distritos tienen formas
    muy distintas: Ate es ancho y San Juan de Lurigancho es alto.
    """
    margen = MARGEN_POR_DISTRITO.get(nombre, MARGEN_VISTA)

    def merc_y(lat):
        return np.degrees(np.log(np.tan(np.pi / 4 +
                                        np.radians(np.clip(lat, -85, 85)) / 2)))

    lon_span = max(v["max_lon"] - v["min_lon"], 1e-6)
    lat_span = max(merc_y(v["max_lat"]) - merc_y(v["min_lat"]), 1e-6)
    zoom = min(np.log2(ancho_px / 256 * 360 / lon_span),
               np.log2(alto_px / 256 * 360 / lat_span))
    return pdk.ViewState(
        longitude=(v["min_lon"] + v["max_lon"]) / 2,
        latitude=(v["min_lat"] + v["max_lat"]) / 2,
        zoom=float(np.clip(zoom + np.log2(margen), 3, 16)), pitch=0, bearing=0,
    )


# ===========================================================================
# COORDENADAS PEGADAS
# ===========================================================================

def parsear_coordenadas(texto):
    """
    Una coordenada por linea. Acepta coma, punto y coma, tab o espacios como
    separador, y un rotulo opcional despues del par.

    DECISION: el orden invertido se CORRIGE en vez de rechazarse. Pegar lon/lat
    es el error mas comun cuando el dato viene de un sistema de informacion
    geografica, y en Peru los dos rangos no se solapan, asi que la deteccion es
    inequivoca. Se avisa igual, porque si el archivo de origen esta invertido
    conviene saberlo antes de seguir usandolo.
    """
    puntos, errores, invertidos = [], [], 0

    for n, linea in enumerate(texto.splitlines(), start=1):
        s = linea.strip()
        if not s or s.startswith("#"):
            continue

        crudos = re.findall(r"[-+]?\d+\.\d+|[-+]?\d+", s)
        if len(crudos) < 2:
            errores.append(f"línea {n}: no se encontraron dos números en «{s}»")
            continue
        try:
            a, b = float(crudos[0]), float(crudos[1])
        except ValueError:
            errores.append(f"línea {n}: no se pudo leer el par en «{s}»")
            continue

        ok_directo = (LAT_PERU[0] <= a <= LAT_PERU[1] and
                      LON_PERU[0] <= b <= LON_PERU[1])
        ok_inverso = (LAT_PERU[0] <= b <= LAT_PERU[1] and
                      LON_PERU[0] <= a <= LON_PERU[1])

        if ok_directo:
            lat, lon = a, b
        elif ok_inverso:
            lat, lon = b, a
            invertidos += 1
        else:
            errores.append(f"línea {n}: ({a}, {b}) cae fuera del Perú")
            continue

        resto = s
        for c in crudos[:2]:
            resto = resto.replace(c, "", 1)
        rotulo = resto.strip(" ,;\t|") or f"P{len(puntos) + 1}"
        puntos.append({"lat": lat, "lon": lon, "rotulo": rotulo})

    return puntos, errores, invertidos


def ubicar_puntos(puntos, zd):
    """
    En que zona cae cada punto. Se resuelve sobre la misma geometria que se
    dibuja, asi que la tabla dice exactamente lo que se ve en el mapa.

    Un punto fuera de toda zona del distrito se reporta como tal en vez de
    asignarse a la mas cercana. Puede ser un error de digitacion, una
    asignacion de distrito equivocada, o territorio que salio de El Porvenir
    con la division distrital.
    """
    from shapely.geometry import Point

    val = zd[zd["geom"].notna()]
    cajas = np.array([g.bounds for g in val["geom"]]) if len(val) else np.zeros((0, 4))

    for pt in puntos:
        p = Point(pt["lon"], pt["lat"])
        pt["IDZONA"] = None
        if not len(cajas):
            continue
        cand = np.where((cajas[:, 0] <= pt["lon"]) & (pt["lon"] <= cajas[:, 2]) &
                        (cajas[:, 1] <= pt["lat"]) & (pt["lat"] <= cajas[:, 3]))[0]
        for i in cand:
            if val.iloc[i]["geom"].contains(p):
                pt["IDZONA"] = val.iloc[i]["IDZONA"]
                break
    return puntos


# ===========================================================================
# CARGA Y BARRA PRINCIPAL
# ===========================================================================

FIRMA = firma_datos()
zonas_all, manz_all, vistas, diag = cargar(FIRMA)
nombres = {v["nombre"]: ubi for ubi, v in vistas.items()}

with st.container(key="barra_principal"):
    st.markdown(
        '<div class="titulo-barra">'
        '<span class="marca">Innovations for Poverty Action</span>'
        'Piloto de Aprendizaje: priorización de zonas'
        '<span class="sub"> &nbsp;·&nbsp; Ate · San Juan de Lurigancho · '
        'El Porvenir</span></div>', unsafe_allow_html=True)

    # El instructivo es la pagina de entrada a proposito. El mapa se interpreta
    # mal si quien lo mira no sabe que la cobertura compara un registro actual
    # contra un censo de 2017, ni que la seleccion depende de un supuesto de
    # crecimiento. Un selector de paginas, y no pestañas, porque asi el mapa
    # solo se construye cuando alguien lo pide.
    pagina = st.radio("Sección", ["Instructivo", "Mapa dinámico"],
                      horizontal=True, label_visibility="collapsed")


# ===========================================================================
# PAGINA 1: INSTRUCTIVO
# ===========================================================================

if pagina == "Instructivo":

    # --- Cifras del instructivo ---------------------------------------------
    # Todas salen del parquet, asi que el texto se actualiza solo cuando se
    # vuelve a correr el pipeline. Ninguna cifra esta escrita a mano.
    n_por_dist = {v["nombre"]: int((zonas_all["distrito"] == ubi).sum())
                  for ubi, v in vistas.items()}
    n_perfiles = int(zonas_all["perfil"].dropna().nunique())
    brecha_total = float(zonas_all["brecha_meta_ofis"].sum())
    n_riesgo = int(zonas_all["riesgo_seguridad"].sum())
    n_alto = int(zonas_all["ingreso_alto"].sum())

    # Meta de empadronamiento por distrito. Sale del parquet, no esta escrita a
    # mano: es el mismo numero que el procedimiento de priorizacion usa para
    # decidir hasta donde crece cada bloque, asi que el tablero y el
    # procedimiento no pueden quedar desalineados.
    metas = (zonas_all.groupby(["distrito", "nombre_distrito"], as_index=False)
             .agg(meta=("meta_hogares", "first"), zonas=("IDZONA", "count"))
             .dropna(subset=["meta"]))
    metas = metas.sort_values("meta", ascending=False)
    meta_total = float(metas["meta"].sum())
    max_meta = max(float(metas["meta"].max()) if len(metas) else 1, 1)

    def mil(x):
        return f"{x:,.0f}".replace(",", " ")

    # Barras de la meta por distrito. Sin leyenda: la cifra va sobre la barra,
    # que es lo que pide la guia de visualizacion de IPA.
    barras_meta = ""
    for _, r in metas.iterrows():
        ancho = max(100 * float(r["meta"]) / max_meta, 6)
        barras_meta += (
            f'<div class="fila"><div class="et">{r["nombre_distrito"]}</div>'
            f'<div class="b" style="width:{ancho:.1f}%;background:{IPA_VERDE}">'
            f'{mil(r["meta"])}</div></div>')

    def tarjeta(icono, titulo, cuerpo):
        return (f'<div class="tarjeta"><h4><span class="icono">{icono}</span>'
                f'{titulo}</h4>{cuerpo}</div>')

    def ley(color, texto):
        return (f'<div class="ley"><div class="sw" style="background:{color}">'
                f'</div><div>{texto}</div></div>')

    def paso(n, texto):
        return f'<div class="paso"><div class="num">{n}</div><p>{texto}</p></div>'

    rampa = "".join(f'<div style="background:{c}"></div>'
                    for c in ESCALA_COBERTURA)
    rampa_et = "".join(f'<div>{t}</div>' for t in ETIQUETAS_COBERTURA)

    perfiles_lst = sorted(p for p in zonas_all["perfil"].dropna().unique())
    ley_perfil = "".join(
        ley(PALETA_PERFIL[i % len(PALETA_PERFIL)], f"Perfil {p}")
        for i, p in enumerate(perfiles_lst))

    st.markdown(f"""
<div class="doc">

<div class="entrada"><div>
Este tablero muestra dónde conviene empezar el empadronamiento del Sistema de
Focalización de Hogares, conocido como SISFOH, en Ate, San Juan de Lurigancho y
El Porvenir. Presenta las {diag['n_zonas']} zonas de los tres distritos con la
información que se usó para elegirlas, y permite ver cómo cambia esa elección
según el supuesto de crecimiento de hogares que se adopte.
</div></div>

<h2>Qué es este tablero</h2>

<div class="grid2">
{tarjeta("🎯", "Para qué sirve",
         "<p>El Piloto de Aprendizaje empadrona hogares en tres distritos para "
         "probar y ajustar el procedimiento antes de aplicarlo a mayor escala. "
         "No alcanza el presupuesto para visitar todas las zonas, así que hay "
         "que elegir.</p><p>Este tablero muestra el resultado de esa elección "
         "y, sobre todo, la información con la que se tomó.</p>")}
{tarjeta("🧭", "Qué unidad usa",
         f"<p>La unidad es la zona censal del Instituto Nacional de "
         f"Estadística e Informática, el INEI. Cada polígono del mapa es una "
         f"zona: {n_por_dist.get('Ate', 0)} en Ate, "
         f"{n_por_dist.get('San Juan de Lurigancho', 0)} en San Juan de "
         f"Lurigancho y {n_por_dist.get('El Porvenir', 0)} en El Porvenir.</p>"
         "<p>Las manzanas aparecen como líneas finas de referencia, para "
         "ubicarse, pero no llevan ningún dato.</p>")}
</div>

<h2>Cómo leer los colores del mapa</h2>

<p>El mapa se pinta de una de dos maneras, y encima se pueden marcar las dos
exclusiones. Conviene reconocer estos colores antes de abrirlo.</p>

<div class="grid3">
<div class="tarjeta">
<h4><span class="icono">📊</span>Cobertura</h4>
<p>Cuánto de la zona ya está registrado. El verde se oscurece a medida que
sube.</p>
<div class="rampa">{rampa}</div>
<div class="rampa-et">{rampa_et}</div>
<p>Las dos últimas clases son azules porque ya no hay brecha: el registro tiene
más hogares que los que contó el censo. El azul se oscurece cuando el exceso es
mayor.</p>
</div>

<div class="tarjeta">
<h4><span class="icono">🗂️</span>Perfil</h4>
<p>Qué tipo de zona es. Los {n_perfiles} perfiles no están ordenados: el perfil
3 no es mejor ni peor que el 1, es distinto.</p>
{ley_perfil}
</div>

<div class="tarjeta">
<h4><span class="icono">🚫</span>Exclusiones</h4>
<p>Zonas que el procedimiento retira del operativo. Al marcarlas, tapan el color
de fondo.</p>
{ley(COLOR_RIESGO, f"Riesgo de seguridad ({n_riesgo} zonas)")}
{ley(COLOR_INGRESO_ALTO, f"Ingreso alto ({n_alto} zonas)")}
{ley(COLOR_AMBOS, "Ambas condiciones")}
<p style="margin-top:8px">El contorno verde oscuro marca las zonas
seleccionadas para el piloto.</p>
</div>
</div>

<h2>Qué significa cada dato</h2>

<div class="grid2">
{tarjeta("📈", "Cobertura",
         "<p>Es la proporción de hogares de una zona que ya están registrados. "
         "Compara los hogares del Registro Integrado del SISFOH, llamado RIS, "
         "con los hogares que el Censo 2017 contó en esa misma zona. Una "
         "cobertura de 40 por ciento significa que cerca de seis de cada 10 "
         "hogares todavía no están registrados.</p>"
         "<p>Puede pasar de 100 por ciento. El registro es actual y el censo "
         "tiene ocho años, así que donde el distrito creció hay más hogares "
         "registrados que censados. Eso no es un error: indica que el censo se "
         "quedó corto en esa zona.</p>")}
{tarjeta("🏠", "Potencial de hogares sin empadronar",
         "<p>Es el número de hogares que faltan por registrar en una zona. Es "
         "la diferencia entre los hogares del censo y los del registro.</p>"
         "<p>Cuando el registro supera al censo, la brecha se cuenta como cero, "
         "porque una zona sobre registrada no aporta hogares nuevos al "
         "operativo.</p>")}
{tarjeta("🧩", "Perfil",
         f"<p>Agrupa a las zonas según su comportamiento conjunto en varias "
         f"características, entre ellas cobertura, tamaño, pobreza y "
         f"densidad.</p><p>Hay {n_perfiles} perfiles. Sirven para saber si el "
         f"piloto está aprendiendo sobre distintos tipos de territorio o si "
         f"concentra todo su esfuerzo en uno solo.</p>")}
{tarjeta("📍", "Zonas de Intervención del Piloto de Aprendizaje",
         "<p>Son las zonas seleccionadas para el operativo. Forman un bloque "
         "continuo, de modo que una brigada pueda recorrerlo sin traslados "
         "largos.</p><p>En el mapa aparecen con contorno verde oscuro.</p>")}
</div>

<h2>Cómo se eligieron las zonas</h2>

<div class="grid4">
{paso(1, "Se descartan las zonas ya registradas, las que tienen <b>alerta de "
         "criminalidad</b> y las que contienen <b>manzanas de ingreso "
         "alto</b>.")}
{paso(2, "Se parte de una zona con <b>déficit alto</b> y se crece hacia zonas "
         "vecinas, de modo que el bloque quede continuo.")}
{paso(3, "Se detiene al reunir la <b>meta de hogares</b> del distrito, más un "
         "margen para hogares no encontrados, rechazos y direcciones "
         "inválidas.")}
{paso(4, "Entre las alternativas posibles se prefiere la que <b>cubre más "
         "perfiles</b> y ocupa menos superficie.")}
</div>

<h2>La meta del proyecto</h2>

<div class="escenarios">
<div class="fichas">
{tarjeta("🎯", "Cuántos hogares hay que empadronar",
         f"<p>El Piloto de Aprendizaje debe empadronar <b>{mil(meta_total)} "
         f"hogares</b> en los tres distritos. La meta se fija por distrito y "
         f"orienta hasta dónde se extiende el operativo en cada uno.</p>"
         f"<p>El procedimiento de priorización busca reunir esa meta con un "
         f"margen adicional, porque en campo siempre hay hogares no "
         f"encontrados, rechazos y direcciones inválidas.</p>")}
{tarjeta("📐", "La meta frente a la brecha",
         f"<p>La brecha estimada en los tres distritos es de "
         f"{mil(brecha_total)} hogares sin registrar. La meta cubre cerca del "
         f"{100 * meta_total / max(brecha_total, 1):.0f} por ciento de esa "
         f"brecha.</p>"
         f"<p>Por eso hay que elegir zonas. El piloto no busca cerrar la "
         f"brecha, sino probar y ajustar el procedimiento antes de aplicarlo a "
         f"mayor escala.</p>")}
</div>
<div class="tarjeta">
<h4>San Juan de Lurigancho concentra 13 000 de los {mil(meta_total)} hogares de
la meta</h4>
<div class="barras">{barras_meta}</div>
<div class="fuente">Meta de empadronamiento por distrito, en hogares.
Fuente: procedimiento de priorización del proyecto, IPA.</div>
</div>
</div>

<h2>Cómo usar el mapa</h2>

<div class="grid3">
{tarjeta("1️⃣", "Elija distrito y forma de contar la brecha",
         "<p>La tabla superior resume los hogares del censo, los del registro, "
         "el potencial sin empadronar y la meta del distrito, separando las zonas de "
         "intervención del resto. El mapa se reencuadra solo al cambiar de "
         "distrito.</p>"
         "<p>El control de brecha alterna entre el conteo oficial del Censo "
         "2017 y el mismo conteo ajustado al crecimiento de hogares estimado a "
         "2025. Las dos cifras se reportan, ninguna reemplaza a la otra.</p>")}
{tarjeta("2️⃣", "Cambie el color y marque exclusiones",
         "<p>El color alterna entre perfil y cobertura. Las casillas de riesgo "
         "e ingreso alto tapan el color de fondo. El dato sigue apareciendo al "
         "pasar el cursor sobre la zona.</p>")}
{tarjeta("3️⃣", "Ubique coordenadas",
         "<p>El panel derecho acepta coordenadas pegadas, una por línea. El "
         "tablero las dibuja e indica en qué zona cae cada una y si esa zona "
         "forma parte del piloto.</p>")}
</div>

<h2>Alcances y límites</h2>

<p>Las cifras de este tablero sirven para planificar el operativo. No sirven
para estimar pobreza ni para caracterizar hogares individuales. Los cinco
límites que siguen condicionan cómo deben leerse.</p>

<div class="grid-lim">
<div class="limite"><b>⏳ El censo tiene ocho años.</b>
<p>Todos los denominadores provienen del Censo 2017. En zonas de crecimiento
reciente el censo subestima los hogares, y por eso existe el escenario
proyectado. El factor de crecimiento es distrital y uniforme, de modo que
reparte el crecimiento por igual dentro del distrito, aunque en la práctica se
concentra en la periferia.</p></div>

<div class="limite"><b>🚨 La alerta de criminalidad mide delitos reportados.</b>
<p>Depende de la presencia policial y de la disposición a denunciar. Excluir
zonas por esta variable retira sistemáticamente las que tienen más presencia
institucional y conserva las sub registradas, que pueden ser menos seguras y no
aparecer. La ausencia de alerta no es evidencia de que una zona sea segura, y el
protocolo de campo no debe relajarse por ello.</p></div>

<div class="limite"><b>🗺️ La estratificación de ingresos tiene vacíos.</b>
<p>Proviene de la cartografía del INEI y no cubre todas las zonas. Las zonas sin
dato no se marcan como ingreso alto, porque la falta de información no es
evidencia de ingreso alto. Descartarlas sesgaría la selección en contra de la
periferia, que es donde la cartografía tiene más vacíos.</p></div>

<div class="limite"><b>✂️ El Porvenir cambió de límites.</b>
<p>El distrito se dividió y parte de su territorio pasó a otro distrito. El
tablero usa la cartografía vigente, con {n_por_dist.get('El Porvenir', 0)}
zonas. Las zonas de la cartografía anterior no aparecen. Una coordenada de esa
zona perdida se reporta como fuera del distrito.</p></div>

<div class="limite"><b>🔀 La selección es una buena solución, no la única.</b>
<p>El procedimiento busca un bloque continuo y compacto que reúna la meta de
hogares. El problema no tiene una solución óptima calculable, así que el
resultado es una alternativa razonable y reproducible entre varias posibles.
Cambiar la meta, el margen de sobremuestra o los umbrales cambia la
selección.</p></div>
</div>

<h2>Fuentes y alcance de los datos</h2>

<div class="cierre">
<table>
<tr><th>Dato</th><th>Fuente</th></tr>
<tr><td>Zonas censales y población</td><td>Censo Nacional 2017, INEI</td></tr>
<tr><td>Hogares registrados</td><td>Registro Integrado del SISFOH</td></tr>
<tr><td>Estrato de ingreso por manzana</td>
<td>Planos estratificados por ingreso, INEI</td></tr>
<tr><td>Alerta de criminalidad</td>
<td>Sistema de Denuncias Policiales, SIDPOL</td></tr>
<tr><td>Selección de zonas</td>
<td>Procedimiento de priorización del proyecto, IPA</td></tr>
</table>

{tarjeta("🔄", "Cuándo se actualiza",
         "<p>El tablero lee directamente el resultado del procedimiento de "
         "priorización. Cada vez que ese procedimiento se vuelve a correr, las "
         "cifras de esta página y los mapas se actualizan solos.</p>"
         f"<p>Zonas cargadas en esta versión: {diag['n_zonas']}. Manzanas "
         f"dibujadas como referencia: {diag['manz_usadas']:,}."
         .replace(",", " ") + "</p>")}
</div>

<div class="pie">
Innovations for Poverty Action · Proyecto SISFOH con el Organismo de
Focalización e Información Social y la Cooperación Alemana al Desarrollo, GIZ.
</div>

</div>
    """, unsafe_allow_html=True)

    st.stop()


# ===========================================================================
# PAGINA 2: MAPA DINAMICO
# ===========================================================================

with st.container(key="barra_controles"):
    c_dist, c_brecha, c_mapa = st.columns([2.0, 3.0, 5.4])

    with c_dist:
        st.markdown('<div class="grupo">Distrito</div>', unsafe_allow_html=True)
        distrito_sel = st.selectbox("Distrito", options=sorted(nombres),
                                    label_visibility="collapsed")

    with c_brecha:
        st.markdown('<div class="grupo">Potencial sin empadronar</div>',
                    unsafe_allow_html=True)
        # El switch cambia la cifra reportada Y las zonas de intervencion, porque la
        # seleccion se corrio por separado con cada conteo de hogares.
        escenario = st.radio(
            "Brecha", ["Oficial (censo 2017)", "Proyectada (crecimiento 2025)"],
            horizontal=True, label_visibility="collapsed",
            help="Cambia la brecha reportada y, con ella, las zonas que el "
                 "Piloto de Aprendizaje interviene.")
    es_pro = escenario.startswith("Proyectada")
    suf = "pro" if es_pro else "ofis"

    with c_mapa:
        st.markdown('<div class="grupo">Mapa</div>', unsafe_allow_html=True)
        m1, m2, m3, m4, m5 = st.columns([2.3, 1.5, 1.3, 1.4, 1.3])
    with m1:
        relleno = st.radio("Color", ["Perfil", "Cobertura"], horizontal=True,
                           label_visibility="collapsed")
    with m2:
        ver_riesgo = st.checkbox("Riesgo de seguridad", value=False,
                                 help="Pinta las zonas con alerta de "
                                      "criminalidad.")
    with m3:
        ver_alto = st.checkbox("Ingreso alto", value=False,
                               help="Pinta las zonas con presencia de manzanas "
                                    "de ingreso alto.")
    with m4:
        ver_piloto = st.checkbox("Zonas de intervención", value=True,
                                 help="Contorno sobre las zonas seleccionadas "
                                      "en el escenario activo.")
    with m5:
        ver_manzanas = st.checkbox("Manzanas", value=True,
                                   help="Capa de bordes de manzana. Solo "
                                        "referencia urbana, sin datos.")

ubigeo_sel = nombres[distrito_sel]
zd = zonas_all[zonas_all["distrito"] == ubigeo_sel].reset_index(drop=True)

col_cob = f"cobertura_op_{suf}"
col_bre = f"brecha_meta_{suf}"
col_ine = f"inei_h_tot_op_{suf}"
col_blq = "zona_ofis_pro" if es_pro else "zona_ofis"
en_piloto = zd[col_blq].notna()


def cifras(sub):
    """
    Hogares del censo, del registro y brecha de un subconjunto de zonas. La
    cobertura se calcula de las sumas y no se promedia: promediar coberturas
    haria pesar igual a una zona de 30 hogares y a una de 900.
    """
    con = sub[sub[col_ine].notna() & sub["h_total"].notna()]
    inei = float(con[col_ine].sum())
    ris = float(con["h_total"].sum())
    return dict(n=len(sub), sin_dato=int(len(sub) - len(con)), inei=inei, ris=ris,
                brecha=float(sub[col_bre].fillna(0).sum()),
                cob=(100 * ris / inei if inei else float("nan")))


tot, pil, res = cifras(zd), cifras(zd[en_piloto]), cifras(zd[~en_piloto])


def fila_html(clase, etiqueta, c, nota=""):
    cob = "—" if np.isnan(c["cob"]) else f"{c['cob']:.1f}%"
    return (f'<tr class="{clase}"><td>{etiqueta}'
            f'{f"<span class=nota> · {nota}</span>" if nota else ""}</td>'
            f'<td>{c["n"]:,}</td><td>{c["inei"]:,.0f}</td>'
            f'<td>{c["ris"]:,.0f}</td><td>{c["brecha"]:,.0f}</td>'
            f'<td>{cob}</td></tr>')


etiqueta_esc = "proyectada a 2025" if es_pro else "oficial, censo 2017"

# --- Desagregacion por tipo de zona dentro de la intervencion ---------------
# Responde a la pregunta operativa que sigue a "cuantas zonas entraron": sobre
# que TIPOS de zona va a aprender el piloto, y cuanto pesa cada uno. Un bloque
# que reune la meta con un solo perfil cumple la cifra pero no ensena nada
# sobre los demas tipos de territorio.
#
# Las subfilas solo aparecen para los perfiles efectivamente presentes en la
# seleccion del distrito, y suman exactamente la fila del total de la
# intervencion. Las zonas sin perfil, si las hubiera, entran como "sin perfil"
# para que la suma cuadre y no se pierda ninguna en el camino.
perf_pil = zd[en_piloto].copy()
perf_pil["perfil_et"] = perf_pil["perfil"].fillna("sin perfil")
subfilas = ""
for p in sorted(perf_pil["perfil_et"].unique()):
    c = cifras(perf_pil[perf_pil["perfil_et"] == p])
    etiqueta = f"Perfil {p}" if p != "sin perfil" else "Sin perfil"
    parte = 100 * c["brecha"] / pil["brecha"] if pil["brecha"] else 0
    subfilas += fila_html("sub", f"↳ {etiqueta}", c,
                          f"{parte:.0f}% del potencial de la intervención")

st.markdown(
    '<table class="resumen">'
    '<tr><th>Ámbito</th><th>Zonas</th><th>Hogares INEI</th>'
    '<th>Hogares RIS</th><th>Potencial sin empadronar</th><th>Cobertura</th></tr>'
    + fila_html("piloto", "Zonas de Intervención del Piloto de Aprendizaje", pil,
                f"selección {etiqueta_esc}")
    + subfilas
    + fila_html("", "Resto del distrito", res)
    + fila_html("total", f"{distrito_sel}, total", tot,
                f'{tot["sin_dato"]} zonas sin dato' if tot["sin_dato"] else "")
    + '</table>', unsafe_allow_html=True)

# La meta del distrito da la escala de lo que se ve arriba: sin ella, una brecha
# de 69 000 hogares no dice nada sobre el tamano del operativo. Sale del parquet,
# que es el mismo numero que usa el procedimiento de priorizacion.
meta_dist = zd["meta_hogares"].dropna()
meta_dist = float(meta_dist.iloc[0]) if len(meta_dist) else float("nan")
meta_proy = float(zonas_all.groupby("distrito")["meta_hogares"].first().sum())
if not np.isnan(meta_dist):
    st.markdown(
        f'<div class="meta-linea"><span class="et">Meta de empadronamiento</span>'
        f'<span class="v">{meta_dist:,.0f}</span> hogares en {distrito_sel}, '
        f'de <span class="v">{meta_proy:,.0f}</span> en todo el proyecto.'
        f'</div>'.replace(",", " "), unsafe_allow_html=True)

st.markdown(
    f'<div class="disclaimer"><b>Cómo leer el mapa.</b> Cada polígono es una '
    f'zona censal del INEI. La brecha mostrada es la <b>{etiqueta_esc}</b>. La '
    f'cobertura compara los hogares del Registro Integrado con los del Censo '
    f'2017, y puede pasar de 100% porque el registro es actual y el censo tiene '
    f'ocho años. Las casillas de riesgo e ingreso alto tapan el color de fondo: '
    f'en esas zonas deja de verse el perfil o la cobertura, pero el dato sigue '
    f'apareciendo al pasar el cursor. El detalle de cada variable está en el '
    f'Instructivo.</div>', unsafe_allow_html=True)


# ===========================================================================
# MAPA
# ===========================================================================

col_mapa, col_lado = st.columns([3.4, 1.35])

with col_lado:
    st.markdown('<div class="panel"><h4>Coordenadas</h4>'
                'Pegue una por línea, en formato <code>latitud, longitud</code>. '
                'Se acepta un rótulo después del par. Si el par viene invertido, '
                'el tablero lo corrige y avisa.</div>', unsafe_allow_html=True)
    texto_coords = st.text_area(
        "Coordenadas", height=118, label_visibility="collapsed",
        placeholder="-12.0264, -76.9412  Local 1\n-12.0311, -76.9502  Local 2")
    tam_punto = st.slider("Tamaño del punto (metros)", 20, 400, 90, 10)

puntos, err_coords, n_invertidos = parsear_coordenadas(texto_coords or "")
puntos = ubicar_puntos(puntos, zd)

with col_mapa:
    # Los niveles de perfil se ordenan sobre el universo COMPLETO, no sobre el
    # distrito: si se ordenaran por distrito, el perfil 2 seria de un color en
    # Ate y de otro en San Juan de Lurigancho, y comparar los mapas dejaria de
    # ser posible.
    perfiles = sorted(p for p in zonas_all["perfil"].dropna().unique())
    tabla_p = {p: hex_to_rgb(PALETA_PERFIL[i % len(PALETA_PERFIL)])
               for i, p in enumerate(perfiles)}

    if relleno == "Perfil":
        base = [tabla_p.get(v, hex_to_rgb(COLOR_SIN_DATO)) + [210]
                for v in zd["perfil"]]
        pares = [(PALETA_PERFIL[perfiles.index(p) % len(PALETA_PERFIL)],
                  f"Perfil {p}") for p in perfiles if (zd["perfil"] == p).any()]
        if zd["perfil"].isna().any():
            pares.append((COLOR_SIN_DATO, "Sin perfil"))
    else:
        base = clasificar_cortes(zd[col_cob].to_numpy(dtype=float),
                                 ESCALA_COBERTURA, CORTES_COBERTURA)
        pares = list(zip(ESCALA_COBERTURA, ETIQUETAS_COBERTURA))
        if zd[col_cob].isna().any():
            pares.append((COLOR_SIN_DATO, "Sin dato"))

    # Las exclusiones tapan el color de fondo. Es lo que corresponde
    # operativamente: una zona excluida no se discute por su perfil sino por su
    # exclusion. Cuando cae en las dos lleva color propio, para que el conteo de
    # la leyenda cuadre con lo que se ve.
    r = zd["riesgo_seguridad"].to_numpy() if ver_riesgo else np.zeros(len(zd), bool)
    a = zd["ingreso_alto"].to_numpy() if ver_alto else np.zeros(len(zd), bool)
    for i in range(len(base)):
        if r[i] and a[i]:
            base[i] = hex_to_rgb(COLOR_AMBOS) + [235]
        elif r[i]:
            base[i] = hex_to_rgb(COLOR_RIESGO) + [235]
        elif a[i]:
            base[i] = hex_to_rgb(COLOR_INGRESO_ALTO) + [235]
    if ver_riesgo:
        pares.append((COLOR_RIESGO, f"Riesgo de seguridad ({int(r.sum())})"))
    if ver_alto:
        pares.append((COLOR_INGRESO_ALTO, f"Ingreso alto ({int(a.sum())})"))
    if ver_riesgo and ver_alto:
        pares.append((COLOR_AMBOS, f"Ambas ({int((r & a).sum())})"))

    titulo = "Perfil de zona" if relleno == "Perfil" else "Cobertura del RIS"
    st.markdown(f'<div style="font-family:Georgia,serif;font-size:1.1rem;'
                f'color:{IPA_VERDE_OSCURO};margin:2px 0 6px 0">{titulo}'
                f'<span style="font-family:Arial,sans-serif;font-size:.80rem;'
                f'color:#6b6b6d"> &nbsp;·&nbsp; {distrito_sel} &nbsp;·&nbsp; '
                f'brecha {etiqueta_esc}</span></div>', unsafe_allow_html=True)
    st.markdown(leyenda_html(pares), unsafe_allow_html=True)

    # Atributos en nombres de una letra: pydeck repite la clave en CADA
    # registro, asi que los nombres largos cuestan envio en cada recarga.
    def txt(col, dec=0):
        return [("sin dato" if pd.isna(v) else
                 (f"{v:,.0f}" if dec == 0 else f"{v:,.1f}"))
                for v in zd[col]]

    attrs = pd.DataFrame({
        "IDZONA": zd["IDZONA"], "z": zd["etiqueta"],
        "f": zd["perfil"].fillna("sin perfil"),
        "k": txt(col_cob, 1), "e": txt("h_total"), "t": txt(col_ine),
        "b": txt(col_bre), "s": zd[col_blq].fillna("fuera del piloto"),
        "c": base,
    })
    df_zona = filas_poligono(FIRMA, ubigeo_sel).merge(attrs, on="IDZONA",
                                                      how="left")

    capas = [pdk.Layer(
        "PolygonLayer", data=df_zona, get_polygon="p", get_fill_color="c",
        get_line_color=BORDE_ZONA, line_width_min_pixels=0.8,
        stroked=True, filled=True, pickable=True, auto_highlight=True,
    )]

    if ver_manzanas:
        mzd = manz_all[manz_all["ubigeo"] == ubigeo_sel]
        if len(mzd):
            capas.append(pdk.Layer(
                "PolygonLayer", data=pd.DataFrame({"p": mzd["poligono"].tolist()}),
                get_polygon="p", filled=False, stroked=True,
                get_line_color=BORDE_MANZANA, line_width_min_pixels=0.4,
                pickable=False,
            ))

    # El contorno del piloto va sin relleno para no tapar el perfil ni la
    # cobertura, que es justamente la lectura que se quiere cruzar: que tipo de
    # zona hay dentro del bloque que se va a recorrer.
    if ver_piloto:
        sel = df_zona[df_zona["s"] != "fuera del piloto"]
        if len(sel):
            capas.append(pdk.Layer(
                "PolygonLayer", data=sel[["p"]], get_polygon="p", filled=False,
                stroked=True, get_line_color=BORDE_PILOTO,
                line_width_min_pixels=2.6, pickable=False,
            ))

    if puntos:
        df_pt = pd.DataFrame([{"lon": p["lon"], "lat": p["lat"], "r": p["rotulo"]}
                              for p in puntos])
        capas.append(pdk.Layer(
            "ScatterplotLayer", data=df_pt, get_position=["lon", "lat"],
            get_fill_color=COLOR_PUNTO, get_radius=tam_punto,
            radius_min_pixels=4, radius_max_pixels=40, stroked=True,
            get_line_color=[255, 255, 255, 255], line_width_min_pixels=1.5,
            pickable=True,
        ))
        capas.append(pdk.Layer(
            "TextLayer", data=df_pt, get_position=["lon", "lat"], get_text="r",
            get_size=13, get_color=[65, 64, 66, 255],
            get_pixel_offset=[0, -16], pickable=False,
        ))

    st.pydeck_chart(
        pdk.Deck(
            layers=capas,
            initial_view_state=calcular_vista(vistas[ubigeo_sel], distrito_sel,
                                              900, ALTO_MAPA_PX),
            tooltip={"html": "<b>{z}</b><br/>Perfil: {f}<br/>"
                             "Cobertura: {k}%<br/>Hogares RIS: {e} de {t} "
                             "(censo)<br/>Potencial sin empadronar: {b}<br/>"
                             "Piloto: {s}",
                     "style": {"fontSize": "12px",
                               "backgroundColor": IPA_VERDE_OSCURO,
                               "color": "#ffffff",
                               "fontFamily": "Arial, Helvetica, sans-serif"}},
            map_provider="carto", map_style=pdk.map_styles.LIGHT,
        ),
        width="stretch", height=ALTO_MAPA_PX,
        # La key fuerza a deck.gl a remontarse: initial_view_state solo se
        # aplica en el montaje inicial, sin esto el mapa conserva el encuadre
        # del distrito anterior. Solo entran las variables que deben reencuadrar
        # o repintar; el texto de coordenadas no, para no remontar en cada tecla.
        key=f"mapa_{ubigeo_sel}_{relleno}_{es_pro}_{ver_riesgo}_{ver_alto}"
            f"_{ver_piloto}_{ver_manzanas}_{len(puntos)}_{tam_punto}",
    )


with col_lado:
    if n_invertidos:
        st.warning(f"{n_invertidos} coordenada(s) venían en orden longitud y "
                   f"latitud. El tablero las corrigió. Conviene revisar el "
                   f"archivo de origen.")
    if err_coords:
        st.error("No se pudieron leer:\n\n" +
                 "\n".join(f"- {e}" for e in err_coords[:6]) +
                 (f"\n- y {len(err_coords) - 6} más" if len(err_coords) > 6 else ""))
    if puntos:
        idx = zd.set_index("IDZONA")
        filas = []
        for p in puntos:
            r_ = idx.loc[p["IDZONA"]] if p["IDZONA"] in idx.index else None
            filas.append({
                "Punto": p["rotulo"],
                "Zona": (r_["etiqueta"] if r_ is not None else "fuera"),
                "Perfil": (r_["perfil"] if r_ is not None and pd.notna(r_["perfil"])
                           else "sin dato"),
                "Piloto": ("sí" if r_ is not None and pd.notna(r_[col_blq])
                           else "no"),
            })
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        fuera = sum(1 for p in puntos if p["IDZONA"] is None)
        if fuera:
            st.caption(f"{fuera} punto(s) caen fuera de {distrito_sel}. Puede "
                       f"ser un error de digitación, una asignación de distrito "
                       f"equivocada o, en El Porvenir, territorio que pasó al "
                       f"otro distrito tras la división.")

    # Recordatorios. Son las tres advertencias que mas cambian la lectura del
    # mapa, asi que se repiten aca aunque esten en el Instructivo: quien llega
    # directo al mapa no las habria visto. El icono da el punto de entrada
    # visual; el texto es el que hace el trabajo.
    st.markdown(
        f'<div class="panel recordatorios" style="margin-top:10px">'
        f'<h4>Antes de decidir</h4>'
        f'<div class="rec"><span>⏳</span><div>La cobertura compara un registro '
        f'actual contra un censo de 2017. Por eso puede pasar de 100%.</div></div>'
        f'<div class="rec"><span>🚨</span><div>La ausencia de alerta de '
        f'criminalidad no significa que la zona sea segura. Mide delitos '
        f'reportados.</div></div>'
        f'<div class="rec"><span>🗺️</span><div>Las zonas sin estrato de ingreso '
        f'no se marcan como ingreso alto. La falta de dato no es '
        f'evidencia.</div></div>'
        f'<div class="rec"><span>🔀</span><div>La selección cambia con el '
        f'escenario de brecha. Compare los dos antes de fijarla.</div></div>'
        f'<div class="rec-pie">📘 El detalle completo está en el '
        f'Instructivo.</div></div>',
        unsafe_allow_html=True)

    st.caption(f"Zonas cargadas: {diag['n_zonas']} · manzanas dibujadas: "
               f"{diag['manz_usadas']:,} de {diag['manz_total']:,}")
