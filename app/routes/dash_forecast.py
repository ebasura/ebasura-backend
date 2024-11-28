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
import plotly.graph_objects as go
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import logging

logging.basicConfig(level=logging.INFO)

# Fetch the initial depth setting from the database
initial_depth = float(db.fetch_one("SELECT setting_value FROM system_settings WHERE setting_name = 'initial_depth';")['setting_value'])

# Cache management functions
def cache_model(model, model_filename, last_trained_time):
    with open(model_filename, 'wb') as file:
        pickle.dump({'model': model, 'last_trained_time': last_trained_time}, file, protocol=pickle.HIGHEST_PROTOCOL)

def load_cached_model(model_filename):
    if os.path.exists(model_filename):
        with open(model_filename, 'rb') as file:
            cached_data = pickle.load(file)
            return cached_data['model'], cached_data['last_trained_time']
    return None, None

# Data fetching and feature engineering
def two_day_school_hours():
    query = """
        SELECT bin_fill_levels.*, waste_bins.bin_name, waste_type.name AS waste_type_name 
        FROM bin_fill_levels 
        INNER JOIN waste_bins ON bin_fill_levels.bin_id = waste_bins.bin_id 
        INNER JOIN waste_type ON waste_type.waste_type_id = bin_fill_levels.waste_type 
    """
    try:
        data = db.fetch(query) 
    except Exception as e:
        logging.error(f"Error fetching data from database: {e}")
        return {}

    df = pd.DataFrame(data, columns=['bin_id', 'bin_name', 'waste_type_name', 'timestamp', 'fill_level'])

    if df.empty:
        logging.warning("The fetched data is empty. Please check the database query.")
        return {}

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['fill_level'] = pd.to_numeric(df['fill_level'], errors='coerce')
    df.dropna(subset=['timestamp', 'fill_level'], inplace=True)

    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['day_of_month'] = df['timestamp'].dt.day
    df['month'] = df['timestamp'].dt.month
    df['lag_1'] = df['fill_level'].shift(1).fillna(0)

    forecast_results = {}
    days_to_forecast = 5
    all_hours = list(range(24))  # Forecast for all hours of the day (0 to 23)

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
            try:
                grid_search.fit(X_train, y_train)
                model_fit = grid_search.best_estimator_
                cache_model(model_fit, model_filename, datetime.now())
            except Exception as e:
                logging.error(f"Error during model training: {e}")
                continue

        try:
            y_pred = model_fit.predict(X_test)

            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            mape = mean_absolute_percentage_error(y_test, y_pred)
            accuracy_score = 100 - mape * 100
            logging.info(f"Accuracy Score for Bin {bin_name}, Waste Type {waste_type}: {accuracy_score:.2f}%")

        except Exception as e:
            logging.error(f"Error during model evaluation: {e}")
            continue

        future_dates = []
        current_date = datetime.now()

        for day_offset in range(1, days_to_forecast + 1):
            for hour in all_hours:  # Predict for every hour (0 to 23)
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

        try:
            forecast_values = model_fit.predict(future_X)
        except Exception as e:
            logging.error(f"Error during forecasting: {e}")
            continue

        bin_forecast = []
        for i, future in enumerate(future_dates):
            future_fill_level = min(max(forecast_values[i], 0), 100)
            filled_height = initial_depth - future_fill_level
            percentage_full = (filled_height / initial_depth) * 100

            bin_forecast.append({
                'datetime': future['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'date': future['timestamp'].strftime('%Y-%m-%d'),
                'time': future['timestamp'].strftime('%H:%M'),
                'predicted_level': float("{:.2f}".format(percentage_full))
            })

        if bin_id not in forecast_results:
            forecast_results[bin_id] = {
                'bin_name': bin_name,
                'waste_types': {}
            }

        forecast_results[bin_id]['waste_types'][waste_type] = bin_forecast

    return forecast_results


def create_dash_forecast(server, pathname): 
    forecast_results = two_day_school_hours()

    app = dash.Dash(__name__, server=server, url_base_pathname=pathname)

    app.layout = html.Div([
        dcc.Dropdown(
            id='bin-selector',
            options=[{'label': res['bin_name'], 'value': bin_id} for bin_id, res in forecast_results.items()],
            value=list(forecast_results.keys())[0] if forecast_results else None,
            placeholder="Select a Bin to View Forecast",
        ),
        dcc.Interval(
            id='interval-component',
            interval=24*60*60*1000,
            n_intervals=0
        ),
        dcc.Graph(id='forecast-graph'),
        dcc.Checklist(
            id='force-update',
            options=[{'label': 'Force Update Model', 'value': 'update'}],
            value=[],
            style={'margin': '20px'}
        ),
        html.Div(id='debug-output') 
    ])

    @app.callback(
        [Output('forecast-graph', 'figure'),
         Output('debug-output', 'children')],
        [Input('bin-selector', 'value'),
         Input('interval-component', 'n_intervals'),
         Input('force-update', 'value')]
    )
    def update_graph(selected_bin_id, n_intervals, force_update):
        forecast_results = two_day_school_hours()

        if selected_bin_id is None or selected_bin_id not in forecast_results:
            return go.Figure(), "Please select a valid bin from the dropdown."

        if 'update' in force_update:
            forecast_results = two_day_school_hours()

        selected_bin = forecast_results[selected_bin_id]
        fig = go.Figure()

        for waste_type, forecast_data in selected_bin['waste_types'].items():
            dates = [entry['datetime'] for entry in forecast_data]
            levels = [entry['predicted_level'] for entry in forecast_data]

            if not dates or not levels:
                return go.Figure(), "No forecast data available for the selected bin."

            fig.add_trace(go.Scatter(
                x=dates, y=levels,
                name=f"{selected_bin['bin_name']} - {waste_type}",
                mode='lines+markers',  
                marker=dict(size=6),
                line=dict(width=2)
            ))

        fig.update_layout(
            title=f"Waste Fill Level Forecast for {selected_bin['bin_name']}",
            xaxis_title='Datetime',
            yaxis_title='Predicted Fill Level (%)',
            xaxis=dict(showgrid=True),
            yaxis=dict(range=[0, 100], showgrid=True),
            hovermode='x unified',
            template="plotly_white",  
            font=dict(family="Arial, sans-serif", size=14),
            margin=dict(l=40, r=40, t=60, b=40),  # Padding for readability
            plot_bgcolor="#f9f9f9",
            paper_bgcolor="#f4f4f4"
        )

        return fig, "Forecast updated successfully."

    return app
