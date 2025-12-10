import pandas as pd

# Read the CSV file
df = pd.read_csv('ipl_scraper/ipl-2020-21-1210595/mumbai-indians-vs-chennai-super-kings-1st-match-1216492/corrected_data.csv')

# Create a new dataframe with mapped columns
mapped_df = pd.DataFrame()
mapped_df['over_number'] = df['over']
mapped_df['batting_team'] = df.apply(lambda row: 'MI' if row['innings'] == 'MI' else 'CSK', axis=1)

# Save to new CSV
mapped_df.to_csv('innings_summary.csv', index=False)
