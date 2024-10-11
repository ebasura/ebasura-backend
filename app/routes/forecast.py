import os
import pickle
import time
from datetime import timedelta, datetime
import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from app.engine import db

def cache_model(model, model_filename, last_trained_time):
    # Save the model and the last trained time to disk using pickle
    with open(model_filename, 'wb') as file:
        pickle.dump({'model': model, 'last_trained_time': last_trained_time}, file)


def load_cached_model(model_filename):
    # Load the model and last trained time from disk if it exists
    if os.path.exists(model_filename):
        with open(model_filename, 'rb') as file:
            cached_data = pickle.load(file)
            return cached_data['model'], cached_data['last_trained_time']
    return None, None


def two_day_school_hours():
    query = """
        SELECT bin_fill_levels.*, waste_bins.bin_name, waste_type.name AS waste_type_name 
        FROM bin_fill_levels 
        INNER JOIN waste_bins ON bin_fill_levels.bin_id = waste_bins.bin_id 
        INNER JOIN waste_type ON waste_type.waste_type_id = bin_fill_levels.waste_type;
    """
    data = db.fetch(query)  # Fetch data from the database

    # Step 2: Convert fetched data into a DataFrame
    df = pd.DataFrame(data, columns=['bin_id', 'bin_name', 'waste_type_name', 'timestamp', 'fill_level'])

    # Convert timestamp to datetime format and fill levels to numeric
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['fill_level'] = pd.to_numeric(df['fill_level'])

    # Step 3: Forecasting fill levels for the next 48 hours (8am to 4pm) and accuracy check
    forecast_results = []
    hours_to_forecast = 48
    working_hours = list(range(8, 17, 4))  # 8 AM to 4 PM (inclusive)

    # Directory to store cached models
    cache_dir = 'model_cache'
    os.makedirs(cache_dir, exist_ok=True)

    # Group by each bin_id and waste_type_name to model fill levels independently
    for (bin_id, waste_type), bin_data in df.groupby(['bin_id', 'waste_type_name']):

        # Extract bin_name and waste_type_name
        bin_name = bin_data['bin_name'].iloc[0]

        # Sort by timestamp
        bin_data = bin_data.sort_values(by='timestamp')

        # Extract the time series data (fill_level over time)
        time_series_data = bin_data.set_index('timestamp')['fill_level']

        # Step 4: Cache handling with 24-hour retraining
        # Define a unique filename for the cached model
        model_filename = f'{cache_dir}/sarimax_model_bin_{bin_id}_waste_{waste_type}.pkl'

        # Try to load the cached model and its last trained time
        model_fit, last_trained_time = load_cached_model(model_filename)

        # If no cached model exists or it needs to be retrained (after 24 hours)
        if model_fit is None or (datetime.now() - last_trained_time).total_seconds() > 86400:
            # Train the SARIMAX model
            model = SARIMAX(time_series_data, order=(1, 1, 1), seasonal_order=(1, 1, 1, 24))
            model_fit = model.fit(disp=False)

            # Cache the trained model to disk, along with the current timestamp
            cache_model(model_fit, model_filename, datetime.now())

        # Forecast the next 48 hours
        forecast = model_fit.get_forecast(steps=hours_to_forecast)
        forecast_values = forecast.predicted_mean

        # Step 5: Create a forecast for working hours (8 AM to 4 PM)
        last_timestamp = bin_data['timestamp'].max()
        bin_forecast = []

        for day in range(1, (hours_to_forecast // len(working_hours)) + 1):
            for hour in working_hours:
                future_time = last_timestamp + timedelta(days=day, hours=hour - last_timestamp.hour)

                # Get the forecast value for the corresponding time
                future_fill_level = forecast_values[
                    day * len(working_hours) - len(working_hours) + working_hours.index(hour)]

                # Cap the predicted fill level between 0 and 100
                future_fill_level = min(max(future_fill_level, 0), 100)

                # Store the forecast result with the date and time
                bin_forecast.append({
                    'date': future_time.strftime('%Y-%m-%d'),
                    'time': future_time.strftime('%I:%M %p'),  # Format to HH:MM AM/PM
                    'predicted_level': future_fill_level
                })

        # Append forecast results for this bin and waste type
        forecast_results.append({
            'bin_name': bin_name,
            'waste_type': waste_type,
            'forecast': bin_forecast
        })

    return forecast_results
