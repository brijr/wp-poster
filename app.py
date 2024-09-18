import streamlit as st
import pandas as pd
import requests
from typing import List, Dict, Tuple
from urllib.parse import urlparse, urlunparse
import os
from dotenv import load_dotenv
import json
import re
import sqlite3

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

def get_sqlite_tables(db_path: str) -> List[str]:
    """Get table names from SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def get_sqlite_columns(db_path: str, table_name: str) -> List[str]:
    """Get column names from SQLite table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    return columns

def process_and_send_data(data: pd.DataFrame, field_mapping: Dict[str, str], post_type: str, wp_url: str, wp_username: str, wp_app_password: str) -> Tuple[int, int]:
    """Process the data and send it to WordPress."""
    success_count = 0
    error_count = 0
    normalized_url = normalize_url(wp_url)

    progress_bar = st.progress(0)
    total_rows = len(data)

    for i, row in data.iterrows():
        post = {wp_field: row[csv_field] for wp_field, csv_field in field_mapping.items()}
        if 'slug' in post:
            post['slug'] = sanitize_slug(post['slug'])

        try:
            response = requests.post(
                f"{normalized_url}/wp-json/wp/v2/{post_type}",
                json=post,
                auth=(wp_username, wp_app_password)
            )
            response.raise_for_status()
            success_count += 1
        except requests.RequestException as e:
            error_count += 1
            st.error(f"Error sending data for row {i}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                st.error(f"Response content: {e.response.content}")

        progress_bar.progress((i + 1) / total_rows)

    return success_count, error_count

def sanitize_slug(slug: str) -> str:
    """Sanitize the slug to ensure it's URL-friendly."""
    # Remove any characters that aren't alphanumeric, underscore, or hyphen
    slug = re.sub(r'[^\w-]', '', slug)
    # Convert to lowercase
    slug = slug.lower()
    # Replace spaces with hyphens
    slug = slug.replace(' ', '-')
    return slug

def get_post_type_fields(post_type_data: Dict) -> List[str]:
    """Extract relevant fields from post type data."""
    fields = []
    schema = post_type_data.get("schema", {})
    properties = schema.get("properties", {})

    # Add basic WordPress fields that are likely to exist
    basic_fields = ["title", "content", "excerpt", "status", "author", "featured_media", "categories", "tags", "slug"]
    fields.extend(basic_fields)

    # Add all properties as fields
    fields.extend(properties.keys())

    # Fetch ACF fields
    try:
        acf_fields = fetch_acf_fields(post_type_data.get("rest_base"), debug=True)
        fields.extend(acf_fields)
    except Exception as e:
        st.warning(f"Failed to fetch ACF fields: {str(e)}")

    # Remove duplicates and sort
    fields = sorted(list(set(fields)))

    # Debug information
    st.write("Post type data:")
    st.json(post_type_data)
    st.write("Available fields (including ACF):")
    st.json(fields)

    return fields

def fetch_acf_fields(post_type: str, debug: bool = False) -> List[str]:
    """Fetch ACF fields for a given post type."""
    wp_url = os.getenv("WORDPRESS_URL")
    wp_username = os.getenv("WORDPRESS_USERNAME")
    wp_app_password = os.getenv("WORDPRESS_APP_PASSWORD")

    normalized_url = normalize_url(wp_url)
    # Use the correct endpoint for ACF fields
    full_url = f"{normalized_url}/wp-json/wp/v2/{post_type}"
    if debug:
        st.write(f"Attempting to fetch ACF fields from: {full_url}")

    try:
        response = requests.get(
            full_url,
            auth=(wp_username, wp_app_password)
        )
        response.raise_for_status()
        posts_data = response.json()

        # Extract ACF field names from the first post
        if posts_data and isinstance(posts_data, list) and len(posts_data) > 0:
            acf_data = posts_data[0].get('acf', {})
            fields = list(acf_data.keys())

            if debug:
                st.write(f"ACF fields found: {fields}")

            return fields
        else:
            if debug:
                st.warning(f"No posts found for post type '{post_type}'.")
            return []

    except requests.RequestException as e:
        if e.response is not None and e.response.status_code == 404:
            if debug:
                st.warning(f"ACF fields not found for post type '{post_type}'. This is normal if ACF is not used for this post type.")
        else:
            if debug:
                st.error(f"Error fetching ACF fields: {str(e)}")
        return []

def save_mapping(mapping: Dict[str, str], filename: str):
    with open(filename, 'w') as f:
        json.dump(mapping, f)

def load_mapping(filename: str) -> Dict[str, str]:
    with open(filename, 'r') as f:
        return json.load(f)

def sanitize_input(input_string: str) -> str:
    return re.sub(r'[^\w\s-]', '', input_string).strip()

def test_wordpress_connection(wp_url: str, wp_username: str, wp_app_password: str):
    normalized_url = normalize_url(wp_url)
    try:
        response = requests.get(
            f"{normalized_url}/wp-json/wp/v2/users/me",
            auth=(wp_username, wp_app_password)
        )
        response.raise_for_status()
        user_data = response.json()
        st.success(f"Successfully authenticated as: {user_data.get('name', 'Unknown')}")
        st.json(user_data)
    except requests.RequestException as e:
        st.error(f"Error testing connection: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Response content: {e.response.content}")

def check_user_capabilities(wp_url: str, wp_username: str, wp_app_password: str):
    normalized_url = normalize_url(wp_url)
    try:
        response = requests.get(
            f"{normalized_url}/wp-json/wp/v2/users/me?context=edit",
            auth=(wp_username, wp_app_password)
        )
        response.raise_for_status()
        user_data = response.json()
        st.write("User Capabilities:")
        st.json(user_data.get('capabilities', {}))
    except requests.RequestException as e:
        st.error(f"Error checking user capabilities: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Response content: {e.response.content}")

def main():
    st.title("WordPress CSV/SQLite Field Mapper")

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

        # Display information for the selected post type
        if selected_post_type:
            with st.expander(f"View Information for '{selected_post_type}'"):
                post_type_data = post_types[selected_post_type]
                st.write(f"Post Type: {selected_post_type}")
                st.write(f"REST Base: {post_type_data.get('rest_base')}")
                st.write(f"Description: {post_type_data.get('description')}")
                st.write(f"Hierarchical: {post_type_data.get('hierarchical')}")
                st.write(f"Viewable: {post_type_data.get('viewable')}")

                post_type_fields = get_post_type_fields(post_type_data)
                if post_type_fields:
                    st.write("Available fields:")
                    for field in post_type_fields:
                        st.write(f"- {field}")
                else:
                    st.write("No fields available for this post type.")

                st.write("Supported features:")
                st.json(post_type_data.get('supports', {}))

                st.write("Raw post type data:")
                st.json(post_type_data)

        # Data source selection
        data_source = st.radio("Select Data Source", ["CSV", "SQLite"])

        if data_source == "CSV":
            # File uploader for CSV
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
            if uploaded_file is not None:
                df = pd.read_csv(uploaded_file)
                columns = get_csv_columns(df)
        else:
            # File uploader for SQLite
            uploaded_file = st.file_uploader("Choose a SQLite database file", type="db")
            if uploaded_file is not None:
                db_path = "temp_db.db"
                with open(db_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Get table names
                tables = get_sqlite_tables(db_path)
                selected_table = st.selectbox("Select Table", tables)

                # Get columns for the selected table
                columns = get_sqlite_columns(db_path, selected_table)
                df = pd.read_sql_query(f"SELECT * FROM {selected_table}", sqlite3.connect(db_path))

        if 'df' in locals() and not df.empty:
            # Get fields for selected post type
            post_type_fields = get_post_type_fields(post_types[selected_post_type])

            # Field mapping
            st.subheader("Map columns to WordPress fields")
            field_mapping = {}
            for column in columns:
                mapped_field = st.selectbox(f"Map column '{column}' to", [""] + post_type_fields, key=column)
                if mapped_field:
                    field_mapping[mapped_field] = column

            # Preview mapping
            if field_mapping:
                st.subheader("Field Mapping Preview")
                for wp_field, column in field_mapping.items():
                    st.write(f"WordPress '{wp_field}' <- '{column}'")

            # Data preview
            st.subheader("Data Preview")
            st.dataframe(df.head())

            # Save and Load Mapping buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Mapping"):
                    save_mapping(field_mapping, "mapping.json")
                    st.success("Mapping saved successfully!")
            with col2:
                if st.button("Load Mapping"):
                    try:
                        loaded_mapping = load_mapping("mapping.json")
                        field_mapping.update(loaded_mapping)
                        st.success("Mapping loaded successfully!")
                    except FileNotFoundError:
                        st.error("No saved mapping found.")

            # Upload data to WordPress
            if st.button("Upload Data to WordPress"):
                if field_mapping:
                    with st.spinner("Processing and sending data..."):
                        success_count, error_count = process_and_send_data(df, field_mapping, selected_post_type, wp_url, wp_username, wp_app_password)
                    st.success(f"Processed {success_count} entries successfully. {error_count} entries failed.")
                else:
                    st.warning("Please map at least one field before uploading.")

        if st.button("Test WordPress Connection"):
            test_wordpress_connection(wp_url, wp_username, wp_app_password)
            check_user_capabilities(wp_url, wp_username, wp_app_password)

if __name__ == "__main__":
    main()
