import os
import re
import json
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ============================================
# CMS Hospital Dataset Downloader
# Author: Sai Krishna Valluri
# HealthPartners Data Engineering Assessment
# ============================================

# Configuration
CMS_API_URL = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items"
OUTPUT_DIR = Path("cms_hospital_data")
METADATA_FILE = Path("run_metadata.json")
MAX_WORKERS = 5

def to_snake_case(column_name: str) -> str:
    """Convert mixed case column names with spaces/special chars to snake_case."""
    # Replace special characters and spaces with underscore
    name = re.sub(r'[^a-zA-Z0-9]', '_', str(column_name))
    # Handle camelCase
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    name = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', name)
    # Clean up multiple underscores and lowercase
    name = re.sub(r'_+', '_', name).strip('_').lower()
    return name

def load_metadata() -> dict:
    """Load metadata from previous run."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(metadata: dict):
    """Save run metadata for next run comparison."""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Metadata saved to {METADATA_FILE}")

def get_hospital_datasets() -> list:
    """Fetch all datasets related to Hospitals from CMS metastore."""
    print("📥 Fetching CMS dataset catalog...")
    
    try:
        response = requests.get(CMS_API_URL, timeout=30)
        response.raise_for_status()
        datasets = response.json()
        
        # Filter for Hospital-related datasets
        hospital_datasets = [
            d for d in datasets
            if 'hospital' in str(d.get('title', '')).lower() or
               'hospital' in str(d.get('description', '')).lower() or
               'hospital' in str(d.get('keyword', [])).lower()
        ]
        
        print(f"✅ Found {len(hospital_datasets)} Hospital-related datasets")
        return hospital_datasets
        
    except Exception as e:
        print(f"❌ Error fetching datasets: {e}")
        return []

def get_download_url(dataset: dict) -> str:
    """Extract CSV download URL from dataset metadata."""
    try:
        distributions = dataset.get('distribution', [])
        for dist in distributions:
            if dist.get('mediaType') == 'text/csv':
                return dist.get('downloadURL', '')
            if dist.get('format', '').lower() == 'csv':
                return dist.get('downloadURL', '')
        # Try direct data link
        identifier = dataset.get('identifier', '')
        if identifier:
            return f"https://data.cms.gov/provider-data/sites/default/files/resources/{identifier}.csv"
    except Exception:
        pass
    return ''

def should_download(dataset: dict, metadata: dict) -> bool:
    """Check if dataset has been modified since last run."""
    dataset_id = dataset.get('identifier', '')
    modified_date = dataset.get('modified', '')
    
    if dataset_id not in metadata:
        return True  # Never downloaded before
    
    last_modified = metadata.get(dataset_id, {}).get('modified', '')
    if modified_date != last_modified:
        return True  # Modified since last run
    
    print(f"⏭️  Skipping (no changes): {dataset.get('title', dataset_id)}")
    return False

def download_and_process(dataset: dict, metadata: dict) -> dict:
    """Download a single dataset, convert columns to snake_case, save CSV."""
    title = dataset.get('title', 'unknown')
    dataset_id = dataset.get('identifier', 'unknown')
    modified = dataset.get('modified', '')
    
    try:
        download_url = get_download_url(dataset)
        if not download_url:
            print(f"⚠️  No download URL for: {title}")
            return {'id': dataset_id, 'status': 'no_url', 'modified': modified}
        
        print(f"📥 Downloading: {title}")
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()
        
        # Read CSV
        from io import StringIO
        df = pd.read_csv(StringIO(response.text), low_memory=False)
        
        # Convert column names to snake_case
        original_cols = list(df.columns)
        df.columns = [to_snake_case(col) for col in df.columns]
        
        # Save to output directory
        OUTPUT_DIR.mkdir(exist_ok=True)
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)[:50]
        output_path = OUTPUT_DIR / f"{safe_title}.csv"
        df.to_csv(output_path, index=False)
        
        print(f"✅ Saved: {output_path} ({len(df):,} rows, {len(df.columns)} cols)")
        
        # Return metadata for this run
        return {
            'id': dataset_id,
            'status': 'success',
            'modified': modified,
            'rows': len(df),
            'columns': len(df.columns),
            'file': str(output_path),
            'downloaded_at': datetime.now().isoformat(),
            'sample_columns': list(df.columns)[:5]
        }
        
    except Exception as e:
        print(f"❌ Failed: {title} — {e}")
        return {'id': dataset_id, 'status': 'failed', 'error': str(e)}

def main():
    print("=" * 60)
    print("CMS HOSPITAL DATASET DOWNLOADER")
    print(f"Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Load previous run metadata
    metadata = load_metadata()
    print(f"📋 Previous run metadata: {len(metadata)} datasets tracked")
    
    # Get all hospital datasets
    datasets = get_hospital_datasets()
    if not datasets:
        print("❌ No datasets found. Exiting.")
        return
    
    # Filter to only datasets modified since last run
    to_download = [d for d in datasets if should_download(d, metadata)]
    print(f"\n📥 Datasets to download: {len(to_download)} of {len(datasets)}")
    
    if not to_download:
        print("✅ All datasets are up to date. Nothing to download.")
        return
    
    # Download in parallel
    print(f"\n🚀 Starting parallel download with {MAX_WORKERS} workers...")
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_and_process, d, metadata): d 
            for d in to_download
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    # Update metadata
    for result in results:
        if result.get('status') == 'success':
            metadata[result['id']] = {
                'modified': result['modified'],
                'last_downloaded': result['downloaded_at'],
                'rows': result['rows'],
                'file': result['file']
            }
    
    save_metadata(metadata)
    
    # Summary
    success = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'failed']
    skipped = [r for r in results if r.get('status') == 'no_url']
    
    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully downloaded : {len(success)}")
    print(f"❌ Failed                 : {len(failed)}")
    print(f"⚠️  No URL found           : {len(skipped)}")
    print(f"⏭️  Skipped (no changes)   : {len(datasets) - len(to_download)}")
    print(f"📁 Output directory        : {OUTPUT_DIR.absolute()}")
    print("=" * 60)

if __name__ == "__main__":
    main()
    