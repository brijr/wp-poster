import streamlit as st
import pandas as pd
import requests
from typing import List, Dict, Tuple
from urllib.parse import urlparse, urlunparse
import os
from dotenv import load_dotenv
import json
import re
import logging

# Load environment variables
load_dotenv()

def normalize_url(url: str) -> str:
    """Ensure the URL has a scheme."""
    parsed = urlparse(url)
    if not parsed.scheme:
        return urlunparse(parsed._replace(scheme="https"))
    return url

@st.cache_data(ttl=3600)
def fetch_wordpress_post_types(wp_url: str, wp_username: str, wp_app_password: str) -> Dict[str, Dict]:
    """Fetch post types from WordPress instance."""
    normalized_url = normalize_url(wp_url)
    try:
        response = requests.get(
            f"{normalized_url}/wp-json/wp/v2/types",
            auth=(wp_username, wp_app_password)
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error fetching post types: {str(e)}")
        return {}
    except json.JSONDecodeError as e:
        st.error(f"Error decoding JSON response: {str(e)}")
        return {}

def validate_wordpress_connection(wp_url: str, wp_username: str, wp_app_password: str) -> bool:
    """Validate WordPress connection."""
    try:
        response = requests.get(
            f"{normalize_url(wp_url)}/wp-json/wp/v2/types",
            auth=(wp_username, wp_app_password)
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False

def get_csv_columns(df: pd.DataFrame) -> List[str]:
    """Get column names from uploaded CSV."""
    return df.columns.tolist()

def process_and_send_data(df: pd.DataFrame, field_mapping: Dict[str, str], post_type: str, wp_url: str, wp_username: str, wp_app_password: str, batch_size: int = 10) -> Tuple[int, int]:
    """Process the CSV data and send it to WordPress."""
    success_count = 0
    error_count = 0
    normalized_url = normalize_url(wp_url)

    progress_bar = st.progress(0)
    total_rows = len(df)

    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        post_data = {wp_field: row[csv_field] for wp_field, csv_field in field_mapping.items() for _, row in batch.iterrows()}

        try:
            response = requests.post(
                f"{normalized_url}/wp-json/wp/v2/{post_type}",
                json=post_data,
                auth=(wp_username, wp_app_password)
            )
            response.raise_for_status()
            success_count += 1
        except requests.RequestException as e:
            error_count += 1
            st.error(f"Error sending data: {str(e)}")

        progress_bar.progress((i + batch_size) / total_rows)

    return success_count, error_count

def get_post_type_fields(post_type_data: Dict) -> List[str]:
    """Extract relevant fields from post type data."""
    fields = []
    properties = post_type_data.get("schema", {}).get("properties", {})

    # Add title and content fields if they exist
    if "title" in properties:
        fields.append("title")
    if "content" in properties:
        fields.append("content")

    # Add other relevant fields
    fields.extend(["status", "excerpt", "featured_media"])

    # Add custom fields if they exist
    acf = properties.get("acf", {}).get("properties", {})
    fields.extend(acf.keys())

    return fields

def save_mapping(mapping: Dict[str, str], filename: str):
    with open(filename, 'w') as f:
        json.dump(mapping, f)

def load_mapping(filename: str) -> Dict[str, str]:
    with open(filename, 'r') as f:
        return json.load(f)

def sanitize_input(input_string: str) -> str:
    return re.sub(r'[^\w\s-]', '', input_string).strip()

def normalize_url(url: str) -> str:
    """Ensure the URL has a scheme."""
    parsed = urlparse(url)
    if not parsed.scheme:
        return urlunparse(parsed._replace(scheme="https"))
    return url

def main():
    st.title("WordPress CSV Field Mapper")

    # Get WordPress credentials from environment variables
    wp_url = os.getenv("WORDPRESS_URL")
    wp_username = os.getenv("WORDPRESS_USERNAME")
    wp_app_password = os.getenv("WORDPRESS_APP_PASSWORD")

    if not all([wp_url, wp_username, wp_app_password]):
        st.error("WordPress credentials are not set in the .env file.")
        return

    st.write(f"Connected to WordPress URL: {wp_url}")

    # Validate WordPress connection
    if not validate_wordpress_connection(wp_url, wp_username, wp_app_password):
        st.error("Unable to connect to WordPress. Please check your credentials.")
        return

    # Fetch post types
    with st.spinner("Fetching post types..."):
        post_types = fetch_wordpress_post_types(wp_url, wp_username, wp_app_password)

    if post_types:
        selected_post_type = st.selectbox("Select Post Type", list(post_types.keys()))

        # File uploader
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            csv_columns = get_csv_columns(df)

            # Get fields for selected post type
            post_type_fields = get_post_type_fields(post_types[selected_post_type])

            # Field mapping
            st.subheader("Map CSV columns to WordPress fields")
            field_mapping = {}
            for csv_column in csv_columns:
                mapped_field = st.selectbox(f"Map CSV column '{csv_column}' to", [""] + post_type_fields, key=csv_column)
                if mapped_field:
                    field_mapping[mapped_field] = csv_column

            if st.button("Process and Send Data"):
                if field_mapping:
                    with st.spinner("Processing and sending data..."):
                        success_count, error_count = process_and_send_data(df, field_mapping, selected_post_type, wp_url, wp_username, wp_app_password)
                    st.success(f"Processed {success_count} entries successfully. {error_count} entries failed.")
                else:
                    st.warning("Please map at least one field before processing.")

            # Preview mapping
            if field_mapping:
                st.subheader("Field Mapping Preview")
                for wp_field, csv_column in field_mapping.items():
                    st.write(f"WordPress '{wp_field}' <- CSV '{csv_column}'")

            # Data preview
            if not df.empty:
                st.subheader("Data Preview")
                st.dataframe(df.head())

            if st.button("Save Mapping"):
                save_mapping(field_mapping, "mapping.json")
                st.success("Mapping saved successfully!")

            if st.button("Load Mapping"):
                try:
                    loaded_mapping = load_mapping("mapping.json")
                    field_mapping.update(loaded_mapping)
                    st.success("Mapping loaded successfully!")
                except FileNotFoundError:
                    st.error("No saved mapping found.")

if __name__ == "__main__":
    main()
