"""Format departures for LED display."""

from datetime import datetime
from domain.api import DeparturesResponse, Departure


def calculate_minutes_until(departure: Departure) -> int | None:
    """Calculate minutes until departure based on expected or scheduled time.
    
    Args:
        departure: Departure object
        
    Returns:
        Minutes until departure, or None if can't calculate
    """
    # Use expected time if available, otherwise scheduled
    time_str = departure.expected or departure.scheduled
    if not time_str:
        return None
    
    try:
        # Parse ISO format: "2024-01-01T01:00:00"
        dep_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        now = datetime.now(dep_time.tzinfo) if dep_time.tzinfo else datetime.now()
        
        diff = dep_time - now
        minutes = int(diff.total_seconds() / 60)
        return max(0, minutes)  # Don't show negative
    except (ValueError, TypeError):
        return None


def format_departure_time(departure: Departure) -> str:
    """Format departure time as 'Xmin' or 'NOW'.
    
    Args:
        departure: Departure object
        
    Returns:
        Formatted time string
    """
    minutes = calculate_minutes_until(departure)
    
    if minutes is None:
        # Fallback to display field
        time = departure.display
        if time == "Nu":
            return "NOW"
        return time
    
    if minutes == 0:
        return "NOW"
    return f"{minutes}min"


def format_departures(response: DeparturesResponse, max_items: int = 3) -> str:
    """Format departures for LED display.
    
    Args:
        response: DeparturesResponse from API
        max_items: Maximum number of departures to show
        
    Returns:
        Formatted string for display (e.g., "13 Ropsten 3min  18 Alvik 5min")
    """
    if not response.departures:
        return "No departures"
    
    parts = []
    for dep in response.departures[:max_items]:
        # Get line designation
        line = dep.line.designation if dep.line else "?"
        
        # Shorten destination if too long
        dest = dep.destination
        if len(dest) > 10:
            dest = dest[:9] + "."
        
        # Calculate time from expected/scheduled
        time = format_departure_time(dep)
        
        parts.append(f"{line} {dest} {time}")
    
    return "  ".join(parts)


def format_destination_time(departure: Departure) -> str:
    """Format as 'Destination - display'.
    
    Args:
        departure: Departure object
        
    Returns:
        Formatted string (e.g., "Ropsten - 3 min")
    """
    return f"{departure.destination} - {departure.display}"


def format_two_lines(departure: Departure) -> tuple[str, str]:
    """Format departure as two separate lines.
    
    Args:
        departure: Departure object
        
    Returns:
        Tuple of (destination, display_time) e.g., ("Ropsten", "3 min")
    """
    return (departure.destination, departure.display)


def format_single_departure(response: DeparturesResponse, index: int = 0) -> str:
    """Format a single departure for LED display.
    
    Args:
        response: DeparturesResponse from API
        index: Which departure to show (0 = next)
        
    Returns:
        Formatted string (e.g., "13 Ropsten 3 min")
    """
    if not response.departures or index >= len(response.departures):
        return "---"
    
    dep = response.departures[index]
    line = dep.line.designation if dep.line else "?"
    return f"{line} {dep.destination} {dep.display}"
