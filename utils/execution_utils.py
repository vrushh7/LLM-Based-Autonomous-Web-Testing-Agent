# utils/execution_utils.py
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class ExecutionContext:
    """Execution context for test runs."""
    test_folder: Optional[Path] = None
    downloads_folder: Optional[Path] = None
    screenshots_folder: Optional[Path] = None
    instruction: str = ""
    current_url: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _make_test_folder_name(instruction: str, max_length: int = 50) -> str:
    """Create a safe folder name from instruction."""
    if not instruction:
        return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Sanitize instruction
    safe_name = re.sub(r'[^\w\s\-]', '', instruction.lower())
    safe_name = re.sub(r'[\s\-]+', '_', safe_name.strip())
    
    # Truncate if too long
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]
    
    # Add timestamp for uniqueness
    timestamp = datetime.now().strftime('%H%M%S')
    return f"{safe_name}_{timestamp}"


def _create_run_dirs(folder_name: str, base_dir: Path = Path("test_runs")) -> Dict[str, Path]:
    """Create run directories for test execution."""
    root_dir = base_dir / folder_name
    screenshots_dir = root_dir / "screenshots"
    downloads_dir = root_dir / "downloads"
    logs_dir = root_dir / "logs"
    
    for dir_path in [root_dir, screenshots_dir, downloads_dir, logs_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return {
        "root": root_dir,
        "screenshots": screenshots_dir,
        "downloads": downloads_dir,
        "logs": logs_dir,
    }