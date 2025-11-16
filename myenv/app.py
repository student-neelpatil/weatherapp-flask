import requests
from flask import Flask, render_template, request
from datetime import datetime

app = Flask(__name__)

# --- Helper Functions for Open-Meteo ---

def format_time(timestamp, timezone_offset=0):
    """Converts a Unix timestamp to a human-readable time (e.g., '06:30 AM')"""
    try:
        # Open-Meteo daily data gives timestamps in YYYY-MM-DD string format
        # We need to parse them first if they are not integers
        if isinstance(timestamp, str):
            # Example: "2024-05-01T06:30"
            dt_obj = datetime.fromisoformat(timestamp)
        else:
            # Handle integer timestamps (if any)
            dt_obj = datetime.fromtimestamp(timestamp + timezone_offset)
        
        return dt_obj.strftime('%I:%M %p')
    except Exception as e:
        print(f"Error formatting time: {e}")
        return "-"

def get_weather_description_and_icon(code):
    """
    Translates Open-Meteo WMO weather code into a description and
    a compatible OpenWeatherMap icon code (e.g., '01d', '10n').
    """
    # WMO Code descriptions and icon mappings
    # This is a simplified mapping.
    mapping = {
        0: ("Clear sky", "01d"),
        1: ("Mainly clear", "01d"),
        2: ("Partly cloudy", "02d"),
        3: ("Overcast", "04d"),
        45: ("Fog", "50d"),
        48: ("Depositing rime fog", "50d"),
        51: ("Drizzle: Light", "09d"),
        53: ("Drizzle: Moderate", "09d"),
        55: ("Drizzle: Dense", "09d"),
        61: ("Rain: Slight", "10d"),
        63: ("Rain: Moderate", "10d"),
        65: ("Rain: Heavy", "10d"),
        80: ("Rain showers: Slight", "09d"),
        81: ("Rain showers: Moderate", "09d"),
        82: ("Rain showers: Violent", "09d"),
        71: ("Snow fall: Slight", "13d"),
        73: ("Snow fall: Moderate", "13d"),
        75: ("Snow fall: Heavy", "13d"),
        95: ("Thunderstorm", "11d"),
    }
    # Default to "Clear" if code not found
    description, icon = mapping.get(code, ("Clear sky", "01d"))
    
    # Simple day/night logic (Open-Meteo doesn't provide this in current API)
    # We'll assume 'd' (day) for all icons for simplicity
    
    return description.capitalize(), icon

# --- Main Application Route ---

@app.route('/', methods=['GET', 'POST'])
def index():
    weather_data = None
    forecast_list = None
    error_message = None

    if request.method == 'POST':
        city = request.form['city']
        
        try:
            # --- Step 1: Geocoding (City -> Lat/Lon) ---
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
            geo_response = requests.get(geo_url)
            geo_response.raise_for_status()
            geo_data = geo_response.json()

            if not geo_data.get('results'):
                error_message = f"City not found: '{city}'. Please check the spelling."
            else:
                lat = geo_data['results'][0]['latitude']
                lon = geo_data['results'][0]['longitude']
                # Use the name from the geocoding API for proper capitalization
                display_city_name = f"{geo_data['results'][0]['name']}, {geo_data['results'][0].get('country_code', '')}"

                # --- Step 2: Get All Weather Data from Open-Meteo ---
                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast"
                    f"?latitude={lat}&longitude={lon}"
                    f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,pressure_msl,wind_speed_10m,weather_code"
                    f"&daily=weather_code,temperature_2m_max,sunrise,sunset,uv_index_max"
                    f"&timezone=auto" # Automatically get the local timezone
                )
                weather_response = requests.get(weather_url)
                weather_response.raise_for_status()
                data = weather_response.json()

                # --- Step 3: Parse Current Weather ---
                current = data['current']
                description, icon = get_weather_description_and_icon(current['weather_code'])
                
                weather_data = {
                    'city': display_city_name,
                    'temperature': f"{current['temperature_2m']:.0f}",
                    'feels_like': f"{current['apparent_temperature']:.0f}",
                    'description': description,
                    'wind': f"{current['wind_speed_10m']:.1f}", # Open-Meteo gives km/h, convert to m/s
                    'humidity': current['relative_humidity_2m'],
                    'pressure': f"{current['pressure_msl']:.0f}",
                    'uvi': f"{data['daily']['uv_index_max'][0]:.1f}", # Get today's UVI from daily
                    'sunrise': format_time(data['daily']['sunrise'][0]), # Get today's sunrise
                    'sunset': format_time(data['daily']['sunset'][0]),   # Get today's sunset
                }

                # --- Step 4: Parse 5-Day Forecast ---
                forecast_list = []
                daily_data = data['daily']
                
                # Loop from index 1 to 5 (to get the *next* 5 days)
                for i in range(1, 6):
                    desc, icon = get_weather_description_and_icon(daily_data['weather_code'][i])
                    forecast_list.append({
                        'day': datetime.fromisoformat(daily_data['time'][i]).strftime('%a'), # 'Mon'
                        'icon': icon,
                        'temp': f"{daily_data['temperature_2m_max'][i]:.0f}",
                        'desc': desc
                    })

        except requests.exceptions.HTTPError as errh:
            error_message = f"An API error occurred: {errh.response.status_code}"
        except requests.exceptions.RequestException as err:
            error_message = f"A network error occurred: {err}"
        except (KeyError, IndexError) as err:
            error_message = f"Error parsing weather data. Missing data: {err}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"

    # IMPORTANT: Changed this from 'homepage.html' to 'index.html'
    # to match the file you provided.
    return render_template('homepage.html', 
                           weather=weather_data, 
                           forecast=forecast_list, 
                           error=error_message)

if __name__ == '__main__':
    app.run(debug=True)