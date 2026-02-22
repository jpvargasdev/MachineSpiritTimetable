"""SL Transport API client."""

import aiohttp
from dataclasses import dataclass, field
from typing import Optional


BASE_URL = "https://transport.integration.sl.se/v1"


# ── Data models ──────────────────────────────────────────────────────

@dataclass
class Journey:
    """Journey information."""
    id: int
    state: str  # NOTEXPECTED, EXPECTED, etc.
    prediction_state: str  # NORMAL, etc.
    passenger_level: str  # EMPTY, LOW, MEDIUM, HIGH


@dataclass
class StopArea:
    """Stop area information."""
    id: int
    name: str
    sname: Optional[str] = None
    type: str = ""  # BUSTERM, METROSTN, etc.


@dataclass
class StopPoint:
    """Stop point information."""
    id: int
    name: str
    designation: str = ""


@dataclass
class Line:
    """Line information."""
    id: int
    designation: str  # e.g., "13X", "17"
    transport_mode: str  # BUS, METRO, TRAIN, TRAM, SHIP
    group_of_lines: str = ""


@dataclass
class Deviation:
    """Deviation/disruption information."""
    importance_level: int
    consequence: str  # INFORMATION, CANCELLED, etc.
    message: str


@dataclass
class Departure:
    """A single departure."""
    direction: str
    direction_code: int
    destination: str
    display: str  # e.g., "3 min", "Nu", "10:45"
    state: str  # NOTEXPECTED, EXPECTED, etc.
    scheduled: Optional[str] = None
    expected: Optional[str] = None
    via: Optional[str] = None
    journey: Optional[Journey] = None
    stop_area: Optional[StopArea] = None
    stop_point: Optional[StopPoint] = None
    line: Optional[Line] = None
    deviations: list[Deviation] = field(default_factory=list)


@dataclass
class StopDeviation:
    """Stop-level deviation information."""
    id: int
    importance_level: int
    message: str


@dataclass
class DeparturesResponse:
    """Response from departures endpoint."""
    departures: list[Departure] = field(default_factory=list)
    stop_deviations: list[StopDeviation] = field(default_factory=list)
    stop_name: Optional[str] = None


# ── API Client ───────────────────────────────────────────────────────

class SLApi:
    """Client for SL Transport API."""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_departures(
        self, 
        site_id: int,
        transport: str = "METRO"
    ) -> DeparturesResponse:
        """Get departures for a site.
        
        Args:
            site_id: SL site ID (e.g., 9192 for T-Centralen)
            transport: Transport type (METRO, BUS, TRAIN, TRAM, SHIP)
            
        Returns:
            DeparturesResponse with list of departures
        """
        session = await self._get_session()
        
        url = f"{BASE_URL}/sites/{site_id}/departures"
        params = {"transport": transport}
        
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()
        
        departures = []
        stop_name = None
        
        for dep in data.get("departures", []):
            # Extract stop name from first departure
            if stop_name is None:
                stop_area_data = dep.get("stop_area", {})
                stop_name = stop_area_data.get("name")
            
            # Parse journey
            journey_data = dep.get("journey")
            journey = None
            if journey_data:
                journey = Journey(
                    id=journey_data.get("id", 0),
                    state=journey_data.get("state", ""),
                    prediction_state=journey_data.get("prediction_state", ""),
                    passenger_level=journey_data.get("passenger_level", "")
                )
            
            # Parse stop_area
            stop_area_data = dep.get("stop_area")
            stop_area = None
            if stop_area_data:
                stop_area = StopArea(
                    id=stop_area_data.get("id", 0),
                    name=stop_area_data.get("name", ""),
                    sname=stop_area_data.get("sname"),
                    type=stop_area_data.get("type", "")
                )
            
            # Parse stop_point
            stop_point_data = dep.get("stop_point")
            stop_point = None
            if stop_point_data:
                stop_point = StopPoint(
                    id=stop_point_data.get("id", 0),
                    name=stop_point_data.get("name", ""),
                    designation=stop_point_data.get("designation", "")
                )
            
            # Parse line
            line_data = dep.get("line")
            line = None
            if line_data:
                line = Line(
                    id=line_data.get("id", 0),
                    designation=line_data.get("designation", "?"),
                    transport_mode=line_data.get("transport_mode", transport),
                    group_of_lines=line_data.get("group_of_lines", "")
                )
            
            # Parse deviations
            deviations = []
            for dev in dep.get("deviations", []):
                deviations.append(Deviation(
                    importance_level=dev.get("importance_level", 0),
                    consequence=dev.get("consequence", ""),
                    message=dev.get("message", "")
                ))
            
            departures.append(Departure(
                direction=dep.get("direction", ""),
                direction_code=dep.get("direction_code", 0),
                destination=dep.get("destination", "Unknown"),
                display=dep.get("display", "?"),
                state=dep.get("state", ""),
                scheduled=dep.get("scheduled"),
                expected=dep.get("expected"),
                via=dep.get("via"),
                journey=journey,
                stop_area=stop_area,
                stop_point=stop_point,
                line=line,
                deviations=deviations
            ))
        
        # Parse stop_deviations
        stop_deviations = []
        for sd in data.get("stop_deviations", []):
            stop_deviations.append(StopDeviation(
                id=sd.get("id", 0),
                importance_level=sd.get("importance_level", 0),
                message=sd.get("message", "")
            ))
        
        return DeparturesResponse(
            departures=departures,
            stop_deviations=stop_deviations,
            stop_name=stop_name
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()
