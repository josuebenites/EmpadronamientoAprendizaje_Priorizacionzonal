# Empadronamiento de aprendizaje: priorización de zonas

**Documentación técnica y de fuentes**
Distritos: Ate, San Juan de Lurigancho y El Porvenir (Trujillo)
Última actualización: 27 de agosto de 2026

---

## 1. Resumen en una página (para presentar)

El tablero muestra **dos mapas del mismo distrito, lado a lado**, para decidir dónde inicia el operativo de empadronamiento:

| Mapa | Qué muestra | Unidad del dato |
|---|---|---|
| Izquierdo | Nivel de ingreso (estrato del INEI) | **Manzana** |
| Derecho | Cobertura de empadronamiento (% o cantidad) | **Zona censal INEI 2017** |

Como la cobertura se mide por zona censal y no por manzana, en el mapa derecho **varias manzanas vecinas comparten color**: pertenecen a la misma zona. Es intencional y refleja cómo se organiza el trabajo de campo.

**Lo más importante que hay que saber:**

1. **El nivel de ingreso es real y oficial** en Ate y San Juan de Lurigancho: son las **22,318 manzanas del INEI** con su estratificación oficial. El Porvenir está pendiente.
2. **La cartografía es oficial**: zonas censales del INEI 2017 (266 zonas) y manzanas del INEI para los dos distritos de Lima.
3. **La cobertura ya es real y oficial** (`01_Raw/Zonas Piloto.xlsx`): hogares del **Registro Integrado (RI)** sobre hogares del **Censo INEI 2017**, por zona censal. Ya no queda nada sintético salvo el ingreso de El Porvenir.
4. **La población y los hogares por zona son reales** (INEI 2017). En cambio las **"construcciones detectadas" no son hogares**: es una detección satelital que ahora solo se usa en el dato por manzana (§3.3).

**Cifras actuales:**

| Distrito | Zonas | Manzanas | Población (INEI) | Hogares (INEI 2017) | Hogares en el RI | Cobertura |
|---|---|---|---|---|---|---|
| Ate | 90 | 7,939 | 581,309 | 161,649 | 101,980 | **63.1%** |
| San Juan de Lurigancho | 158 | 14,379 | 980,619 | 265,468 | 248,742 | **93.7%** |
| El Porvenir | 18 (13 con dato) | 2,058 | 131,967 | 25,521 | 32,572 | **127.6%** |
| **Total** | **266** | **24,376** | **1,693,895** | **452,638** | **383,294** | **84.7%** |

> **Las manzanas grises son solo de El Porvenir.** Ate y San Juan de Lurigancho no tienen ni una: sus 90 y 158 zonas están todas cubiertas. El gris se debe a que el Excel **no trae fila** para 5 zonas de El Porvenir, no a códigos que no encajen (§2.6 explica por qué son dos problemas distintos).

> **La cobertura puede pasar del 100%.** El RI es un registro **actual** y el censo es de **2017**. Donde el distrito creció desde entonces hay más hogares registrados que censados, y el porcentaje se dispara. No es un error: es la señal de que el censo 2017 ya quedó corto como denominador (§3.4).

---

## 2. De dónde salen los datos

### 2.1 Zonas censales ✅ OFICIAL

| | |
|---|---|
| **Archivo** | `Targeting Criteria/zona_perfiles.gpkg` |
| **Origen** | Cartografía censal del **INEI, Censo 2017** |
| **Contenido** | 266 zonas censales, con códigos `CODDPTO`, `CODPROV`, `CODDIST`, `CODZONA` |
| **Detalle** | Muy alto: 2,693 vértices por zona en promedio |

Trae además variables reales disponibles para uso futuro: `perfil`, `inei_poblacion`, `media_pobreza`, `n_delitos_p1000`, `servicios_basicos_km2`, `health`, `education`, entre otras 33 columnas.

> **Nota histórica:** al inicio se usó cartografía **INEI‑2007** de un repositorio público, cuyo contorno distrital tenía solo 6 a 12 vértices (El Porvenir era prácticamente un hexágono). Fue reemplazada por la cartografía 2017 del equipo.

### 2.2 Manzanas y nivel de ingreso ✅ OFICIAL (Ate y SJL)

| | |
|---|---|
| **Archivo** | `ingresos_ate_sjl_consolidado.shp` (+ `.dbf`, `.shx`, `.prj`) |
| **Origen** | Estratificación oficial del **INEI**, limpiada por el equipo |
| **Contenido** | **22,318 manzanas**: SJL 14,379 y Ate 7,939 |
| **Columnas** | `IDMANZANA`, `UBIGEO`, `CODZONA`, `CODMZNA`, `ESTRATO`, `nivel_ingreso`, `distrito_fuente` |
| **Sistema de coordenadas** | WGS84 (EPSG:4326), igual que el resto |

**El `ESTRATO` mapea 1 a 1 con `nivel_ingreso`**, sin ambigüedad:

| ESTRATO | nivel_ingreso | Manzanas |
|---|---|---|
| 1 | Bajo | 15,292 |
| 2 | Medio bajo | 4,003 |
| 3 | Medio | 2,401 |
| 4 | Medio alto | 622 |
| 5 | Alto | **0** |

> ⚠️ **No hay ninguna manzana clasificada como "Alto"** en Ate ni en SJL. El tablero solo muestra en la leyenda los estratos presentes, para no sugerir categorías vacías. Es plausible dado el perfil de ambos distritos, pero conviene confirmarlo con quien preparó la base.

**El enlace con las zonas censales fue verificado y es perfecto:** las 248 zonas de Ate y SJL calzan al 100% por `UBIGEO` + `CODZONA`, sin huérfanos en ninguna dirección y sin ninguna manzana sin zona.

### 2.3 Manzanas de El Porvenir ⚠️ PROVISIONAL

El Porvenir **todavía no tiene estratificación del INEI**. Mientras llega:

- Sus manzanas se construyen con el **grafo vial de Overture Maps**: se toma la red de calles y se calculan las caras cerradas entre ellas (*polygonize*), y cada cara se recorta contra su zona censal.
- Su **nivel de ingreso aparece como "Sin dato"**, en gris, y el título del mapa lo indica explícitamente.

Cuando llegue la estratificación, se integra igual que Ate y SJL y estas manzanas provisionales se reemplazan.

### 2.4 Construcciones (Overture Maps) ⚠️ NO OFICIAL

| | |
|---|---|
| **Fuente** | **Overture Maps Foundation**, release `2026‑08‑19.0` |
| **Quién está detrás** | Microsoft, Meta, Amazon (AWS) y TomTom |
| **Cómo se construye** | OpenStreetMap + detección por IA sobre imágenes satelitales + Esri |
| **¿Es oficial?** | **No.** Dataset abierto de calidad industrial, sin carácter oficial en Perú |

Descargadas: Ate 255,826, SJL 401,527, El Porvenir 83,116. Se usan para contar construcciones dentro de cada manzana. Ver las precauciones de §3.3.

---

### 2.5 Cobertura de empadronamiento ✅ OFICIAL

**Archivo:** `01_Raw/Zonas Piloto.xlsx`, hoja `ZonaCensal`.

Trae, por **subzona censal**, los hogares registrados en el **Registro Integrado (RI)** y los que contó el **Censo INEI 2017**. La cobertura del tablero es:

```
cobertura = hogares en el RI / hogares del Censo INEI 2017
```

**Cómo se enlaza con el mapa.** El código `IDZONA` del Excel se descompone así:

```
13010200901  =  130102   009    01
                UBIGEO   ZONA   SUBZONA
```

El Excel llega a **409 subzonas** y el tablero dibuja a nivel **zona**, así que se **suman** las subzonas de cada zona (409 → 261). Sumar es exacto: son conteos de hogares, no porcentajes.

> **Por qué se agrega a zona y no a subzona.** Porque el esquema de subzonas del Excel **no es el de la cartografía censal**. Ver §2.6, que lo documenta en detalle. A nivel **zona**, en cambio, el cruce es perfecto: **90 de 90 zonas en Ate y 158 de 158 en SJL**, es decir el **100% de las manzanas** de ambos distritos.

**Verificación independiente 1: la población.** La población del Censo 2017 que trae este Excel coincide con la del `.gpkg` de zonas, que es otro archivo: **581,309 personas en Ate en ambos**, y 0.1% de diferencia en SJL.

**Verificación independiente 2: el cálculo ya existía.** El `.gpkg` de zonas trae una columna `ris_cobertura_h` con esta misma cobertura ya calculada. Comparada contra la que produce el tablero, en las **260 zonas** coincide con una diferencia máxima de **0.05 puntos porcentuales**, que es solo el redondeo a un decimal:

| Zona | Tablero | `ris_cobertura_h` |
|---|---|---|
| Ate 001 | 38.7% | 38.72549 |
| Ate 003 | 11.9% | 11.942517 |
| Ate 004 | 1.2% | 1.161563 |

Esto confirma dos cosas: que la fórmula es la correcta, y que **agregar a zona es la misma decisión** que ya se había tomado al construir el `.gpkg`.

---

### 2.6 El esquema de subzonas del Excel no es el del censo

Este punto costó entenderlo y conviene dejarlo escrito, porque la conclusión intuitiva es la equivocada.

El identificador oficial de manzana del INEI se arma así (confirmado con el diccionario de variables de la base DNCE):

```
IDMANZANA = UBIGEO(6) + CODZONA(3) + SUFZONA(2) + CODMZNA(3) + SUFMZNA(1)
                                     ↑
                          "Sufijo de zona" = la subzona
```

**El shapefile de ingresos reproduce fielmente la cartografía oficial.** Se verificó contra la *Base cartográfica a nivel de manzana 2017 - DNCE* (485,696 manzanas del país, publicada en septiembre de 2020): los valores de `SUFZONA` son **los mismos**. Lo mismo vale para `02_Cleaned/base_carto_intervencion.shp`, que son 27,645 manzanas = exactamente el recorte de la base DNCE a los tres distritos.

**El que difiere es el Excel.** Subdivide más que la cartografía censal, y a veces con otra numeración:

| Zona | Cartografía INEI 2017 | Excel |
|---|---|---|
| Ate 035 | `00` (una sola) | `01`, `02`, `03` |
| Ate 039 | `00` | `01`, `02`, `03`, `04` |
| SJL 012 | `00` | `01`, `02`, `03`, `04` |
| SJL 001 | `01`, `02` | `03` a `09` |

El caso de SJL 001 es el revelador: no es una subdivisión más fina de lo mismo, son **números distintos**. Es decir, esas subzonas se trazaron para el operativo y no salen del marco censal.

**Cuánto coincide.** En 227 de las 266 zonas los dos esquemas son idénticos:

| Distrito | Zonas que coinciden | Manzanas |
|---|---|---|
| Ate | 80 de 90 | 7,000 (78%) |
| San Juan de Lurigancho | 136 de 158 | 10,927 (67%) |
| El Porvenir | 11 de 18 | 945 (40%) |
| **Total** | **227 de 266** | **18,872 (68%)** |

**Qué haría falta para pintar a nivel subzona.** La cartografía de las subzonas del Excel, que **no está en el proyecto**: los tres archivos cartográficos disponibles son el mismo esquema DNCE. Habría que pedírsela a quien armó el Excel. Ver §10.

**Lo que no cubre:**

| Situación | Alcance | Cómo aparece |
|---|---|---|
| El Porvenir, zonas 003 a 007 | 5 de 18 zonas (985 manzanas) | **Gris, "Sin dato"**, y quedan fuera de los totales |
| Una subzona de SJL (`15013213605`) | 64 hogares de 248,742 (**0.03%**) | Llega sin denominador del censo; se descarta entera para que el numerador y el denominador sigan siendo el mismo conjunto |

**Dos problemas que no hay que confundir.** Se parecen pero no tienen nada que ver:

| | Qué es | Qué provoca hoy |
|---|---|---|
| **Filas ausentes** | El Excel no trae las zonas 003 a 007 de El Porvenir | **Las 985 manzanas grises.** Es el 44% del distrito |
| **Subzonas distintas** | El Excel subdivide distinto que el censo (§2.6) | **Nada.** Al agregar a zona, el cruce es del 100% |

Dicho de otro modo: el gris es por **ausencia de dato**, no por códigos incompatibles.

---

## 3. ¿Qué tan confiables son los datos?

### 3.1 Las manzanas del INEI mejoraron mucho la calidad ✅

Al reemplazar las manzanas construidas con Overture por las oficiales del INEI, el porcentaje de manzanas sin ninguna construcción detectada se desplomó:

| Distrito | Con manzanas Overture | Con manzanas INEI |
|---|---|---|
| Ate | 16.4% | **1.8%** |
| San Juan de Lurigancho | 22.9% | **1.8%** |
| El Porvenir | 3.0% | 2.8% *(sigue en Overture)* |

Es una validación cruzada fuerte: las manzanas del INEI coinciden con donde efectivamente hay construcciones, mientras que las derivadas de la red vial generaban caras vacías.

### 3.2 ⚠️ Cuatro zonas censales de SJL sin calles mapeadas

En San Juan de Lurigancho hay **4 zonas censales** (códigos 148, 165, 175 y 177, **2,442 habitantes**) donde Overture no tiene calles que formen manzanas cerradas, típico de asentamientos informales o expansión reciente.

Esto se detectó cuando las manzanas se construían con Overture, y se resolvió dibujando esas zonas **completas, como una sola unidad**, para que su población no desapareciera del mapa. **Con las manzanas del INEI el problema ya no aplica en SJL**, pero la salvaguarda sigue activa para El Porvenir.

### 3.3 ⚠️ Las "construcciones detectadas" no son hogares

> **Ya no afectan a la cobertura.** Hasta la versión anterior el denominador del mapa de cobertura eran estas construcciones. Ahora es el **conteo de hogares del Censo INEI 2017** (§2.5), que es un dato oficial. Las construcciones quedaron solo como dato informativo de cada manzana, así que lo que sigue importa mucho menos que antes.

Una construcción detectada es **un techo visto desde satélite**, no un hogar censado. Comparando contra la población real del INEI:

| Distrito | Construcciones | Población (INEI) | Personas por construcción |
|---|---|---|---|
| Ate | 108,931 | 581,309 | **5.34** |
| San Juan de Lurigancho | 215,655 | 980,619 | **4.55** |
| El Porvenir | 54,378 | 131,967 | **2.43** |

El promedio real en Perú urbano es de **~3.7 personas por hogar**. Las cifras de Lima quedan por encima (un techo alberga varias viviendas: edificio multifamiliar, quinta) y El Porvenir por debajo (casa baja de una familia).

> **Mejora respecto a la versión anterior:** con las manzanas construidas por Overture estos ratios eran 8.96 / 8.93 / 2.56, muy alejados de la realidad. Con las manzanas del INEI bajaron a 5.34 / 4.55 / 2.43, bastante más cerca del 3.7 esperado.

**Qué significa "no comparable":** el mismo número quiere decir cosas distintas según el tipo de vivienda. Entre Ate y SJL la diferencia es moderada (5.34 vs 4.55, un 17%), así que compararlos es razonable. Contra El Porvenir la brecha es de **2.2 veces**, y ahí la comparación engaña.

**Regla práctica:**

- ✅ Comparar manzanas o zonas **dentro de un mismo distrito**.
- ✅ Comparar **Ate contra San Juan de Lurigancho** (con cuidado, difieren 17%).
- ❌ Comparar cualquiera de ellos **contra El Porvenir**: usar la población del INEI.
- ❌ **Dimensionar equipos de campo**: usar los **hogares del Censo 2017** que ya trae el tablero (§2.5), no las construcciones.

### 3.4 ⚠️ Cómo leer una cobertura mayor al 100%

El numerador y el denominador **no son de la misma fecha**:

| | Qué es | Fecha |
|---|---|---|
| Numerador | Hogares en el Registro Integrado | **Actual** |
| Denominador | Hogares contados por el censo | **2017** |

Donde el distrito creció desde 2017, el RI registra más hogares de los que el censo llegó a contar, y la razón pasa del 100%. No es un error de cálculo ni de enlace: es **crecimiento urbano**.

| Distrito | Zonas sobre 100% | Máximo |
|---|---|---|
| Ate | 19 de 90 | 650.9% |
| San Juan de Lurigancho | 81 de 158 | 535.4% |
| El Porvenir | 11 de 13 | 178.9% |

**Qué hacer con eso:**

- ✅ **Priorizar por las zonas bajas.** Una zona al 12% es una zona donde falta trabajo, y ese dato es sólido.
- ⚠️ **No leer el porcentaje como "avance del operativo"** en las zonas sobre 100%: ahí el denominador quedó viejo, y lo único que se puede afirmar es que la zona ya está cubierta.
- ❌ **No promediar los porcentajes de las zonas.** Los totales del tablero se calculan sumando hogares y dividiendo una sola vez, que es lo correcto.

En el tablero, la última clase de color es **"≥ 100%"** (abierta hacia arriba) justamente para que una zona al 650% no aplaste la escala de todas las demás.

### 3.5 Resumen de confiabilidad

| Elemento | ¿Real? | ¿Oficial? | Confiabilidad |
|---|---|---|---|
| Zonas censales | Sí | **Sí, INEI 2017** | ✅ Alta |
| Manzanas de Ate y SJL | Sí | **Sí, INEI** | ✅ Alta |
| **Nivel de ingreso de Ate y SJL** | Sí | **Sí, INEI** | ✅ Alta |
| Población por zona | Sí | **Sí, INEI 2017** | ✅ Alta |
| Manzanas de El Porvenir | Sí | No | ⚠️ Provisional, hasta que llegue la estratificación |
| Nivel de ingreso de El Porvenir | No | No | ❌ **No disponible** ("Sin dato") |
| **Hogares por zona (Censo 2017)** | Sí | **Sí, INEI 2017** | ✅ Alta |
| **Cobertura (RI / Censo 2017)** | **Sí** | **Sí** | ✅ Alta, con la advertencia de §3.4 |
| Construcciones detectadas | Sí | No | ⚠️ **No son hogares** (§3.3), ya no se usan para la cobertura |
| Cobertura de El Porvenir | Parcial | Sí | ⚠️ 13 de 18 zonas; las otras 5 en gris |

---

## 4. Límites y decisiones tomadas

### 4.1 Límites vigentes

| Límite | Valor | Por qué | Dónde se cambia |
|---|---|---|---|
| Simplificación de contornos | **~2.2 m** | Reduce los vértices del shapefile del INEI al 24% sin cambio visible (un píxel son ~38 m al zoom de distrito) | `scripts/generar_manzanas.py` → `TOLERANCIA_SIMPLIFY` |
| Precisión de coordenadas | **5 decimales (~1 m)** | Reduce peso sin pérdida visible | `scripts/generar_manzanas.py` |
| Área mínima de manzana | **300 m²** | *Solo El Porvenir*: descarta astillas entre calles casi paralelas | `MIN_AREA_M2` |
| Área máxima de manzana | **200,000 m²** | *Solo El Porvenir*: descarta polígonos no urbanos | `MAX_AREA_M2` |
| Umbral de baja cobertura | **100%**, ajustable desde la barra | Marca toda zona que no cerró el empadronamiento | `app.py` → `UMBRAL_BAJA_COBERTURA` (valor inicial) |
| Cortes de cobertura (%) | **<50 · 50‑75 · 75‑90 · 90‑100 · ≥100** | Cortes fijos, no cuantiles: un porcentaje tiene significado absoluto y debe leerse contra el umbral. Se aprietan cerca de 100 porque ahí se decide el operativo, y la última clase queda **abierta** para que una zona al 650% no aplaste la escala (§3.4) | `app.py` → `CORTES_COBERTURA` |
| Zonas sin cobertura | **Se dibujan en gris** | No se asume cero: no saber no es lo mismo que no haber empadronado. Quedan fuera de todos los totales | `app.py` → `COLOR_SIN_COBERTURA` |

**No hay ningún límite en la cantidad de manzanas.** Se dibujan todas, sin muestreo. Las 22,318 manzanas del INEI se conservan íntegras.

### 4.2 ⚠️ Un límite que existió y ya fue eliminado

En una versión anterior, cuando el tablero dibujaba **casas individuales**, hubo un tope de **40,000 casas por distrito** por velocidad. Eso hacía que **se viera solo ~10% de las casas reales**:

| Paso (ejemplo de Ate) | Casas | Qué pasaba |
|---|---|---|
| Descargadas de Overture | 255,826 | La descarga pide un rectángulo |
| Realmente dentro de Ate | ~155,631 (61%) | El rectángulo incluye distritos vecinos |
| Tras el tope de 40,000 | 40,000 | ← **el recorte más grande** |
| En una manzana válida | 16,064 | Casas sobre avenidas o en manzanas descartadas |

**Ya no existe.** Se documenta porque es el tipo de recorte silencioso que puede llevar a una conclusión equivocada si nadie lo sabe.

### 4.3 Ya no queda nada sintético, salvo el ingreso de El Porvenir

La cobertura sintética **fue reemplazada por el dato oficial** de `01_Raw/Zonas Piloto.xlsx` (§2.5). El nivel de ingreso tampoco es sintético en Ate ni SJL.

Lo único pendiente es el **nivel de ingreso de El Porvenir**, que aparece como "Sin dato" a la espera de la estratificación del INEI.

**Una decisión importante al agregar:** los totales del distrito se calculan **sumando los hogares y dividiendo una sola vez**, no promediando los porcentajes de las zonas. Promediar daría más peso a una zona de 200 hogares que a una de 6,000. Las zonas sin dato quedan fuera del cálculo en vez de contar como cero.

---

## 5. Con qué está hecho

Todo es **Python** y todo el software es **gratuito y de código abierto**. No hay licencias que pagar.

| Herramienta | Para qué | Nota |
|---|---|---|
| **Python** | Lenguaje base | |
| **Streamlit** | Construye la página web | Evita programar una web desde cero |
| **pydeck / deck.gl** | Dibuja los mapas | Motor de Uber; usa la **tarjeta de video (GPU)** |
| **Polars** | Lee y filtra los datos | **Escrito en Rust** |
| **pyogrio** | Lee el shapefile del INEI | Lector rápido de formatos geográficos |
| **Shapely** | Cálculos geométricos | Solo fuera de línea |
| **SQLite** | Lee el GeoPackage del INEI | Un `.gpkg` es internamente una base SQLite |
| **Apache Parquet** | Formato de los datos | Columnar, muy rápido de leer |
| **CARTO basemap** | Mapa de fondo | Versión gratuita, sin cuenta |

### 5.1 Sobre las alternativas consideradas

- **"Una librería en Rust para Python"** → **ya se usa**: Polars está escrito en Rust.
- **"CPython"** → CPython **es** el Python estándar; ya se está ejecutando. No es una versión más rápida.
- **"mapgl"** → es de **R**, no de Python. Usa MapLibre GL JS, misma familia que deck.gl; no sería más rápido.
- **"CARTO"** → plataforma comercial de pago. **CARTO es co‑creador de deck.gl**, el motor que ya usamos gratis.

---

## 6. Cómo se logró que cargue rápido

El principio: **hacer el trabajo pesado una sola vez, por adelantado.**

### 6.1 Las siete decisiones clave

**1. Precalcular toda la geometría fuera de línea.** Leer el shapefile, enlazar con las zonas y contar construcciones toma ~60 segundos. Se corre **una sola vez** (`scripts/generar_manzanas.py`). El tablero nunca hace geometría mientras el usuario navega.

**2. Parquet + Polars.** Las 24,376 manzanas se cargan en **92 milisegundos**, y quedan en caché: se lee una sola vez por sesión.

**3. Dibujar con la GPU.** deck.gl envía los polígonos a la tarjeta de video. Folium o Leaflet dibujan cada polígono como elemento HTML y colapsan con miles de formas.

**4. Enviar solo las columnas que el mapa usa.** Se detectó midiendo: se pasaban las 14 columnas de la tabla cuando el mapa necesita 3 o 4. Corregirlo dio **4.6× de mejora**.

**5. Simplificar contornos y unificar el resaltado.** Dos ajustes:

- La simplificación de ~2.2 m redujo los vértices del shapefile del INEI **al 24%** (de 651,337 a 157,734), invisible a la vista.
- El resaltado de baja cobertura se dibujaba como **una segunda capa** con los polígonos de las zonas bajas. Con el umbral en 100% eso significaba **enviar casi toda la geometría dos veces**. Se corrigió.

**6. Repartir el resaltado en vez de repetirlo (nuevo).** El borde de resaltado viajaba como un color por manzana, y como solo tiene **dos valores posibles** eso costaba 19 bytes por manzana para transmitir un solo bit: **0.27 MB en SJL**. Ahora las manzanas se **reparten** en dos capas (normales y resaltadas), cada una con su borde constante. Nada se duplica: cada manzana sigue yendo una sola vez.

**7. Abreviar lo que se repite en cada manzana (nuevo).** El tooltip de cobertura es **el mismo para todas las manzanas de una zona**, pero deck.gl obliga a mandarlo en cada una. Se envía `"054"` en vez de `"Zona 054"` (la palabra va en la plantilla, que viaja una sola vez) y los números van **sin comillas ni separador de miles**. Entre esto y el punto 6, el mapa de ingreso bajó de **3.50 a 3.16 MB** en SJL pese a que ahora lleva más información.

### 6.2 Rendimiento actual (medido)

**Lectura de datos** (una sola vez por sesión, queda en caché):

| Paso | Tiempo |
|---|---|
| Leer `manzanas.parquet` (24,376 manzanas) | **22 ms** |
| Convertir los polígonos a listas de Python | **110 ms** |
| Convertir el resto de columnas | **6 ms** |
| **Total** | **~140 ms** |

**Trabajo por cambio de control** (filtrar el distrito y armar los atributos):

| Distrito | Manzanas | Cálculo en Python | Peso enviado al navegador |
|---|---|---|---|
| Ate | 7,939 | **11 ms** | 3.63 MB (1.75 ingreso + 1.88 cobertura) |
| San Juan de Lurigancho | 14,379 | **17 ms** | 6.53 MB (3.16 ingreso + 3.37 cobertura) |
| El Porvenir | 2,058 | **6 ms** | 0.81 MB (0.38 ingreso + 0.42 cobertura) |

San Juan de Lurigancho es el más pesado porque tiene 14,379 manzanas reales.

**La conclusión que importa:** el cálculo en Python son **11 a 17 milisegundos**. Todo lo demás es preparar y enviar los datos al navegador y dibujarlos. Por eso **reescribir el código en otro lenguaje no ayudaría**: no hay nada que acelerar del lado del cálculo. Lo que sí ayuda es mandar menos bytes, que es de lo que trata §6.1.

> Al cargar la cobertura real, el mapa de cobertura de SJL pasó de 3.23 a 3.37 MB (+4%) porque ahora lleva hogares del RI, hogares del censo y la brecha de cada zona. En paralelo, los puntos 6 y 7 de §6.1 bajaron el mapa de ingreso de 3.50 a 3.16 MB, así que **el total por distrito quedó por debajo del anterior** aun con más información en pantalla.

### 6.3 Si se necesita más velocidad

1. **Filtrar manzanas sin construcciones**: ahora solo 1.8%, así que el margen es pequeño.
2. **Vector tiles** (`tippecanoe` + `MVTLayer`): el navegador pediría solo lo visible. Es la solución definitiva, pero requiere una herramienta en C++ difícil de montar en Windows sin Docker.
3. **Envío binario** en vez de texto JSON.

---

## 7. Cómo cargar los datos que faltan

Reemplazar `data/manzanas.parquet` respetando estas columnas:

| Columna | Nivel | Descripción |
|---|---|---|
| `manzana_id` | Manzana | Identificador interno |
| `id_manzana_inei` | Manzana | `IDMANZANA` del INEI |
| `distrito` | Manzana | Nombre en mayúsculas |
| `poligono` | Manzana | Lista de coordenadas `[lon, lat]` |
| `nivel_ingreso` | Manzana | `Bajo`, `Medio bajo`, `Medio`, `Medio alto`, `Alto` o `Sin dato` |
| `n_hogares` | Manzana | Construcciones detectadas |
| `zona_key` / `codzona` / `zona_nombre` | Zona | Identificación de la zona censal |
| `cobertura_pct` | Zona | `hogares_ri / hogares_inei * 100`. **Vacío** si no hay dato |
| `hogares_inei` | Zona | Hogares del Censo INEI 2017 (denominador) |
| `hogares_ri` | Zona | Hogares en el Registro Integrado (numerador) |
| `brecha_hogares` | Zona | `hogares_inei - hogares_ri`. Positiva = faltan por registrar |
| `hogares_pobres` | Zona | Hogares pobres y pobres extremos del RI |

**Regla clave:** todas las manzanas de una misma zona deben tener **el mismo valor** en las columnas de zona. Así funciona el color compartido por zona.

**Para actualizar la cobertura** basta reemplazar `01_Raw/Zonas Piloto.xlsx` conservando la hoja `ZonaCensal` y sus columnas (`IDZONA`, `h_total`, `inei_h_total`, `h_pobre`, `h_pobre_ext`, `inei_p_total`) y volver a correr el generador. El `IDZONA` debe seguir siendo `UBIGEO(6) + ZONA(3) + SUBZONA(2)`.

Para regenerar todo desde las fuentes originales, correr `python scripts/generar_manzanas.py` (~2 min). Necesita `openpyxl` (ya está en `requirements.txt`).

**Qué revisar después de regenerar.** El generador imprime cuántas zonas quedaron con cobertura por distrito. Si aparece un número menor al esperado, es que el Excel trae zonas que la cartografía no tiene (o al revés) y hay que revisar los códigos antes de dar el dato por bueno.

---

## 8. Estructura del proyecto

```
GIZ/
├── app.py                              El tablero
├── DOCUMENTACION.md                    Este documento
├── requirements.txt                    Librerías necesarias
├── ingresos_ate_sjl_consolidado.shp    ← manzanas + ingreso del INEI (+ .dbf .shx .prj)
├── 01_Raw/
│   └── Zonas Piloto.xlsx               ← cobertura oficial (hogares RI vs Censo 2017)
├── Targeting Criteria/
│   └── zona_perfiles.gpkg              ← zonas censales INEI 2017
├── scripts/
│   ├── extract_distritos.py            (histórico) extraía distritos del archivo 2007
│   └── generar_manzanas.py             Arma la base que consume el tablero
└── data/
    ├── manzanas.parquet                ← lo que usa el tablero (1.2 MB)
    ├── zonas.parquet                   ← atributos INEI por zona
    ├── distritos.parquet               ← límites para el encuadre
    └── raw_buildings/                  Descargas de Overture (110 MB, no se versiona)
```

**Ejecutar:**

```powershell
streamlit run app.py
```

Abre `http://localhost:8501`. Para detenerlo: `Ctrl+C`.

---

## 9. Preguntas frecuentes

**¿Por qué varias manzanas comparten color en el mapa de cobertura?**
Porque la cobertura se mide **por zona censal**, no por manzana. Es intencional.

**¿Qué significa el contorno negro delgado?**
Marca las zonas por debajo del umbral de cobertura (100% por defecto, ajustable). Aparece en **ambos mapas**, para ver dónde coincide el bajo ingreso con la baja cobertura.

**¿El nivel de ingreso es real?**
**Sí, en Ate y San Juan de Lurigancho**: es la estratificación oficial del INEI. En El Porvenir aparece "Sin dato" porque su estratificación aún no llega.

**¿Por qué no aparece el nivel "Alto"?**
Porque **el INEI no clasificó ninguna manzana de Ate ni de SJL como "Alto"**. La leyenda solo muestra los estratos presentes.

**¿La cobertura es real?**
**Sí, y es oficial.** Sale de `01_Raw/Zonas Piloto.xlsx`: hogares del Registro Integrado sobre hogares del Censo INEI 2017, por zona censal (§2.5). El único dato sintético que queda es el nivel de ingreso de El Porvenir.

**¿Por qué hay zonas con más de 100% de cobertura?**
Porque el registro es actual y el censo es de 2017. Donde el distrito creció, hay más hogares registrados que censados. No es un error; ver §3.4 para cómo leerlo.

**¿Por qué El Porvenir tiene manzanas grises en el mapa de cobertura?**
Porque el Excel trae 13 de sus 18 zonas. Las 5 restantes salen en gris como "Sin dato" y no entran en los totales: no saber no es lo mismo que no haber empadronado.

**¿Se ven todas las manzanas?**
**Sí, todas, sin muestreo.**

**¿Cuánto cuesta mantener esto?**
Nada. Todo el software es libre y los datos son abiertos o propios.

---

## 10. Pendientes

| Prioridad | Tema | Acción |
|---|---|---|
| ✅ Hecho | ~~Datos reales de cobertura~~ | Cargados desde `01_Raw/Zonas Piloto.xlsx` (§2.5) |
| ✅ Hecho | ~~Denominador real de hogares por zona~~ | Era el mismo archivo: trae los hogares del Censo 2017 y los del RI por subzona censal. Ya es el denominador del mapa, y con eso §3.3 dejó de afectar a la cobertura |
| **Alta** | Estratificación del INEI para El Porvenir | Al llegar, se integra igual que Ate y SJL y reemplaza sus manzanas provisionales |
| **Alta** | Cobertura de las zonas 003 a 007 de El Porvenir | 5 de 18 zonas salen en gris porque el Excel no las trae. Son **1,038 manzanas, el 44% del distrito**. Confirmar si quedan fuera del piloto o si es un faltante del archivo (§11, pregunta 1) |
| Media | Cartografía de las subzonas del Excel | No está en el proyecto: los tres archivos cartográficos disponibles son el mismo esquema DNCE 2017 (§2.6). Con ella se podría pintar a nivel subzona en vez de zona |
| Media | Fecha de corte del RI | El denominador es el censo 2017, fijo. El numerador es el registro, y sin su fecha no se puede rotular "cobertura al mes X" (§11, pregunta 3) |
| Media | Denominador más actual que el censo 2017 | En 111 de 261 zonas el RI ya supera al censo (§3.4). Un padrón más reciente haría que el porcentaje vuelva a leerse como "avance" en todas las zonas |
| Media | Confirmar la ausencia del estrato "Alto" | Ninguna manzana de Ate ni SJL quedó en ese estrato (§2.2) |
| Baja | Variables INEI adicionales del `.gpkg` | Trae `perfil`, `media_pobreza`, `n_delitos_p1000`, `health`, `education` y otras. Podrían sumarse como capas o filtros |
| Baja | Mapa de pobreza | El Excel ya trae hogares pobres y pobres extremos por zona, y el generador los guarda en `hogares_pobres`. Falta solo decidir si se muestran |
| Baja | Población de El Porvenir en el `.gpkg` | Las zonas 003 a 007 comparten el mismo valor (6,097 cada una), lo que parece un relleno del archivo y no un dato real. No afecta a la cobertura, pero sí al total de población del distrito |

---

## 11. Preguntas para quien elaboró el Excel

`01_Raw/Zonas Piloto.xlsx` fue elaborado internamente. Estas son las preguntas que quedaron abiertas después de revisarlo, ordenadas por cuánto cambian el tablero.

**1. El Porvenir, zonas 003 a 007.** El Excel no trae ninguna fila para esas 5 zonas, así que hoy salen en gris. Son **1,038 manzanas, el 44% del distrito**. ¿Quedaron fuera del piloto a propósito, o falta agregarlas? Si están fuera, se deja el gris y se explica en la leyenda; si es un faltante, el mapa de El Porvenir cambia bastante.

**2. Las subzonas del Excel.** El `IDZONA` subdivide distinto que la cartografía censal del INEI. En Ate 035 la cartografía tiene una sola subzona (`00`) y el Excel tiene tres (`01`, `02`, `03`); en SJL 001 la cartografía tiene `01` y `02` y el Excel tiene de `03` a `09`, que son números distintos, no una subdivisión (§2.6).

- ¿Esas subzonas se trazaron para el operativo, o vienen de algún archivo?
- Si se trazaron, ¿existe el shapefile? Con él se podría pintar a nivel subzona en vez de zona.
- ¿Respetan los límites de las zonas censales? Si no, agregar a zona sigue siendo lo correcto aunque llegue la cartografía.

**3. Fecha de corte del RI.** El denominador es el censo 2017, que es fijo. El numerador es el registro, que se mueve. ¿A qué fecha está cortado? Sin eso el tablero solo puede decir "cobertura", no "cobertura al mes X".

**4. Una subzona sin denominador.** La subzona `15013213605` de SJL trae 64 hogares del RI pero llega vacía en `inei_h_total` e `inei_p_total`. Se descartó entera para que numerador y denominador fueran el mismo conjunto de subzonas. Son 64 hogares sobre 248,742 (**0.03%**), así que no cambia ninguna cifra, pero conviene confirmar si es un dato faltante o algo esperado.

**Lo que ya NO hace falta preguntar:** la fórmula de la cobertura. La columna `ris_cobertura_h` del `.gpkg` de zonas reproduce exactamente el mismo cálculo (§2.5), así que la definición está confirmada.
