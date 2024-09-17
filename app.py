import streamlit as st
import pandas as pd
import requests
from typing import List, Dict
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """Ensure the URL has a scheme."""
    parsed = urlparse(url)
    if not parsed.scheme:
        return urlunparse(parsed._replace(scheme="https"))
    return url

def fetch_wordpress_post_types(wp_url: str) -> Dict[str, Dict]:
    """Fetch post types from WordPress instance."""
    normalized_url = normalize_url(wp_url)
    try:
        response = requests.get(f"{normalized_url}/wp-json/wp/v2/types")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error fetching post types: {str(e)}")
        return {}

def get_csv_columns(df: pd.DataFrame) -> List[str]:
    """Get column names from uploaded CSV."""
    return df.columns.tolist()

def main():
    st.title("WordPress CSV Field Mapper")

    # WordPress URL input
    wp_url = st.text_input("Enter WordPress URL (e.g., wordpress.travelmellow.com)")

    if wp_url:
        # Fetch post types
        with st.spinner("Fetching post types..."):
            post_types = fetch_wordpress_post_types(wp_url)

        if post_types:
            selected_post_type = st.selectbox("Select Post Type", list(post_types.keys()))

            # File uploader
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

            if uploaded_file is not None:
                df = pd.read_csv(uploaded_file)
                csv_columns = get_csv_columns(df)

                # Get fields for selected post type
                post_type_fields = post_types[selected_post_type].get("schema", {}).get("properties", {})

                # Field mapping
                st.subheader("Map CSV columns to WordPress fields")
                field_mapping = {}
                for wp_field in post_type_fields:
                    mapped_column = st.selectbox(f"Map '{wp_field}' to", [""] + csv_columns)
                    if mapped_column:
                        field_mapping[wp_field] = mapped_column

                if st.button("Preview Mapping"):
                    st.write("Field Mapping:")
                    st.json(field_mapping)

                    # Here you can add logic to process the mapping and send data to WordPress

if __name__ == "__main__":
    main()
