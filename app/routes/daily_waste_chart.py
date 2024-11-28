from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd
from app.engine import db
from datetime import datetime, timedelta

def create_dash_app(server, pathname, bin_id):
    dash_app = Dash(__name__, server=server, url_base_pathname=pathname)

    dash_app.layout = html.Div([
        dcc.Loading( 
            id="loading-icon",
            type="default",
            children=[dcc.Graph(id='graph-content')]
        ),
        dcc.Interval(id='interval-component', interval=10000, n_intervals=0), 
        html.Div(id='no-data-message') 
    ])

    @dash_app.callback(
        [Output('graph-content', 'figure'),
         Output('no-data-message', 'children')],
        [Input('interval-component', 'n_intervals')]
    )
    def update_graph(n):
        sql = """
        SELECT DATE(waste_data.timestamp) AS date, waste_bins.bin_name, waste_type.name AS waste_type, COUNT(waste_data.waste_type_id) AS count
        FROM waste_data
        INNER JOIN waste_type ON waste_type.waste_type_id = waste_data.waste_type_id
        INNER JOIN waste_bins ON waste_bins.bin_id = waste_data.bin_id
        WHERE waste_bins.bin_id = %s
        GROUP BY DATE(waste_data.timestamp), waste_type.name
        ORDER BY DATE(waste_data.timestamp);
        """
        try:
            rows = db.fetch(sql, (bin_id,))

            if not rows:
                return go.Figure(), "No data available for the selected waste type."

            df = pd.DataFrame(rows, columns=['date', 'bin_name', 'waste_type', 'count'])

            fig = go.Figure()

            for waste_type in df['waste_type'].unique():
                df_filtered = df[df['waste_type'] == waste_type]
                fig.add_trace(go.Scatter(
                    x=df_filtered['date'], 
                    y=df_filtered['count'], 
                    mode='lines+markers', 
                    name=waste_type, 
                    line=dict(width=4),
                    marker=dict(size=8),
                    hovertemplate='<b>%{x}</b><br>Waste Count: %{y}<br>Waste Type: %{text}<extra></extra>',
                    text=[waste_type] * len(df_filtered)
                ))
            bin_name = df['bin_name'].iloc[0]
            
            fig.update_layout(
                title=f'Waste Data per Day for {bin_name}',
                xaxis_title='Date',
                yaxis_title='Waste Count',
                showlegend=True,
                legend_title="Waste Type",
                legend=dict(
                    title="Waste Type",  
                    font=dict(color="black")  
                ),
                font=dict(family="Arial, sans-serif", size=14),
                hovermode='x unified',  # Unified hover for better comparison
                template="plotly_white",  # White theme for light background
                margin=dict(l=40, r=40, t=60, b=40),  # Margin adjustment
                plot_bgcolor="#f9f9f9",  # Light background color for the chart
                paper_bgcolor="#f4f4f4",  # Background color for the page
                xaxis=dict(showgrid=True, gridwidth=1, gridcolor='lightgray'),
                yaxis=dict(showgrid=True, gridwidth=1, gridcolor='lightgray'),
                transition_duration=500  # Smooth transitions when data updates
            )

            return fig, ""  # Return the figure and an empty message for no-data
        except Exception as e:
            # Handle database or query failure
            return go.Figure(), f"Error fetching data: {str(e)}"

    return dash_app


def cas_dash(server):
    return create_dash_app(server, '/daily-waste/1/', bin_id=1)


def cte_dash(server):
    return create_dash_app(server, '/daily-waste/2/', bin_id=2)


def cbme_dash(server):
    return create_dash_app(server, '/daily-waste/3/', bin_id=3)
