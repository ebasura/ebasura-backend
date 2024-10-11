from datetime import timedelta
import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from app.engine import db


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

    # Group by each bin_id and waste_type_name to model fill levels independently
    for (bin_id, waste_type), bin_data in df.groupby(['bin_id', 'waste_type_name']):

        # Extract bin_name and waste_type_name
        bin_name = bin_data['bin_name'].iloc[0]

        # Sort by timestamp
        bin_data = bin_data.sort_values(by='timestamp')

        # Extract the time series data (fill_level over time)
        time_series_data = bin_data.set_index('timestamp')['fill_level']

        # Step 4: Fit a SARIMAX model on the time series data
        # Using SARIMAX with seasonal_order (p,d,q)(P,D,Q,s), where s is the seasonal period (24 for daily seasonality)
        model = SARIMAX(time_series_data, order=(1, 1, 1), seasonal_order=(1, 1, 1, 24))
        model_fit = model.fit(disp=False)

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
