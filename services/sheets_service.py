"""
Equipment data service - handles reading/writing equipment inventory.
Supports both CSV files and Google Sheets.
"""

import pandas as pd
import logging
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

# Global variable to cache the Google Sheets client
_sheets_client = None


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
    
    if not config.GOOGLE_SERVICE_ACCOUNT_FILE or not config.EQUIPMENT_SHEET_ID:
        logger.info("Google Sheets not configured, using CSV fallback")
        return None
    
    try:
        # Define the scope for Google Sheets API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Load credentials from service account file
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=scopes
        )
        
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
    Returns list of equipment dictionaries.
    """
    # Try Google Sheets first
    equipment_list = _load_from_google_sheets()
    
    # Fallback to CSV if Google Sheets failed or not configured
    if equipment_list is None:
        equipment_list = _load_from_csv()
    
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
    Returns True if successful, False if equipment was already taken.
    """
    # Try Google Sheets first
    if _get_google_sheets_client():
        success = _update_google_sheets_status(equipment_id, new_status)
        if success:
            # Also update CSV as backup
            _update_csv_status(equipment_id, new_status)
        return success
    else:
        # Fallback to CSV only
        return _update_csv_status(equipment_id, new_status)
