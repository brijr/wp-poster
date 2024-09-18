# WordPress CSV/SQLite Field Mapper

This application allows you to map and import data from CSV files or SQLite databases into WordPress posts.

## Features

- Connect to WordPress using REST API
- Support for CSV and SQLite data sources
- Dynamic field mapping
- Batch processing of data
- Progress tracking
- Mapping save/load functionality

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your WordPress credentials:
   ```
   WORDPRESS_URL="https://your-wordpress-site.com"
   WORDPRESS_USERNAME="your_username"
   WORDPRESS_APP_PASSWORD="your_app_password"
   ```

## Usage

1. Run the Streamlit app:
   ```
   streamlit run app.py
   ```
2. Select your data source (CSV or SQLite)
3. Upload your file
4. Map the fields from your data source to WordPress fields
5. Click "Process and Send Data" to import the data

## Files

- `app.py`: Main application file containing the Streamlit interface and data processing logic
- `.env.example`: Example environment file for WordPress credentials

## Notes

- Ensure your WordPress site has the REST API enabled
- Use an application password for authentication instead of your main WordPress password
- Large datasets may take some time to process; the app includes a progress bar for tracking
