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

# Configure logging
logging.basicConfig(level=logging.INFO)

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
    try:
        data = db.fetch(query)  # Fetch data from the database
    except Exception as e:
        logging.error(f"Error fetching data from database: {e}")
        return []

    # Convert fetched data into a DataFrame
    df = pd.DataFrame(data, columns=['bin_id', 'bin_name', 'waste_type_name', 'timestamp', 'fill_level'])

    if df.empty:
        logging.warning("The fetched data is empty. Please check the database query.")
        return []

    # Convert timestamp to datetime format and fill levels to numeric
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['fill_level'] = pd.to_numeric(df['fill_level'], errors='coerce')

    # Drop rows with invalid data
    df.dropna(subset=['timestamp', 'fill_level'], inplace=True)

    # Feature engineering: create time-based features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['day_of_month'] = df['timestamp'].dt.day
    df['month'] = df['timestamp'].dt.month
    df['lag_1'] = df['fill_level'].shift(1).fillna(0)  # Adding a lag feature

    # Forecasting fill levels for the next 5 days and accuracy check
    forecast_results = {}
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
            try:
                grid_search.fit(X_train, y_train)
                model_fit = grid_search.best_estimator_

                # Cache the trained model to disk, along with the current timestamp
                cache_model(model_fit, model_filename, datetime.now())
            except Exception as e:
                logging.error(f"Error during model training: {e}")
                continue

        # Evaluate the model accuracy on the test set
        try:
            y_pred = model_fit.predict(X_test)

            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            mape = mean_absolute_percentage_error(y_test, y_pred)
            # Calculate and print accuracy score
            accuracy_score = 100 - mape * 100
            logging.info(f"Accuracy Score for Bin {bin_name}, Waste Type {waste_type}: {accuracy_score:.2f}%")

            # Log the accuracy metrics
            logging.info(f"Bin: {bin_name}, Waste Type: {waste_type}")
            logging.info(f"MAE: {mae:.2f}, MSE: {mse:.2f}, MAPE: {mape:.2%}\n")
        except Exception as e:
            logging.error(f"Error during model evaluation: {e}")
            continue

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
        try:
            forecast_values = model_fit.predict(future_X)
        except Exception as e:
            logging.error(f"Error during forecasting: {e}")
            continue

        # Create a forecast for working hours
        bin_forecast = []
        for i, future in enumerate(future_dates):
            # Cap the predicted fill level between 0 and 100
            future_fill_level = min(max(forecast_values[i], 0), 100)
            
            # Assuming a fixed bin depth of 75 units
            filled_height = 75 - future_fill_level

            percentage_full = (filled_height / 75) * 100

            # Store the forecast result with the date and time
            bin_forecast.append({
                'datetime': future['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'date': future['timestamp'].strftime('%Y-%m-%d'),
                'time': future['timestamp'].strftime('%H:%M'),
                'predicted_level': float("{:.2f}".format(percentage_full))
            })

        # Append forecast results for this bin and waste type
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
        html.H1("Waste Fill Level Forecast Dashboard"),
        dcc.Dropdown(
            id='bin-selector',
            options=[{'label': res['bin_name'], 'value': bin_id} for bin_id, res in forecast_results.items()],
            value=list(forecast_results.keys())[0] if forecast_results else None,
            placeholder="Select a Bin to View Forecast"
        ),
        dcc.Graph(id='forecast-graph'),
        html.Div(id='debug-output')  # Debug output to display messages
    ])

    @app.callback(
        [Output('forecast-graph', 'figure'),
        Output('debug-output', 'children')],
        [Input('bin-selector', 'value')]
    )
    def update_graph(selected_bin_id):
        if selected_bin_id is None or selected_bin_id not in forecast_results:
            return go.Figure(), "Please select a valid bin from the dropdown."

        selected_bin = forecast_results[selected_bin_id]
        fig = go.Figure()

        for waste_type, forecast_data in selected_bin['waste_types'].items():
            dates = [entry['datetime'] for entry in forecast_data]
            levels = [entry['predicted_level'] for entry in forecast_data]

            if not dates or not levels:
                return go.Figure(), "No forecast data available for the selected bin."

            # Add a bar for each waste type with increased width
            fig.add_trace(go.Bar(x=dates, y=levels, name=f"{selected_bin['bin_name']} - {waste_type}", marker=dict(line=dict(width=1.5))))

        fig.update_layout(
            title=f"Waste Fill Level Forecast for {selected_bin['bin_name']}",
            xaxis_title='Datetime',
            yaxis_title='Predicted Fill Level (%)',
            xaxis=dict(showgrid=True),
            yaxis=dict(range=[0, 100], showgrid=True),
            barmode='group'
        )
        return fig, None

    return app
