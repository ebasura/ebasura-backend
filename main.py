from flask import Flask, jsonify, request
from flask_cors import CORS
from app.routes.daily_waste_chart import cas_dash, cbme_dash, cte_dash
from app.routes.fill_level import fill_level_bp
from app.engine import db
from app.routes.forecast import two_day_school_hours
import threading
import asyncio
from check_bin_fill_levels import check_bin_fill_levels
app = Flask(__name__)
cas_dash(app)
cte_dash(app)
cbme_dash(app)

CORS(app, resources={
    r"/*": {"origins": {"https://ebasura.online", "https://www.ebasura.online", "http://192.168.0.125:8000", "http://localhost"}}})

app.register_blueprint(fill_level_bp)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    data = two_day_school_hours()
    return jsonify(data)

@app.route('/api/getWasteData', methods=['GET'])
def get_waste_data():
    year = request.args.get('year')
    bin_id = request.args.get('binId')

    query = """
        SELECT 
            YEAR(waste_data.timestamp) AS year,
            MONTH(waste_data.timestamp) AS month, 
            waste_bins.bin_id AS bin_name, 
            waste_type.name AS waste_type_name, 
            COUNT(*) AS count 
        FROM waste_data 
        INNER JOIN waste_bins ON waste_bins.bin_id = waste_data.bin_id 
        INNER JOIN waste_type ON waste_type.waste_type_id = waste_data.waste_type_id 
        WHERE 
            YEAR(waste_data.timestamp) = %s AND
            waste_bins.bin_id = %s
        GROUP BY 
            YEAR(waste_data.timestamp), 
            MONTH(waste_data.timestamp), 
            waste_bins.bin_id, 
            waste_type.name 
        ORDER BY 
            YEAR(waste_data.timestamp), 
            MONTH(waste_data.timestamp);
    """

    result = db.fetch(query, (year, bin_id))
    
    # Initialize a dictionary to store the counts segregated by waste type
    monthly_waste_data = {
        'Recyclable': [0] * 12,    # Assuming 12 months
        'Non-Recyclable': [0] * 12  # Assuming 12 months
    }

    if result:
        for row in result:
            month_index = row['month'] - 1  # Convert month to 0-indexed
            waste_type_name = row['waste_type_name']
            count = row['count']
            
            # Aggregate counts into the appropriate list
            if waste_type_name == 'Recyclable':
                monthly_waste_data['Recyclable'][month_index] += count
            elif waste_type_name == 'Non-Recyclable':
                monthly_waste_data['Non-Recyclable'][month_index] += count

        # Prepare the response
        response = {
            'series': [
                {
                    'name': 'Recyclable',
                    'data': monthly_waste_data['Recyclable']
                },
                {
                    'name': 'Non-Recyclable',
                    'data': monthly_waste_data['Non-Recyclable']
                }
            ],
            'chart': {
                'height': 350,
                'type': 'line',
                'dropShadow': {
                    'enabled': True,
                    'color': '#000',
                    'top': 18,
                    'left': 7,
                    'blur': 10,
                    'opacity': 0.2
                },
                'zoom': {
                    'enabled': False
                },
                'toolbar': {
                    'show': False
                }
            },
            'colors': ['#77B6EA', '#545454'],
            'dataLabels': {
                'enabled': True,
            },
            'stroke': {
                'curve': 'smooth'
            },
            'title': {
                'text': 'Amount of Waste Segregated',
                'align': 'left'
            },
            'grid': {
                'borderColor': '#e7e7e7',
                'row': {
                    'colors': ['#f3f3f3', 'transparent'], 
                    'opacity': 0.5
                },
            },
            'markers': {
                'size': 1
            },
            'xaxis': {
                'categories': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                'title': {
                    'text': 'Month'
                }
            },
            'yaxis': {
                'title': {
                    'text': 'Trash Data'
                },
                'min': 5,
                'max': 100
            },
            'legend': {
                'position': 'top',
                'horizontalAlign': 'right',
                'floating': True,
                'offsetY': -25,
                'offsetX': -5
            }
        }

        return jsonify(response)
    else:
        return jsonify({
            'error': 'No data found'
        })

# Async function to run the check_bin_fill_levels in a loop
async def monitor_bins():
    while True:
        await check_bin_fill_levels()
        await asyncio.sleep(3600)  # Wait for 1 hour before running the function again

# Function to start the asyncio event loop in a separate thread
def start_monitoring():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(monitor_bins())

if __name__ == '__main__':
    # Start the Flask app in one thread
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000))
    flask_thread.start()

    # Start the asynchronous monitoring function in another thread
    monitoring_thread = threading.Thread(target=start_monitoring)
    monitoring_thread.start()
