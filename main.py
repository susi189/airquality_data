import httpx
import json

url_pollutants = "https://luftdaten.umweltbundesamt.de/api/air-data/v3/components/json"
url_stations = "https://luftdaten.umweltbundesamt.de/api/air-data/v3/stations/json"

def main(url):
    try
        response = httpx.get(url)
        print(response.json())
    except httpx.RequestError as e:
        print(f"An error occurred while making the request: {e}")



if __name__ == "__main__":
    main(url_pollutants)
    