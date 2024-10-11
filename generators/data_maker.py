import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants
bin_names = [1, 2, 3]
waste_types = [1, 2]
days = 7  # Simulate 7 days of data
time_intervals_per_day = 24  # Hourly data


# Function to generate synthetic data with random daily fill fluctuations
def generate_synthetic_data():
    data = []
    start_date = datetime.now() - timedelta(days=days)  # Start from a number of days ago
    time_interval = timedelta(hours=1)  # Hourly data

    for bin_name in bin_names:
        for waste_type in waste_types:
            for day in range(days):
                daily_fill_level = np.random.randint(5, 80)  # Random fill level at the start of the day
                reset_probability = np.random.random()  # Random chance to reset the bin (simulating emptying)
                if reset_probability > 0.7:  # 30% chance that the bin gets emptied overnight
                    daily_fill_level = np.random.randint(5, 20)  # Lower fill level for the new day

                for hour in range(time_intervals_per_day):
                    timestamp = start_date + timedelta(days=day, hours=hour)

                    # Gradually increase the fill level over the course of the day with some randomness
                    fill_increase = np.random.normal(loc=2, scale=1)  # Average increase per hour
                    daily_fill_level += fill_increase

                    # Ensure fill level is capped at 100 and a minimum of 0
                    fill_level = max(min(daily_fill_level, 100), 0)

                    data.append({
                        'bin_name': bin_name,
                        'waste_type': waste_type,
                        'timestamp': timestamp,
                        'fill_level': fill_level
                    })

    return pd.DataFrame(data)


# Generate synthetic data with daily random fluctuations
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
with open('bin_fill_levels_data.sql', 'w') as f:
    for query in sql_queries:
        f.write(query + "\n")

print("SQL queries saved to 'bin_fill_levels_data.sql'")
