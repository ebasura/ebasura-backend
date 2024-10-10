import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants
bin_names = [1, 2, 3]
waste_types = [1, 2]
days = 30  # Simulate 30 days of data
time_intervals_per_day = 24  # Hourly data


# Function to generate synthetic data
def generate_synthetic_data():
    data = []
    start_date = datetime.now() - timedelta(days=days)  # 30 days ago
    time_interval = timedelta(hours=1)  # Hourly data

    for bin_name in bin_names:
        for waste_type in waste_types:
            for day in range(days):
                for hour in range(time_intervals_per_day):
                    timestamp = start_date + timedelta(days=day, hours=hour)
                    fill_level = np.random.randint(10, 90) + np.random.random()  # Random fill level between 10 and 90
                    # Simulating fill level increase over time
                    if waste_type == 2:
                        fill_level += np.random.normal(loc=0.2, scale=0.1) * hour
                    else:
                        fill_level += np.random.normal(loc=0.15, scale=0.05) * hour

                    # Ensure fill level is capped at 100
                    fill_level = min(fill_level, 100)

                    data.append({
                        'bin_name': bin_name,
                        'waste_type': waste_type,
                        'timestamp': timestamp,
                        'fill_level': fill_level
                    })

    return pd.DataFrame(data)


# Generate synthetic data
df = generate_synthetic_data()


# Function to generate SQL insert queries from DataFrame
def generate_sql_insert_queries(df):
    queries = []
    for index, row in df.iterrows():
        query = f"""
            INSERT INTO bin_fill_levels (bin_id, waste_type, timestamp, fill_level)
            VALUES ({row['bin_name']}, {row['waste_type']}, '{row['timestamp']}', {row['fill_level']:.2f});
        """
        queries.append(query)
    return queries


# Generate SQL insert queries
sql_queries = generate_sql_insert_queries(df)

# Save SQL insert queries to a .sql file
with open('../bin_fill_levels_data.sql', 'w') as f:
    for query in sql_queries:
        f.write(query + "\n")

print("SQL queries saved to 'bin_fill_levels_data.sql'")
