from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import pandas as pd
from app.engine import db
from datetime import datetime, timedelta

def create_dash_app(server, pathname, bin_id):
    # Create Dash app
    dash_app = Dash(__name__, server=server, url_base_pathname=pathname)

    # Define the layout of the Dash app
    dash_app.layout = html.Div([
        dcc.Dropdown(id='dropdown-selection',
                     options=[{'label': 'Recyclable', 'value': 'Recyclable'},
                              {'label': 'Non-recyclable', 'value': 'Non-recyclable'}],
                     value='Recyclable',
                     placeholder="Select waste type"),
        dcc.Loading(  # Add a loading spinner for better user feedback
            id="loading-icon",
            type="default",
            children=[
                dcc.Graph(id='graph-content')
            ]
        ),
        dcc.Interval(id='interval-component', interval=10000, n_intervals=0),
        # Reduce query interval to avoid overloading
        html.Div(id='no-data-message')  # Placeholder for no data feedback
    ])

    # Define the callback to update the graph based on selected waste type
    @dash_app.callback(
        [Output('graph-content', 'figure'),
         Output('no-data-message', 'children')],
        [Input('dropdown-selection', 'value'),
         Input('interval-component', 'n_intervals')]
    )
    def update_graph(waste_type, n):
        # SQL query to get all available data for the selected waste type and bin_id
        sql = """
        SELECT DATE(waste_data.timestamp) AS date, COUNT(waste_data.waste_type_id) as count
        FROM waste_data
        INNER JOIN waste_type ON waste_type.waste_type_id = waste_data.waste_type_id
        INNER JOIN waste_bins ON waste_bins.bin_id = waste_data.bin_id
        WHERE waste_type.name = %s AND waste_bins.bin_id = %s
        GROUP BY DATE(waste_data.timestamp)
        ORDER BY DATE(waste_data.timestamp);
        """
        try:
            # Fetch all data from the database for the specified bin and waste type
            rows = db.fetch(sql, (waste_type, bin_id))

            # If no data returned, handle empty data gracefully
            if not rows:
                return px.line(), "No data available for the selected waste type."

            # Convert rows to a DataFrame
            df = pd.DataFrame(rows, columns=['date', 'count'])

            # Create a time series line chart with the fetched data (waste per day)
            fig = px.line(df, x='date', y='count', title=f'Waste Data per Day for {waste_type}')
            fig.update_layout(
                xaxis_title='Date',
                yaxis_title='Waste Count',
                transition_duration=500
            )

            return fig, ""  # Return the figure and an empty message for no-data
        except Exception as e:
            # Handle database or query failure
            return px.line(), f"Error fetching data: {str(e)}"

    return dash_app


def cas_dash(server):
    return create_dash_app(server, '/daily-waste/1/', bin_id=1)


def cte_dash(server):
    return create_dash_app(server, '/daily-waste/2/', bin_id=2)


def cbme_dash(server):
    return create_dash_app(server, '/daily-waste/3/', bin_id=3)
