from datetime import timedelta, time
import json
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
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
    hours_to_forecast = 12
    working_hours = list(range(8, 17, 4))  # 8 AM to 4 PM (inclusive)

    # Group by each bin_id and waste_type_name to model fill levels independently
    for (bin_id, waste_type), bin_data in df.groupby(['bin_id', 'waste_type_name']):

        # Extract bin_name and waste_type_name
        bin_name = bin_data['bin_name'].iloc[0]

        # Sort by timestamp
        bin_data = bin_data.sort_values(by='timestamp')

        # Convert timestamps to numeric format (time in seconds)
        time_numeric = (bin_data['timestamp'] - bin_data['timestamp'].min()).dt.total_seconds().values.reshape(-1, 1)

        # Split data into training and testing sets (last 48 hours for testing)
        train_data = bin_data[:-hours_to_forecast]  # Use all but the last 48 hours for training
        test_data = bin_data[-hours_to_forecast:]   # Use the last 48 hours for testing

        # Fit linear regression model on training data
        model = LinearRegression()
        model.fit(time_numeric[:-hours_to_forecast], train_data['fill_level'])

        # Step 4: Forecast fill levels for the next 48 hours (only 8 AM to 4 PM)
        last_timestamp = bin_data['timestamp'].max()
        bin_forecast = []

        for day in range(1, (hours_to_forecast // len(working_hours)) + 1):
            for hour in working_hours:
                future_time = last_timestamp + timedelta(days=day, hours=hour - last_timestamp.hour)
                future_seconds = (future_time - bin_data['timestamp'].min()).total_seconds()

                # Predict fill level for the future time
                predicted_fill = model.predict(np.array([[future_seconds]]))[0]

                # Store the forecast results with forecast day and time
                bin_forecast.append({
                    'date': future_time.strftime('%Y-%m-%d'),
                    'time': future_time.strftime('%I:%M %p'),  # Format to HH:MM AM/PM
                    'predicted_level': min(predicted_fill, 100)  # Cap fill level at 100%
                })

            forecast_results.append({
            'bin_name': bin_name,
            'waste_type': waste_type,
            'forecast': bin_forecast
        })
        
    return forecast_results

