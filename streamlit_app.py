import streamlit as st
import requests
import tempfile
import zipfile
import os
from pathlib import Path
import plotly.express as px
import pandas as pd


def download_package(package_name, version=None):
    pypi_url = f"https://pypi.org/pypi/{package_name}/json"
    response = requests.get(pypi_url)
    response.raise_for_status()

    package_data = response.json()
    if version is None:
        version = package_data["info"]["version"]

    download_url = None
    for release in package_data["releases"][version]:
        if release["packagetype"] == "sdist":
            download_url = release["url"]
            break

    if not download_url:
        raise ValueError(f"No source distribution found for {package_name} {version}")

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{package_name}.tar.gz")

    response = requests.get(download_url, stream=True)
    response.raise_for_status()

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return file_path


def analyze_package(file_path):
    web_extensions = {
        ".js",
        ".css",
        ".html",
        ".htm",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
    }
    assets = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        if file_path.endswith(".tar.gz"):
            import tarfile

            with tarfile.open(file_path) as tar:
                tar.extractall(temp_dir)
        elif file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path) as zip_ref:
                zip_ref.extractall(temp_dir)

        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = Path(os.path.join(root, file))
                if file_path.suffix.lower() in web_extensions:
                    size = os.path.getsize(file_path)
                    rel_path = str(file_path.relative_to(temp_dir))
                    assets[rel_path] = {
                        "size": size,
                        "extension": file_path.suffix.lower(),
                        "path": rel_path,
                    }

    return assets

def analyze_dataframe(df):
    # Add size in MB column
    df["size_mb"] = df["size"] / (1024 * 1024)

    # Size by extension pie chart
    fig1 = px.pie(
        df.groupby("extension")["size"].sum().reset_index(),
        values="size",
        names="extension",
        title="Distribution of Asset Sizes by Type",
    )
    st.plotly_chart(fig1)

    # Size distribution histogram
    fig2 = px.histogram(
        df,
        x="size_mb",
        nbins=30,
        title="Distribution of Asset Sizes",
        labels={"size_mb": "Size (MB)", "count": "Number of Files"},
        color="extension",
    )
    fig2.update_layout(bargap=0.1)
    st.plotly_chart(fig2)

    # File list
    st.subheader("Asset Details")
    st.dataframe(
        df[["path", "extension", "size_mb"]]
        .sort_values("size_mb", ascending=False)
        .rename(columns={"size_mb": "Size (MB)"})
    )

    # Summary statistics
    st.subheader("Summary")
    total_size_mb = df["size"].sum() / (1024 * 1024)
    st.markdown(
        f"""
    - Total assets: {len(df)}
    - Total size: {total_size_mb:.2f} MB
    - Average size: {df['size_mb'].mean():.2f} MB
    - Median size: {df['size_mb'].median():.2f} MB
    """
    )


st.title("PyPI Package Web Asset Analyzer")

package_input = st.text_input(
    "Enter PyPI package names (comma-separated)",
    "streamlit-cookies-manager,streamlit-option-menu,streamlit-aggrid,st-autorefresh,streamlit-antd-components,streamlit-folium,streamlit-feedback,streamlit-theme,streamlit-lottie,",
)
analyze_button = st.button("Analyze Packages")

dataframes = []
if analyze_button:
    packages = [pkg.strip() for pkg in package_input.split(",")]

    for package in packages:
        st.subheader(f"Analysis for {package}")

        try:
            with st.spinner(f"Downloading and analyzing {package}..."):
                file_path = download_package(package)
                assets = analyze_package(file_path)

                if not assets:
                    st.warning("No web assets found in package")
                    continue

                # Create DataFrame for visualization
                df = pd.DataFrame(
                    [
                        {
                            "path": details["path"],
                            "size": details["size"],
                            "extension": details["extension"],
                        }
                        for details in assets.values()
                    ]
                )
                analyze_dataframe(df)

                dataframes.append(df)
        except Exception as e:
            st.error(f"Error analyzing {package}: {str(e)}")

if len(dataframes):
    st.write("# Cumulative summary")
    analyze_dataframe(pd.concat(dataframes, axis=0, ignore_index=True))

