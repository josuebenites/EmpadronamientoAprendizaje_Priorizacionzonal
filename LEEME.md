# Tablero de priorización de zonas

Empadronamiento de aprendizaje. Ate, San Juan de Lurigancho y El Porvenir.

## Cómo correrlo

```
pip install -r requirements.txt
streamlit run app.py
```

Se abre solo en el navegador. La carpeta `data/` ya viene con los datos
procesados, así que no hay que generar nada.

## Qué mirar primero

- **`DOCUMENTACION.md`** es el documento principal. Está escrito para leerse sin
  saber de programación. El §1 es un resumen de una página.
- **`DOCUMENTACION.md` §11** son las **4 preguntas abiertas** sobre
  `Zonas Piloto.xlsx`. Es lo que necesitamos confirmar.

## Qué es cada archivo

| Archivo | Qué es |
|---|---|
| `app.py` | El tablero |
| `DOCUMENTACION.md` | Cómo se hizo, de dónde sale cada dato y qué limitaciones tiene |
| `data/*.parquet` | Datos ya procesados, es lo que el tablero lee |
| `scripts/generar_manzanas.py` | Genera `data/` desde las fuentes. Se corre una sola vez |
| `01_Raw/Zonas Piloto.xlsx` | Fuente de la cobertura (hogares RI vs Censo 2017) |
| `ingresos_ate_sjl_consolidado.shp` | Fuente del nivel de ingreso y de las manzanas |
| `Targeting Criteria/zona_perfiles.gpkg` | Zonas censales INEI 2017 |

## Nota sobre regenerar los datos

`scripts/generar_manzanas.py` necesita además las descargas de Overture Maps
(`data/raw_buildings/`, 110 MB) que no se incluyen por peso. Sirven para contar
construcciones y para dibujar las manzanas de El Porvenir. **Para usar el
tablero no hacen falta**: `data/` ya viene generado.
