from datetime import timedelta
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
from app.engine import db

# Step 1: Query data from `bin_fill_levels`
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

# Step 3: Forecasting fill levels for the next 48 hours and accuracy check
forecast_results = []
accuracy_results = []

# Number of hours to forecast
hours_to_forecast = 48

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

    # Step 4: Forecast fill levels for the next 48 hours
    last_timestamp = bin_data['timestamp'].max()

    for hour in range(1, hours_to_forecast + 1):
        future_time = last_timestamp + timedelta(hours=hour)
        future_seconds = (future_time - bin_data['timestamp'].min()).total_seconds()

        # Predict fill level for the future time
        predicted_fill = model.predict(np.array([[future_seconds]]))[0]

        # Store the forecast results with forecast day and time
        forecast_results.append({
            'bin_name': bin_name,
            'waste_type': waste_type,
            'forecast_day': future_time.date(),
            'forecast_time': future_time.strftime('%H:%M:%S'),  # Add time in HH:MM:SS format
            'predicted_fill_level': min(predicted_fill, 100)  # Cap fill level at 100%
        })

    # Step 5: Accuracy Evaluation - Compare predictions with actual data (test set)
    actual_fill_levels = test_data['fill_level'].values
    predicted_fill_levels = model.predict(time_numeric[-hours_to_forecast:]).flatten()

    # Calculate MAE and RMSE
    mae = mean_absolute_error(actual_fill_levels, predicted_fill_levels)
    rmse = np.sqrt(mean_squared_error(actual_fill_levels, predicted_fill_levels))

    # Store accuracy results
    accuracy_results.append({
        'bin_name': bin_name,
        'waste_type': waste_type,
        'mae': mae,
        'rmse': rmse
    })

# Step 6: Display forecast results and accuracy metrics
forecast_df = pd.DataFrame(forecast_results)
accuracy_df = pd.DataFrame(accuracy_results)

print("Forecast Results:")
print(forecast_df)

print("\nAccuracy Results (MAE and RMSE):")
print(accuracy_df)
