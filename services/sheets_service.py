"""
Equipment data service - handles reading/writing equipment inventory.
Supports both CSV files and Google Sheets.
"""

import pandas as pd
import logging
import json
import base64
import os
import time
from typing import List, Dict, Optional
from pathlib import Path
from config import config

# Google Sheets imports
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    logger.warning("Google Sheets packages not installed. Using CSV only.")

logger = logging.getLogger(__name__)

# Global variables for caching
_sheets_client = None
_equipment_cache = None
_cache_timestamp = 0
_CACHE_DURATION = 30  # Cache for 30 seconds to reduce API calls


def _get_google_sheets_client():
    """
    Connect to Google Sheets using service account credentials.
    Returns gspread client or None if not configured.
    """
    global _sheets_client
    
    if _sheets_client:
        return _sheets_client
    
    if not GOOGLE_SHEETS_AVAILABLE:
        return None
    
    if not config.EQUIPMENT_SHEET_ID:
        logger.info("Google Sheets not configured (no sheet ID), using CSV fallback")
        return None
    
    try:
        # Define the scope for Google Sheets API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Try to load credentials from multiple sources
        creds = None
        
        # Option 1: Try base64-encoded credentials from environment variable
        creds_b64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
        if creds_b64:
            try:
                creds_json = base64.b64decode(creds_b64).decode()
                creds_info = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
                logger.info("Loaded credentials from GOOGLE_CREDENTIALS_BASE64 env var")
            except Exception as e:
                logger.warning(f"Failed to load base64 credentials: {e}")
        
        # Option 2: Try JSON credentials from environment variable
        if not creds:
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                try:
                    creds_info = json.loads(creds_json)
                    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
                    logger.info("Loaded credentials from GOOGLE_CREDENTIALS_JSON env var")
                except Exception as e:
                    logger.warning(f"Failed to load JSON credentials: {e}")
        
        # Option 3: Try loading from file (for local development)
        if not creds and config.GOOGLE_SERVICE_ACCOUNT_FILE:
            if Path(config.GOOGLE_SERVICE_ACCOUNT_FILE).exists():
                creds = Credentials.from_service_account_file(
                    config.GOOGLE_SERVICE_ACCOUNT_FILE,
                    scopes=scopes
                )
                logger.info(f"Loaded credentials from file: {config.GOOGLE_SERVICE_ACCOUNT_FILE}")
            else:
                logger.warning(f"Credentials file not found: {config.GOOGLE_SERVICE_ACCOUNT_FILE}")
        
        if not creds:
            logger.warning("No Google credentials found in environment or file")
            return None
        
        # Create gspread client
        _sheets_client = gspread.authorize(creds)
        logger.info("Successfully connected to Google Sheets")
        return _sheets_client
        
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        logger.info("Falling back to CSV")
        return None


def _load_from_google_sheets() -> Optional[List[Dict]]:
    """
    Load equipment data from Google Sheets.
    Returns list of equipment dicts or None if failed.
    """
    try:
        client = _get_google_sheets_client()
        if not client:
            return None
        
        # Open the spreadsheet
        sheet = client.open_by_key(config.EQUIPMENT_SHEET_ID)
        worksheet = sheet.worksheet(config.EQUIPMENT_SHEET_NAME)
        
        # Get all records as list of dictionaries
        equipment_list = worksheet.get_all_records()
        
        logger.info(f"Loaded {len(equipment_list)} equipment items from Google Sheets")
        return equipment_list
        
    except Exception as e:
        logger.error(f"Error loading from Google Sheets: {e}")
        return None


def _load_from_csv() -> List[Dict]:
    """
    Load equipment data from CSV file.
    Returns list of equipment dicts.
    """
    try:
        csv_path = Path(config.EQUIPMENT_CSV_PATH)
        
        if not csv_path.exists():
            logger.error(f"Equipment CSV not found at {csv_path}")
            return []
        
        df = pd.read_csv(csv_path)
        equipment_list = df.to_dict('records')
        
        logger.info(f"Loaded {len(equipment_list)} equipment items from CSV")
        return equipment_list
        
    except Exception as e:
        logger.error(f"Error loading equipment from CSV: {e}")
        return []


def load_equipment() -> List[Dict]:
    """
    Load all equipment from Google Sheets (if configured) or CSV fallback.
    Uses a cache to reduce API calls (30 second cache duration).
    Returns list of equipment dictionaries.
    """
    global _equipment_cache, _cache_timestamp
    
    # Check if cache is still valid
    current_time = time.time()
    cache_age = current_time - _cache_timestamp
    
    if _equipment_cache is not None and cache_age < _CACHE_DURATION:
        logger.debug(f"Using cached equipment data (age: {cache_age:.1f}s)")
        return _equipment_cache
    
    # Cache expired or not set - reload data
    logger.debug("Cache expired or empty - reloading equipment data")
    
    # Try Google Sheets first
    equipment_list = _load_from_google_sheets()
    
    # Fallback to CSV if Google Sheets failed or not configured
    if equipment_list is None:
        equipment_list = _load_from_csv()
    
    # Update cache
    _equipment_cache = equipment_list
    _cache_timestamp = current_time
    
    return equipment_list


def get_available_equipment():
    """
    Get only equipment with status 'AVAILABLE'.
    Filters out RENTED, MAINTENANCE, and RESERVED equipment.
    """
    all_equipment = load_equipment()
    
    available = [
        item for item in all_equipment 
        if str(item.get('Status', '')).upper() == 'AVAILABLE'
    ]
    
    logger.info(f"Found {len(available)} available equipment items")
    return available


def get_available_equipment_summary():
    """
    Get a concise summary of available equipment for the system prompt.
    Returns a formatted string listing categories and count, not full details.
    """
    available = get_available_equipment()
    
    if not available:
        return "No equipment currently available."
    
    # Group by category
    categories = {}
    for item in available:
        category = item.get('Category', 'Unknown')
        if category not in categories:
            categories[category] = []
        categories[category].append(item.get('Equipment ID'))
    
    # Build summary string
    summary_lines = [f"We have {len(available)} pieces of equipment available:"]
    for category, ids in sorted(categories.items()):
        summary_lines.append(f"  - {category}: {', '.join(ids)} ({len(ids)} items)")
    
    summary_lines.append("\nUse get_equipment_details_tool(equipment_id) to show specific equipment details to customers.")
    
    return "\n".join(summary_lines)


def get_equipment_by_id(equipment_id: str) -> Optional[Dict]:
    """
    Get specific equipment by ID (e.g., "EQ001").
    Returns None if not found.
    """
    all_equipment = load_equipment()
    
    for item in all_equipment:
        if item.get('Equipment ID') == equipment_id:
            logger.info(f"Found equipment: {equipment_id}")
            return item
    
    logger.warning(f"Equipment not found: {equipment_id}")
    return None


def _update_google_sheets_status(equipment_id: str, new_status: str) -> bool:
    """
    Update equipment status in Google Sheets.
    Returns True if successful, False otherwise.
    """
    try:
        client = _get_google_sheets_client()
        if not client:
            return False
        
        sheet = client.open_by_key(config.EQUIPMENT_SHEET_ID)
        worksheet = sheet.worksheet(config.EQUIPMENT_SHEET_NAME)
        
        # Find the row with this equipment ID
        cell = worksheet.find(equipment_id)
        if not cell:
            logger.error(f"Equipment {equipment_id} not found in Google Sheets")
            return False
        
        # Get current status (Status column is typically column 5)
        current_status = worksheet.cell(cell.row, 5).value
        
        # Race condition check
        if new_status == 'RENTED':
            if current_status != 'AVAILABLE':
                logger.warning(f"Cannot rent {equipment_id}: status is {current_status}, not AVAILABLE")
                return False
        
        # Update the status
        worksheet.update_cell(cell.row, 5, new_status)
        logger.info(f"Updated {equipment_id} in Google Sheets: {current_status} -> {new_status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating Google Sheets: {e}")
        return False


def _update_csv_status(equipment_id: str, new_status: str) -> bool:
    """
    Update equipment status in CSV file.
    Returns True if successful, False otherwise.
    """
    try:
        csv_path = Path(config.EQUIPMENT_CSV_PATH)
        df = pd.read_csv(csv_path)
        equipment_row = df[df['Equipment ID'] == equipment_id]
        
        if equipment_row.empty:
            logger.error(f"Equipment {equipment_id} not found in CSV")
            return False
        
        current_status = equipment_row.iloc[0]['Status']
        
        # Race condition check
        if new_status == 'RENTED':
            if current_status != 'AVAILABLE':
                logger.warning(f"Cannot rent {equipment_id}: status is {current_status}, not AVAILABLE")
                return False
        
        df.loc[df['Equipment ID'] == equipment_id, 'Status'] = new_status
        df.to_csv(csv_path, index=False)
        logger.info(f"Updated {equipment_id}: {current_status} -> {new_status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating CSV: {e}")
        return False


def update_equipment_status(equipment_id: str, new_status: str) -> bool:
    """
    Update equipment status in Google Sheets (if configured) or CSV fallback.
    Handles race conditions by checking status before updating.
    Invalidates cache after successful update.
    Returns True if successful, False if equipment was already taken.
    """
    global _equipment_cache, _cache_timestamp
    
    # Try Google Sheets first
    if _get_google_sheets_client():
        success = _update_google_sheets_status(equipment_id, new_status)
        if success:
            # Also update CSV as backup
            _update_csv_status(equipment_id, new_status)
            # Invalidate cache so next load gets fresh data
            _equipment_cache = None
            _cache_timestamp = 0
            logger.debug(f"Cache invalidated after status update for {equipment_id}")
        return success
    else:
        # Fallback to CSV only
        success = _update_csv_status(equipment_id, new_status)
        if success:
            # Invalidate cache
            _equipment_cache = None
            _cache_timestamp = 0
            logger.debug(f"Cache invalidated after status update for {equipment_id}")
        return success
