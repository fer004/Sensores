import os
import pandas as pd
import requests
import geojson
from datetime import datetime

API_KEY = os.getenv("API_KEY_PURPLEAIR") 
CSV_FILE = 'sensores_detectados.csv'
SALIDA_GEOJSON = 'sensores.geojson'
CAMPOS = 'pm1.0,pm2.5'

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
            point = geojson.Point((fila['longitude'], fila['latitude']))
            features.append(geojson.Feature(geometry=point, properties=props))

    feature_collection = geojson.FeatureCollection(features)
    with open(SALIDA_GEOJSON, 'w', encoding='utf-8') as f:
        geojson.dump(feature_collection, f, indent=2)
    print(f"GeoJSON generado: {SALIDA_GEOJSON}")

if __name__ == '__main__':
    df = leer_csv(CSV_FILE)
    crear_geojson(df)
