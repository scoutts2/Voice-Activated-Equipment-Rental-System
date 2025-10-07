"""
Equipment data service - handles reading/writing equipment inventory.
Supports both CSV files and Google Sheets.
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from pathlib import Path
from config import config

logger = logging.getLogger(__name__)


def load_equipment() -> List[Dict]:
    """
    Load all equipment from CSV file into memory.
    Returns list of equipment dictionaries.
    """
    try:
        csv_path = Path(config.EQUIPMENT_CSV_PATH)
        
        if not csv_path.exists():
            logger.error(f"Equipment CSV not found at {csv_path}")
            return []
        

        df = pd.read_csv(csv_path)
        # Convert to list of dictionaries
        equipment_list = df.to_dict('records')
        
        logger.info(f"Loaded {len(equipment_list)} equipment items from CSV")
        return equipment_list
        
    except Exception as e:
        logger.error(f"Error loading equipment: {e}")
        return []


def get_available_equipment():
    """
    Get only equipment with status 'AVAILABLE'.
    Filters out RENTED, MAINTENANCE, and RESERVED equipment.
    """
    all_equipment = load_equipment()
    
    available = [
        item for item in all_equipment 
        if item.get('Status', '').upper() == 'AVAILABLE'
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


def update_equipment_status(equipment_id: str, new_status: str):
    """
    Update equipment status in CSV (e.g., AVAILABLE -> RENTED).
    
    Handles race conditions by checking status before updating.
    Returns True if successful, False if equipment was already taken.
    """
    try:
        csv_path = Path(config.EQUIPMENT_CSV_PATH)
        df = pd.read_csv(csv_path)
        equipment_row = df[df['Equipment ID'] == equipment_id]
        
        if equipment_row.empty:
            logger.error(f"Equipment {equipment_id} not found in CSV")
            return False
        
        current_status = equipment_row.iloc[0]['Status']
        
        # RACE CONDITION PROTECTION:
        # When trying to book equipment (set to RENTED), verify it's still AVAILABLE
        # If not, another customer just booked it during our conversation
        if new_status == 'RENTED':
            if current_status != 'AVAILABLE':
                logger.warning(f"Cannot rent {equipment_id}: status is {current_status}, not AVAILABLE (race condition)")
                return False
        
        # Update status
        df.loc[df['Equipment ID'] == equipment_id, 'Status'] = new_status
        
        # Write back to CSV
        df.to_csv(csv_path, index=False)
        
        logger.info(f"Updated {equipment_id}: {current_status} -> {new_status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating equipment status: {e}")
        return False
