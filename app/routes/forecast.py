import os
import pickle
from datetime import timedelta, datetime
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
from app.engine import db
import logging

logging.basicConfig(level=logging.INFO)

initial_depth = float(db.fetch_one("SELECT setting_value FROM system_settings WHERE setting_name = 'initial_depth';")['setting_value'])

def cache_model(model, model_filename, last_trained_time):
    with open(model_filename, 'wb') as file:
        pickle.dump({'model': model, 'last_trained_time': last_trained_time}, file, protocol=pickle.HIGHEST_PROTOCOL)

def load_cached_model(model_filename):
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

    df = pd.DataFrame(data, columns=['bin_id', 'bin_name', 'waste_type_name', 'timestamp', 'fill_level'])
    
    if df.empty:
        logging.warning("The fetched data is empty. Please check the database query.")
        return []

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['fill_level'] = pd.to_numeric(df['fill_level'])

    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['day_of_month'] = df['timestamp'].dt.day
    df['month'] = df['timestamp'].dt.month
    df['lag_1'] = df['fill_level'].shift(1).fillna(0)  

    forecast_results = []
    days_to_forecast = 5
    working_hours = [8, 10, 12, 14, 16]

    cache_dir = 'model_cache'
    os.makedirs(cache_dir, exist_ok=True)

    for (bin_id, waste_type), bin_data in df.groupby(['bin_id', 'waste_type_name']):
        bin_name = bin_data['bin_name'].iloc[0]

        bin_data = bin_data.sort_values(by='timestamp')

        X = bin_data[['hour', 'day_of_week', 'day_of_month', 'month', 'lag_1']]
        y = bin_data['fill_level']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        model_filename = f'{cache_dir}/xgboost_model_bin_{bin_id}_waste_{waste_type}.pkl'

        model_fit, last_trained_time = load_cached_model(model_filename)

        if model_fit is None or (datetime.now() - last_trained_time).total_seconds() > 86400:
            param_grid = {
                'n_estimators': [100, 200],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.1, 0.2]
            }
            model = XGBRegressor(objective='reg:squarederror')
            grid_search = GridSearchCV(model, param_grid, cv=3, scoring='neg_mean_squared_error')
            grid_search.fit(X_train, y_train)
            model_fit = grid_search.best_estimator_

            cache_model(model_fit, model_filename, datetime.now())

        y_pred = model_fit.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        mape = mean_absolute_percentage_error(y_test, y_pred)
        accuracy_score = 100 - mape * 100
        logging.info(f"Accuracy Score: {accuracy_score:.2f}%")

        logging.info(f"Bin: {bin_name}, Waste Type: {waste_type}")
        logging.info(f"MAE: {mae:.2f}, MSE: {mse:.2f}, MAPE: {mape:.2%}\n")

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
                    'lag_1': y.iloc[-1]  
                })

        future_df = pd.DataFrame(future_dates)
        future_X = future_df[['hour', 'day_of_week', 'day_of_month', 'month', 'lag_1']]
        forecast_values = model_fit.predict(future_X)

        bin_forecast = []
        for i, future in enumerate(future_dates):
            future_fill_level = min(max(forecast_values[i], 0), 100)

            measured_depth = future_fill_level
            measured_depth = float(measured_depth)

            filled_height = initial_depth - measured_depth
            percentage_full = (filled_height / initial_depth) * 100

            bin_forecast.append({
                'datetime': future['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'date': future['timestamp'].strftime('%Y-%m-%d'),
                'time': future['timestamp'].strftime('%H:%M'),
                'predicted_level': float("{:.2f}".format(percentage_full))
            })

        forecast_results.append({
            'bin_name': bin_name,
            'waste_type': waste_type,
            'forecast': bin_forecast
        })

    return forecast_results
