import os
import pickle
import time
from datetime import timedelta, datetime
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
from app.engine import db
from sklearn.model_selection import GridSearchCV
from app.engine import db

initial_depth = float(db.fetch_one("SELECT setting_value FROM system_settings WHERE setting_name = 'initial_depth';")['setting_value'])

def cache_model(model, model_filename, last_trained_time):
    # Save the model and the last trained time to disk using pickle
    with open(model_filename, 'wb') as file:
        pickle.dump({'model': model, 'last_trained_time': last_trained_time}, file, protocol=pickle.HIGHEST_PROTOCOL)


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
        INNER JOIN waste_type ON waste_type.waste_type_id = bin_fill_levels.waste_type 
    """
    data = db.fetch(query)  # Fetch data from the database

    # Convert fetched data into a DataFrame
    df = pd.DataFrame(data, columns=['bin_id', 'bin_name', 'waste_type_name', 'timestamp', 'fill_level'])

    # Convert timestamp to datetime format and fill levels to numeric
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['fill_level'] = pd.to_numeric(df['fill_level'])

    # Feature engineering: create time-based features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['day_of_month'] = df['timestamp'].dt.day
    df['month'] = df['timestamp'].dt.month
    df['lag_1'] = df['fill_level'].shift(1).fillna(0)  # Adding a lag feature

    # Forecasting fill levels for the next 5 days and accuracy check
    forecast_results = []
    days_to_forecast = 5
    working_hours = [8, 10, 12, 14, 16] 

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
        X = bin_data[['hour', 'day_of_week', 'day_of_month', 'month', 'lag_1']]
        y = bin_data['fill_level']

        # Split the data into training and testing sets (80% train, 20% test)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # Cache handling with 24-hour retraining
        # Define a unique filename for the cached model
        model_filename = f'{cache_dir}/xgboost_model_bin_{bin_id}_waste_{waste_type}.pkl'

        # Try to load the cached model and its last trained time
        model_fit, last_trained_time = load_cached_model(model_filename)

        # If no cached model exists or it needs to be retrained (after 24 hours)
        if model_fit is None or (datetime.now() - last_trained_time).total_seconds() > 86400:
            # Hyperparameter tuning using GridSearchCV
            param_grid = {
                'n_estimators': [100, 200],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.1, 0.2]
            }
            model = XGBRegressor(objective='reg:squarederror')
            grid_search = GridSearchCV(model, param_grid, cv=3, scoring='neg_mean_squared_error')
            grid_search.fit(X_train, y_train)
            model_fit = grid_search.best_estimator_

            # Cache the trained model to disk, along with the current timestamp
            cache_model(model_fit, model_filename, datetime.now())

        # Evaluate the model accuracy on the test set
        y_pred = model_fit.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        mape = mean_absolute_percentage_error(y_test, y_pred)
        # Calculate and print accuracy score
        accuracy_score = 100 - mape * 100
        print(f"Accuracy Score: {accuracy_score:.2f}%")

        # Log the accuracy metrics
        print(f"Bin: {bin_name}, Waste Type: {waste_type}")
        print(f"MAE: {mae:.2f}, MSE: {mse:.2f}, MAPE: {mape:.2%}\n")

        # Forecast the next 5 days starting from the current date
        future_dates = []
        current_date = datetime.now()

        for day_offset in range(1, days_to_forecast + 1):
            for hour in working_hours:
                future_time = datetime.combine(
                    (current_date + timedelta(days=day_offset)).date(),
                    datetime.min.time()
                ) + timedelta(hours=hour)
                future_dates.append({
                    'timestamp': future_time,
                    'hour': future_time.hour,
                    'day_of_week': future_time.weekday(),
                    'day_of_month': future_time.day,
                    'month': future_time.month,
                    'lag_1': y.iloc[-1]  # Use the last observed fill level as lag
                })

        future_df = pd.DataFrame(future_dates)
        future_X = future_df[['hour', 'day_of_week', 'day_of_month', 'month', 'lag_1']]
        forecast_values = model_fit.predict(future_X)

        # Create a forecast for working hours
        bin_forecast = []
        for i, future in enumerate(future_dates):
            # Cap the predicted fill level between 0 and 100
            future_fill_level = min(max(forecast_values[i], 0), 100)
            
            measured_depth = future_fill_level
            measured_depth = float(measured_depth)

            filled_height = initial_depth - measured_depth

            percentage_full = (filled_height / initial_depth) * 100

            # Store the forecast result with the date and time
            bin_forecast.append({
                'datetime': future['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'date': future['timestamp'].strftime('%Y-%m-%d'),
                'time': future['timestamp'].strftime('%H:%M'),
                'predicted_level': float("{:.2f}".format(percentage_full))
            })

        # Append forecast results for this bin and waste type
        forecast_results.append({
            'bin_name': bin_name,
            'waste_type': waste_type,
            'forecast': bin_forecast
        })

    return forecast_results
