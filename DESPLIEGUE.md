# Cómo publicar el tablero

Tablero de priorización de zonas del Piloto de Aprendizaje. Proyecto SISFOH de
Innovations for Poverty Action con el Organismo de Focalización e Información
Social y la Cooperación Alemana al Desarrollo.

## Antes de publicar

El tablero contiene, por zona censal identificada, la alerta de criminalidad
derivada del Sistema de Denuncias Policiales y el estrato de ingresos del
Instituto Nacional de Estadística e Informática. Son agregados sin datos de
personas, de clasificación Internal, y **Internal no se publica en abierto**.

Un mapa público que señale zonas concretas como de riesgo de seguridad puede
estigmatizar barrios. Antes de alojarlo fuera de IPA conviene confirmar con
support@poverty-action.org y acordarlo con el OFIS y la GIZ.

Las tres rutas de abajo suponen acceso restringido, no publicación abierta.

## Diferencia con Shiny

En Shiny, `rsconnect::deployApp()` sube la carpeta directamente desde RStudio a
shinyapps.io. En Streamlit no existe ese comando: **todos los servicios
gestionados despliegan desde un repositorio de Git**. La única excepción es
Posit Connect, el servidor que se instala en la organización, donde
`rsconnect-python` sí publica directo desde la carpeta.

La consecuencia práctica es que hay un paso previo, subir el proyecto a GitHub,
que en Shiny no existía. Se hace una sola vez.

## Qué se sube

```
app.py                    el tablero
requirements.txt          dependencias mínimas
.streamlit/config.toml    tema claro y colores de IPA
data/*.parquet            1.9 MB, entra sin problema en Git
```

No se suben `requirements-dev.txt` ni `scripts/`, salvo que se quiera dejar
constancia de cómo se generaron los datos. `data/raw_buildings/` está excluido
en `.gitignore` por peso y no hace falta para usar el tablero.

## Ruta 1. Streamlit Community Cloud, app privada

Es gratis y es la más rápida. La cuenta gratuita permite **una app privada** y
públicas ilimitadas. Privada significa que solo las cuentas de correo invitadas
pueden abrirla, que es lo que corresponde para IPA, OFIS y GIZ.

1. Crear un repositorio en GitHub, privado, y subir los archivos de arriba.
2. Entrar a share.streamlit.io con la cuenta de GitHub.
3. Elegir el repositorio, la rama y `app.py` como archivo principal.
4. En la configuración de la app, marcarla como privada e invitar los correos.

Los datos quedan alojados en GitHub y en la nube de Streamlit, o sea dos
proveedores externos. Es lo que hay que consultar con el área de sistemas antes
de hacerlo.

## Ruta 2. Posit Connect, si IPA ya lo tiene

Si la organización cuenta con un servidor Posit Connect, esta es la mejor
opción: los datos no salen del control de IPA, el control de acceso por usuario
y grupo ya existe, y la publicación es directa desde la carpeta, sin GitHub.

```
pip install rsconnect-python
rsconnect add --server https://<servidor-de-ipa> --name ipa --api-key <clave>
rsconnect deploy streamlit --name ipa .
```

Vale la pena preguntarle a sistemas si existe, porque el equipo ya publica
Shiny y puede que el servidor esté disponible.

Cuidado con Posit **Connect Cloud**, que es un producto distinto: en el plan
gratuito solo publica contenido público desde repositorios públicos de GitHub.
El acceso privado por correo requiere el plan Advanced, de organización.

## Ruta 3. Sin publicar

Comprimir la carpeta y repartirla. Quien la reciba instala las dependencias una
vez y corre el tablero:

```
pip install -r requirements.txt
streamlit run app.py
```

No expone datos a terceros y sirve para el equipo y para reuniones donde se
comparte pantalla. El costo es que cada persona necesita Python instalado.

## Nota sobre el entorno

Instalar con `pip` sobre la instalación base de Anaconda puede dejar `numpy` y
`pyarrow` desalineados, y el tablero falla con
`ImportError: numpy.core.multiarray failed to import`. Para evitarlo, conviene
un entorno propio:

```
conda create -n tablero python=3.11 -y
conda activate tablero
pip install -r requirements.txt
```

## Actualizar los datos

El tablero lee `data/zonas_ofis_dashboard.parquet`, que produce el script
`3_zonas_subzonas` en R. Para actualizar el tablero basta reemplazar ese archivo
y, si está desplegado desde Git, hacer commit del reemplazo. El tablero detecta
el archivo nuevo por su fecha y tamaño, sin reiniciar ni limpiar nada.
