package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

const baseURL = "https://transport.integration.sl.se/v1"

// Journey holds journey state information.
type Journey struct {
	ID              int    `json:"id"`
	State           string `json:"state"`
	PredictionState string `json:"prediction_state"`
	PassengerLevel  string `json:"passenger_level"`
}

// StopArea holds stop area information.
type StopArea struct {
	ID    int    `json:"id"`
	Name  string `json:"name"`
	SName string `json:"sname"`
	Type  string `json:"type"`
}

// StopPoint holds stop point information.
type StopPoint struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Designation string `json:"designation"`
}

// Line holds line information.
type Line struct {
	ID            int    `json:"id"`
	Designation   string `json:"designation"`
	TransportMode string `json:"transport_mode"`
	GroupOfLines  string `json:"group_of_lines"`
}

// Deviation holds disruption information.
type Deviation struct {
	ImportanceLevel int    `json:"importance_level"`
	Consequence     string `json:"consequence"`
	Message         string `json:"message"`
}

// Departure holds a single departure entry.
type Departure struct {
	Direction     string      `json:"direction"`
	DirectionCode int         `json:"direction_code"`
	Destination   string      `json:"destination"`
	Display       string      `json:"display"`
	State         string      `json:"state"`
	Scheduled     string      `json:"scheduled"`
	Expected      string      `json:"expected"`
	Via           string      `json:"via"`
	Journey       *Journey    `json:"journey"`
	StopArea      *StopArea   `json:"stop_area"`
	StopPoint     *StopPoint  `json:"stop_point"`
	Line          *Line       `json:"line"`
	Deviations    []Deviation `json:"deviations"`
}

// StopDeviation holds stop-level deviation info.
type StopDeviation struct {
	ID              int    `json:"id"`
	ImportanceLevel int    `json:"importance_level"`
	Message         string `json:"message"`
}

// DeparturesResponse is the full API response.
type DeparturesResponse struct {
	Departures     []Departure     `json:"departures"`
	StopDeviations []StopDeviation `json:"stop_deviations"`
	StopName       string
}

// SLApi is the HTTP client for the SL Transport API.
type SLApi struct {
	client *http.Client
}

// NewSLApi creates a new SLApi client.
func NewSLApi() *SLApi {
	return &SLApi{
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// GetDepartures fetches departures for a given site ID and transport mode.
func (a *SLApi) GetDepartures(siteID int, transport string) (*DeparturesResponse, error) {
	url := fmt.Sprintf("%s/sites/%d/departures?transport=%s", baseURL, siteID, transport)

	resp, err := a.client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("http get: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status: %s", resp.Status)
	}

	var raw struct {
		Departures     []Departure     `json:"departures"`
		StopDeviations []StopDeviation `json:"stop_deviations"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return nil, fmt.Errorf("decode json: %w", err)
	}

	result := &DeparturesResponse{
		Departures:     raw.Departures,
		StopDeviations: raw.StopDeviations,
	}

	// Extract stop name from first departure
	if len(raw.Departures) > 0 && raw.Departures[0].StopArea != nil {
		result.StopName = raw.Departures[0].StopArea.Name
	}

	return result, nil
}
