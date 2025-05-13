import os
import json
import pandas as pd
import numpy as np
import requests
import geojson
import shapefile
from shapely.geometry import shape, Point
from scipy.spatial import Delaunay
from datetime import datetime

# Parámetros
API_KEY = os.getenv("API_KEY_PURPLEAIR")
CSV_FILE = 'sensores_detectados.csv'
SALIDA_GEOJSON_SENSORES = 'sensores.geojson'
SALIDA_GEOJSON_COLONIAS = 'AQ.geojson'
ARCHIVO_SHP_COLONIAS = 'shp/2023_1_19_A.shp'
CAMPOS = 'pm1.0,pm2.5'

# ------------------ Funciones ------------------ #

def leer_csv(ruta):
    df = pd.read_csv(ruta)
    df = df.dropna(subset=['latitude', 'longitude', 'sensor_index'])
    df['sensor_index'] = df['sensor_index'].astype(int)
    return df

def consultar_sensor(sensor_index):
    url = f'https://api.purpleair.com/v1/sensors/{sensor_index}?fields={CAMPOS}'
    headers = {'X-API-Key': API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json().get("sensor", {})
        return data.get("pm1.0"), data.get("pm2.5")
    return None, None

def crear_geojson(df):
    features = []
    puntos = []
    valores = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    for _, fila in df.iterrows():
        pm1, pm25 = consultar_sensor(fila['sensor_index'])
        if pm1 is not None and pm25 is not None:
            props = {
                "sensor_index": fila['sensor_index'],
                "name": fila.get('name', ''),
                "pm1_0": pm1,
                "pm2_5": pm25,
                "timestamp": timestamp
            }
            coords = (fila['longitude'], fila['latitude'])
            point = geojson.Point(coords)
            features.append(geojson.Feature(geometry=point, properties=props))
            puntos.append(coords)
            valores.append(pm25)

    feature_collection = geojson.FeatureCollection(features)
    with open(SALIDA_GEOJSON_SENSORES, 'w', encoding='utf-8') as f:
        geojson.dump(feature_collection, f, indent=2)

    print(f"GeoJSON de sensores generado: {SALIDA_GEOJSON_SENSORES}")
    return np.array(puntos), np.array(valores)

def cargar_datos_colonias_shp(archivo_shp_colonias):
    sf = shapefile.Reader(archivo_shp_colonias, encoding='utf-8')
    colonias = []
    for shape_record in sf.iterShapeRecords():
        geometry = shape(shape_record.shape.__geo_interface__)
        nombre_colonia = shape_record.record[0]
        colonias.append({'nombre': nombre_colonia, 'geometry': geometry})
    return colonias

def interpolar_lineal(punto, triangulo_indices, puntos, valores):
    v0, v1, v2 = puntos[triangulo_indices]
    z0, z1, z2 = valores[triangulo_indices]
    delta1 = v1 - v0
    delta2 = v2 - v0
    delta_p = punto - v0
    try:
        A = np.array([delta1, delta2]).T
        w = np.linalg.solve(A, delta_p)
        b0 = 1 - w[0] - w[1]
        b1, b2 = w
        return b0 * z0 + b1 * z1 + b2 * z2
    except np.linalg.LinAlgError:
        return None

def clasificar_calidad_aire(pm25):
    if pm25 is None or np.isnan(pm25):
        return "Sin datos"
    elif pm25 <= 12.0:
        return "Bueno"
    elif pm25 <= 35.4:
        return "Moderado"
    elif pm25 <= 55.4:
        return "No saludable para grupos sensibles"
    elif pm25 <= 150.4:
        return "No saludable"
    elif pm25 <= 250.4:
        return "Muy insalubre"
    else:
        return "Peligroso"

# ------------------ Ejecución Principal ------------------ #

if __name__ == '__main__':
    # Paso 1: Leer CSV y generar puntos
    df_sensores = leer_csv(CSV_FILE)
    puntos_data, valores_puntos = crear_geojson(df_sensores)

    # Paso 2: Cargar colonias
    colonias_data = cargar_datos_colonias_shp(ARCHIVO_SHP_COLONIAS)

    # Paso 3: Triangulación e interpolación
    try:
        tri = Delaunay(puntos_data)
    except ValueError as e:
        print(f"Error en la triangulación de Delaunay: {e}")
        exit()

    for colonia in colonias_data:
        centroide = colonia['geometry'].centroid
        punto_centroide = np.array([centroide.x, centroide.y])
        simplex_index = tri.find_simplex(punto_centroide)
        if simplex_index != -1:
            triangulo_indices = tri.simplices[simplex_index]
            valor_interpolado = interpolar_lineal(punto_centroide, triangulo_indices, puntos_data, valores_puntos)
            colonia['valor_interpolado'] = valor_interpolado
        else:
            colonia['valor_interpolado'] = np.nan

    # Paso 4: Crear GeoJSON de salida
    geo_json_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for colonia in colonias_data:
        geom = colonia['geometry']
        if geom.type == 'Polygon':
            coordinates = [list(geom.exterior.coords)]
        elif geom.type == 'MultiPolygon':
            coordinates = [[list(p.exterior.coords)] for p in geom.geoms]
        else:
            print(f"Colonia omitida ({colonia['nombre']}) - tipo de geometría no soportado: {geom.type}")
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": geom.type,
                "coordinates": coordinates
            },
            "properties": {
                "nombre": colonia['nombre'],
                "valor_interpolado": colonia['valor_interpolado'],
                "AQ": clasificar_calidad_aire(colonia['valor_interpolado'])
            }
        }
        geo_json_data["features"].append(feature)

    with open(SALIDA_GEOJSON_COLONIAS, "w", encoding="utf-8") as f:
        json.dump(geo_json_data, f, ensure_ascii=False, indent=2)

    print(f"GeoJSON de colonias generado: {SALIDA_GEOJSON_COLONIAS}")
