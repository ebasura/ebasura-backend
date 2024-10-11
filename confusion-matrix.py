import os
import pickle
import time
from datetime import timedelta, datetime
import pandas as pd
import numpy as np
from app.engine import db
from prophet import Prophet
from sklearn.ensemble import RandomForestRegressor
import xgboost as xgb


# Caching Functions
def cache_model(model, model_filename, last_trained_time):
    with open(model_filename, 'wb') as file:
        pickle.dump({'model': model, 'last_trained_time': last_trained_time}, file)


def load_cached_model(model_filename):
    if os.path.exists(model_filename):
        with open(model_filename, 'rb') as file:
            cached_data = pickle.load(file)
            return cached_data['model'], cached_data['last_trained_time']
    return None, None


# SQL Data Fetching and Forecasting Function
def two_day_school_hours(algorithm="prophet"):
    query = """
        SELECT bin_fill_levels.*, waste_bins.bin_name, waste_type.name AS waste_type_name 
        FROM bin_fill_levels 
        INNER JOIN waste_bins ON bin_fill_levels.bin_id = waste_bins.bin_id 
        INNER JOIN waste_type ON waste_type.waste_type_id = bin_fill_levels.waste_type;
    """
    data = db.fetch(query)  # Fetch data from the database

    # Convert fetched data into a DataFrame
    df = pd.DataFrame(data, columns=['bin_id', 'bin_name', 'waste_type_name', 'timestamp', 'fill_level'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['fill_level'] = pd.to_numeric(df['fill_level'])

    forecast_results = []
    hours_to_forecast = 48
    working_hours = list(range(8, 17, 4))  # 8 AM to 4 PM

    cache_dir = 'model_cache'
    os.makedirs(cache_dir, exist_ok=True)

    for (bin_id, waste_type), bin_data in df.groupby(['bin_id', 'waste_type_name']):
        bin_name = bin_data['bin_name'].iloc[0]
        bin_data = bin_data.sort_values(by='timestamp')
        time_series_data = bin_data.set_index('timestamp')['fill_level']

        model_filename = f'{cache_dir}/model_bin_{bin_id}_waste_{waste_type}.pkl'
        model_fit, last_trained_time = load_cached_model(model_filename)

        # If no cached model exists or the model needs to be retrained, train the model and generate forecast values
        if model_fit is None or (datetime.now() - last_trained_time).total_seconds() > 86400:

            if algorithm == "prophet":
                forecast_values = train_prophet_model(bin_data)  # Prophet forecast values
            elif algorithm == "random_forest":
                forecast_values = train_random_forest(bin_data)  # Random Forest forecast values
            elif algorithm == "xgboost":
                forecast_values = train_xgboost(bin_data)  # XGBoost forecast values

            # Cache the trained model and forecast data for future use
            cache_model(model_fit, model_filename, datetime.now())

        else:
            forecast_values = model_fit  # Prophet, Random Forest, and XGBoost forecast values

        last_timestamp = bin_data['timestamp'].max()
        bin_forecast = []

        for day in range(1, (hours_to_forecast // len(working_hours)) + 1):
            for hour in working_hours:
                future_time = last_timestamp + timedelta(days=day, hours=hour - last_timestamp.hour)

                # Fetch forecast values according to the algorithm in use
                future_fill_level = forecast_values[
                    day * len(working_hours) - len(working_hours) + working_hours.index(hour)]

                # Cap the predicted fill level between 0 and 100
                future_fill_level = min(max(future_fill_level, 0), 100)

                bin_forecast.append({
                    'date': future_time.strftime('%Y-%m-%d'),
                    'time': future_time.strftime('%I:%M %p'),
                    'predicted_level': future_fill_level
                })

        forecast_results.append({
            'bin_name': bin_name,
            'waste_type': waste_type,
            'forecast': bin_forecast
        })

    return forecast_results


# Prophet Model
def train_prophet_model(bin_data):
    prophet_data = bin_data.reset_index()[['timestamp', 'fill_level']]
    prophet_data.columns = ['ds', 'y']
    model = Prophet()
    model.fit(prophet_data)
    future_dates = model.make_future_dataframe(periods=48, freq='H')
    forecast = model.predict(future_dates)
    return forecast['yhat'].tail(48).values.flatten()


# Random Forest Model
def train_random_forest(bin_data):
    bin_data['hour'] = bin_data['timestamp'].dt.hour
    bin_data['dayofweek'] = bin_data['timestamp'].dt.dayofweek
    bin_data['day'] = bin_data['timestamp'].dt.day
    bin_data['month'] = bin_data['timestamp'].dt.month

    X = bin_data[['hour', 'dayofweek', 'day', 'month']]
    y = bin_data['fill_level']
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    future_dates = pd.date_range(start=bin_data['timestamp'].max(), periods=48, freq='h')
    future_df = pd.DataFrame({
        'hour': future_dates.hour,
        'dayofweek': future_dates.dayofweek,
        'day': future_dates.day,
        'month': future_dates.month
    })

    forecast_values = model.predict(future_df)
    return forecast_values


# XGBoost Model
def train_xgboost(bin_data):
    bin_data['hour'] = bin_data['timestamp'].dt.hour
    bin_data['dayofweek'] = bin_data['timestamp'].dt.dayofweek
    bin_data['day'] = bin_data['timestamp'].dt.day
    bin_data['month'] = bin_data['timestamp'].dt.month

    X = bin_data[['hour', 'dayofweek', 'day', 'month']]
    y = bin_data['fill_level']
    model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
    model.fit(X, y)

    future_dates = pd.date_range(start=bin_data['timestamp'].max(), periods=48, freq='h')
    future_df = pd.DataFrame({
        'hour': future_dates.hour,
        'dayofweek': future_dates.dayofweek,
        'day': future_dates.day,
        'month': future_dates.month
    })

    forecast_values = model.predict(future_df)
    return forecast_values


# Test Prophet Algorithm
results_prophet = two_day_school_hours(algorithm="prophet")

# Test Random Forest Algorithm
results_rf = two_day_school_hours(algorithm="random_forest")

# Test XGBoost Algorithm
results_xgboost = two_day_school_hours(algorithm="xgboost")

# Print Prophet Results
print("Prophet Results:")
print(results_prophet)

# Print Random Forest Results
print("Random Forest Results:")

print(results_rf)

# Print XGBoost Results
print("XGBoost Results ")
print(results_xgboost)
