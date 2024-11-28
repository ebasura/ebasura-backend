import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants
BIN_IDS = [1, 2, 3]
WASTE_TYPES = [1, 2]
PAST_DAYS = 90
FUTURE_DAYS = 1 
TIME_INTERVALS_PER_DAY = 24  
SEED = 42  # For reproducibility
BIN_HEIGHT = 65  # The height of the bin (max fill level is 65)
OUTPUT_FILE = 'bin_fill_levels_data.sql'

# Function to generate synthetic data with bin reset logic (twice a week)
def generate_synthetic_data(bin_ids, waste_types, past_days, future_days, time_intervals_per_day, seed=None):
    """
    Generates synthetic data for waste bin fill levels over a specified period, including
    random resets twice a week (between 6:00 AM and 8:00 AM) to simulate the bin being emptied.
    """
    np.random.seed(seed)  # Set seed for reproducibility
    start_date = datetime.now() - timedelta(days=past_days)
    end_date = datetime.now() + timedelta(days=future_days)
    
    # Generate hourly timestamps
    timestamps = pd.date_range(start=start_date, end=end_date, freq='H')

    # Initialize an empty list to store data
    data = []
    
    # Define reset days (two days a week - Monday and Thursday for example)
    reset_days = [0, 3]  # Monday = 0, Thursday = 3
    
    # Generate data for each bin and waste type
    for bin_id in bin_ids:
        for waste_type in waste_types:
            # Start with a partially full bin (fill level closer to bin height, i.e. 65)
            fill_level = np.random.randint(50, BIN_HEIGHT)  # Start with a bin that's partially empty
            previous_fill_level = fill_level

            for timestamp in timestamps:
                # Logic to reset the bin fill level on reset days
                if timestamp.hour == 6 and timestamp.weekday() in reset_days:
                    # Random reset time between 6 AM and 8 AM (use time object, not timedelta)
                    random_hour = np.random.randint(6, 9)
                    reset_time = datetime.combine(timestamp.date(), datetime.min.time()) + timedelta(hours=random_hour)
                    
                    if timestamp >= reset_time:
                        fill_level = BIN_HEIGHT  # Empty the bin (fill level 65 means the bin is empty)
                
                # Gradual filling pattern (increase over time)
                # Simulate waste being added, increasing the fill level gradually
                if timestamp.hour >= 8 and timestamp.hour < 16:  # Assume bins fill gradually during daytime
                    fill_increase = np.random.normal(loc=2, scale=1)  # Simulate gradual fill-in over time
                    fill_level += fill_increase

                # Bound the fill level between 0 and BIN_HEIGHT (65)
                fill_level = np.clip(fill_level, 0, BIN_HEIGHT)

                # Logic to make the bin fill/empty gradually (reflecting realistic accumulation patterns)
                if fill_level > previous_fill_level:
                    # Gradual increase (daytime)
                    previous_fill_level = fill_level
                else:
                    # Gradual decrease (nighttime or after a reset)
                    previous_fill_level = fill_level
                
                # Append the data to the list
                data.append({
                    'bin_id': bin_id,
                    'waste_type': waste_type,
                    'timestamp': timestamp,
                    'fill_level': round(fill_level, 2)  # Rounded fill level
                })

    return pd.DataFrame(data)

# Function to generate SQL insert queries
def generate_sql_insert_queries(df):
    """
    Generates optimized SQL insert queries for the given DataFrame.
    """
    queries = [
        f"INSERT INTO bin_fill_levels (bin_id, waste_type, timestamp, fill_level) VALUES "
        f"({row['bin_id']}, {row['waste_type']}, '{row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}', {row['fill_level']:.2f});"
        for _, row in df.iterrows()
    ]
    return queries

# Function to save SQL queries to a file
def save_queries_to_file(queries, filename=OUTPUT_FILE):
    """
    Saves the generated SQL queries to a file efficiently using buffered write.
    """
    try:
        with open(filename, 'w') as f:
            f.write("\n".join(queries))
        print(f"SQL queries saved to '{filename}'")
    except Exception as e:
        print(f"Error writing to file: {e}")

# Generate synthetic data with reset logic
df = generate_synthetic_data(BIN_IDS, WASTE_TYPES, PAST_DAYS, FUTURE_DAYS, TIME_INTERVALS_PER_DAY, SEED)

# Generate SQL queries
sql_queries = generate_sql_insert_queries(df)

# Save the queries to a file
save_queries_to_file(sql_queries)
