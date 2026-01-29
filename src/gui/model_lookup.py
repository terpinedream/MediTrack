"""
Model lookup utility for mapping FAA model codes to model names and manufacturers.

Loads ACFTREF.txt file on demand and provides fast lookup of model information.
"""

import csv
from pathlib import Path
from typing import Dict, Optional
import sys

# Add project root to path for config import
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import config
    FAA_DATA_DIR = config.FAA_DATA_DIR
except (ImportError, AttributeError):
    # Fallback if config not available
    FAA_DATA_DIR = project_root / "ReleasableAircraft"


class ModelLookup:
    """
    Utility class for looking up aircraft model information from ACFTREF database.
    
    Provides lazy loading and caching of model code to model name/manufacturer mappings.
    """
    
    def __init__(self, acftref_path: Optional[Path] = None):
        """
        Initialize model lookup.
        
        Args:
            acftref_path: Path to ACFTREF.txt file. If None, uses default from config.
        """
        if acftref_path is None:
            try:
                acftref_path = config.FAA_DATA_DIR / "ACFTREF.txt"
            except (NameError, AttributeError):
                # Fallback if config not available
                acftref_path = FAA_DATA_DIR / "ACFTREF.txt"
        
        self.acftref_path = acftref_path
        self.lookup_cache: Dict[str, Dict[str, str]] = {}
        self._loaded = False
    
    def _load_acftref(self):
        """Load ACFTREF.txt file and build lookup dictionary."""
        if self._loaded:
            return
        
        if not self.acftref_path.exists():
            # ACFTREF file not found - lookup will return None
            self._loaded = True
            return
        
        try:
            with open(self.acftref_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if not reader.fieldnames:
                    self._loaded = True
                    return
                
                # Find the actual column keys (handle BOM and variations)
                code_key = None
                mfr_key = None
                model_key = None
                
                for key in reader.fieldnames:
                    if key:
                        key_clean = key.strip().lstrip('\ufeff')  # Remove BOM
                        if key_clean == 'CODE':
                            code_key = key
                        elif key_clean == 'MFR':
                            mfr_key = key
                        elif key_clean == 'MODEL':
                            model_key = key
                
                # Fallback: use first few columns if standard names not found
                if not code_key:
                    valid_keys = [k for k in reader.fieldnames if k and k.strip()]
                    if len(valid_keys) >= 3:
                        code_key = valid_keys[0]
                        mfr_key = valid_keys[1] if not mfr_key else mfr_key
                        model_key = valid_keys[2] if not model_key else model_key
                    else:
                        # Can't parse file - mark as loaded to avoid retrying
                        self._loaded = True
                        return
                
                # Build lookup dictionary
                for row in reader:
                    code = row.get(code_key, '').strip() if code_key else ''
                    if not code:
                        continue
                    
                    mfr = row.get(mfr_key, '').strip() if mfr_key else ''
                    model = row.get(model_key, '').strip() if model_key else ''
                    
                    self.lookup_cache[code] = {
                        'manufacturer': mfr,
                        'model': model
                    }
            
            self._loaded = True
        
        except Exception as e:
            # Error loading file - mark as loaded to avoid retrying
            self._loaded = True
            # Silently fail - lookup will return None
    
    def lookup(self, model_code: str) -> Optional[Dict[str, str]]:
        """
        Look up model information for a given model code.
        
        Args:
            model_code: FAA model code (e.g., "8680615")
        
        Returns:
            Dictionary with 'manufacturer' and 'model' keys, or None if not found
        """
        if not model_code or not model_code.strip():
            return None
        
        # Ensure ACFTREF is loaded
        if not self._loaded:
            self._load_acftref()
        
        # Look up in cache
        model_code_clean = model_code.strip()
        return self.lookup_cache.get(model_code_clean)
    
    def get_model_name(self, model_code: str) -> Optional[str]:
        """
        Get model name for a given model code.
        
        Args:
            model_code: FAA model code
        
        Returns:
            Model name string, or None if not found
        """
        info = self.lookup(model_code)
        if info:
            return info.get('model')
        return None
    
    def get_manufacturer(self, model_code: str) -> Optional[str]:
        """
        Get manufacturer for a given model code.
        
        Args:
            model_code: FAA model code
        
        Returns:
            Manufacturer name string, or None if not found
        """
        info = self.lookup(model_code)
        if info:
            return info.get('manufacturer')
        return None
    
    def is_loaded(self) -> bool:
        """Check if ACFTREF has been loaded."""
        return self._loaded
    
    def get_cache_size(self) -> int:
        """Get number of entries in lookup cache."""
        return len(self.lookup_cache)
