import pandas as pd
import requests
import json
from datetime import datetime

API_KEY = os.getenv("API_KEY_PURPLEAIR") 
CSV_FILE = 'sensores_detectados.csv'
OUTPUT_FILE = 'sensores.geojson'

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

def crear_geojson(df):
    features = []
    timestamp = datetime.utcnow().isoformat() + 'Z'

    for _, row in df.iterrows():
        pm1, pm25 = consultar_pm(row['sensor_index'])
        if pm1 is None or pm25 is None:
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitude'], row['latitude']]
            },
            "properties": {
                "sensor_index": int(row['sensor_index']),
                "name": row.get('name', ''),
                "pm1_0": round(pm1, 2),
                "pm2_5": round(pm25, 2),
                "timestamp": timestamp
            }
        }
        features.append(feature)

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)

    print(f"Archivo GeoJSON guardado: {OUTPUT_FILE}")

if __name__ == '__main__':
    df = leer_csv(CSV_FILE)
    crear_geojson(df)
