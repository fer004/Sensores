import os
import pandas as pd
import requests
import json
from datetime import datetime

API_KEY = os.getenv("API_KEY_PURPLEAIR") 
CSV_FILE = 'sensores_detectados.csv'
OUTPUT_FILE = 'sensores_arcgis.json'

def leer_csv(ruta):
    df = pd.read_csv(ruta)
    df = df.dropna(subset=['latitude', 'longitude', 'sensor_index'])
    df['sensor_index'] = df['sensor_index'].astype(int)
    return df

def consultar_pm(sensor_id):
    url = f'https://api.purpleair.com/v1/sensors/{sensor_id}?fields=pm1.0,pm2.5'
    headers = {'X-API-Key': API_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json().get('sensor', {})
        return data.get('pm1.0'), data.get('pm2.5')
    return None, None

def generar_arcgis_json(df):
    timestamp = datetime.utcnow().isoformat() + 'Z'
    features = []

    for _, row in df.iterrows():
        pm1, pm25 = consultar_pm(row['sensor_index'])
        if pm1 is None or pm25 is None:
            continue

        feature = {
            "geometry": {
                "x": row['longitude'],
                "y": row['latitude']
            },
            "attributes": {
                "sensor_index": int(row['sensor_index']),
                "name": row.get('name', ''),
                "pm1_0": round(pm1, 2),
                "pm2_5": round(pm25, 2),
                "timestamp": timestamp
            }
        }
        features.append(feature)

    arcgis_json = {
        "geometryType": "esriGeometryPoint",
        "spatialReference": { "wkid": 4326 },
        "fields": [
            {"name": "sensor_index", "type": "esriFieldTypeInteger", "alias": "Sensor ID"},
            {"name": "name", "type": "esriFieldTypeString", "alias": "Nombre"},
            {"name": "pm1_0", "type": "esriFieldTypeDouble", "alias": "PM1.0"},
            {"name": "pm2_5", "type": "esriFieldTypeDouble", "alias": "PM2.5"},
            {"name": "timestamp", "type": "esriFieldTypeString", "alias": "Fecha"}
        ],
        "features": features
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(arcgis_json, f, ensure_ascii=False, indent=2)

    print(f"Archivo ArcGIS JSON guardado: {OUTPUT_FILE}")

if __name__ == '__main__':
    df = leer_csv(CSV_FILE)
    generar_arcgis_json(df)
