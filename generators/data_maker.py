import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants
bin_ids = [1, 2, 3]
waste_types = [1, 2]
past_days = 1  # Number of past days to simulate
future_days = 7  # Number of future days to simulate
time_intervals_per_day = 24  # Hourly data


# Function to generate synthetic data with random daily fill fluctuations
def generate_synthetic_data():
    data = []
    start_date = datetime.now() - timedelta(days=past_days)  # Start from 'past_days' days ago
    end_date = datetime.now() + timedelta(days=future_days)  # Extend to 'future_days' into the future
    total_hours = int((end_date - start_date).total_seconds() / 3600)  # Total number of hours

    for bin_id in bin_ids:
        for waste_type in waste_types:
            # Initialize fill level
            fill_level = np.random.randint(5, 80)
            timestamp = start_date
            for hour in range(total_hours):
                # Simulate bin emptying with a certain probability
                if timestamp.hour == 0 and np.random.random() > 0.7:
                    fill_level = np.random.randint(5, 20)  # Reset fill level

                # Gradually increase the fill level over the course of the day with some randomness
                fill_increase = np.random.normal(loc=2, scale=1)  # Average increase per hour
                fill_level += fill_increase

                # Ensure fill level is capped between 0 and 100
                fill_level = max(min(fill_level, 100), 0)

                # Append data point
                data.append({
                    'bin_id': bin_id,
                    'waste_type': waste_type,
                    'timestamp': timestamp,
                    'fill_level': fill_level
                })

                # Increment timestamp by one hour
                timestamp += timedelta(hours=1)

    return pd.DataFrame(data)


# Generate synthetic data with daily random fluctuations
df = generate_synthetic_data()


# Function to generate SQL insert queries from DataFrame
def generate_sql_insert_queries(df):
    queries = []
    for index, row in df.iterrows():
        timestamp_str = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            INSERT INTO bin_fill_levels (bin_id, waste_type, timestamp, fill_level)
            VALUES ({row['bin_id']}, {row['waste_type']}, '{timestamp_str}', {row['fill_level']:.2f});
        """
        queries.append(query.strip())  # Remove any leading/trailing whitespace
    return queries


# Generate SQL insert queries
sql_queries = generate_sql_insert_queries(df)

# Save SQL insert queries to a .sql file
with open('bin_fill_levels_data.sql', 'w') as f:
    for query in sql_queries:
        f.write(query + "\n")

print("SQL queries saved to 'bin_fill_levels_data.sql'")
