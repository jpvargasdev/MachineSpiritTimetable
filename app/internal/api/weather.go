package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// WeatherCondition holds weather condition info.
type WeatherCondition struct {
	ID          int    `json:"id"`
	Main        string `json:"main"`
	Description string `json:"description"`
	Icon        string `json:"icon"`
}

// CurrentWeather holds current weather data.
type CurrentWeather struct {
	Dt         int64              `json:"dt"`
	Sunrise    int64              `json:"sunrise"`
	Sunset     int64              `json:"sunset"`
	Temp       float64            `json:"temp"`
	FeelsLike  float64            `json:"feels_like"`
	Pressure   int                `json:"pressure"`
	Humidity   int                `json:"humidity"`
	DewPoint   float64            `json:"dew_point"`
	UVI        float64            `json:"uvi"`
	Clouds     int                `json:"clouds"`
	Visibility int                `json:"visibility"`
	WindSpeed  float64            `json:"wind_speed"`
	WindDeg    int                `json:"wind_deg"`
	WindGust   float64            `json:"wind_gust"`
	Weather    []WeatherCondition `json:"weather"`
}

// MinutelyWeather holds minute-by-minute precipitation data.
type MinutelyWeather struct {
	Dt            int64   `json:"dt"`
	Precipitation float64 `json:"precipitation"`
}

// HourlyWeather holds hourly forecast data.
type HourlyWeather struct {
	Dt         int64              `json:"dt"`
	Temp       float64            `json:"temp"`
	FeelsLike  float64            `json:"feels_like"`
	Pressure   int                `json:"pressure"`
	Humidity   int                `json:"humidity"`
	DewPoint   float64            `json:"dew_point"`
	UVI        float64            `json:"uvi"`
	Clouds     int                `json:"clouds"`
	Visibility int                `json:"visibility"`
	WindSpeed  float64            `json:"wind_speed"`
	WindDeg    int                `json:"wind_deg"`
	WindGust   float64            `json:"wind_gust"`
	Weather    []WeatherCondition `json:"weather"`
	Pop        float64            `json:"pop"`
}

// DailyTemp holds daily temperature data.
type DailyTemp struct {
	Day   float64 `json:"day"`
	Min   float64 `json:"min"`
	Max   float64 `json:"max"`
	Night float64 `json:"night"`
	Eve   float64 `json:"eve"`
	Morn  float64 `json:"morn"`
}

// DailyFeelsLike holds daily feels-like temperature data.
type DailyFeelsLike struct {
	Day   float64 `json:"day"`
	Night float64 `json:"night"`
	Eve   float64 `json:"eve"`
	Morn  float64 `json:"morn"`
}

// DailyWeather holds daily forecast data.
type DailyWeather struct {
	Dt        int64              `json:"dt"`
	Sunrise   int64              `json:"sunrise"`
	Sunset    int64              `json:"sunset"`
	Moonrise  int64              `json:"moonrise"`
	Moonset   int64              `json:"moonset"`
	MoonPhase float64            `json:"moon_phase"`
	Summary   string             `json:"summary"`
	Temp      DailyTemp          `json:"temp"`
	FeelsLike DailyFeelsLike     `json:"feels_like"`
	Pressure  int                `json:"pressure"`
	Humidity  int                `json:"humidity"`
	DewPoint  float64            `json:"dew_point"`
	WindSpeed float64            `json:"wind_speed"`
	WindDeg   int                `json:"wind_deg"`
	WindGust  float64            `json:"wind_gust"`
	Weather   []WeatherCondition `json:"weather"`
	Clouds    int                `json:"clouds"`
	Pop       float64            `json:"pop"`
	Rain      float64            `json:"rain"`
	UVI       float64            `json:"uvi"`
}

// WeatherAlert holds weather alert data.
type WeatherAlert struct {
	SenderName  string   `json:"sender_name"`
	Event       string   `json:"event"`
	Start       int64    `json:"start"`
	End         int64    `json:"end"`
	Description string   `json:"description"`
	Tags        []string `json:"tags"`
}

// WeatherResponse is the full OpenWeather One Call API response.
type WeatherResponse struct {
	Lat            float64           `json:"lat"`
	Lon            float64           `json:"lon"`
	Timezone       string            `json:"timezone"`
	TimezoneOffset int               `json:"timezone_offset"`
	Current        CurrentWeather    `json:"current"`
	Minutely       []MinutelyWeather `json:"minutely"`
	Hourly         []HourlyWeather   `json:"hourly"`
	Daily          []DailyWeather    `json:"daily"`
	Alerts         []WeatherAlert    `json:"alerts"`
}

// WeatherApi is the HTTP client for the OpenWeather API.
type WeatherApi struct {
	client *http.Client
	apiKey string
}

// NewWeatherApi creates a new WeatherApi client.
func NewWeatherApi(apiKey string) *WeatherApi {
	return &WeatherApi{
		client: &http.Client{Timeout: 10 * time.Second},
		apiKey: apiKey,
	}
}

// ConditionToIcon maps OpenWeather condition ID to icon name.
// See https://openweathermap.org/weather-conditions for full list.
func ConditionToIcon(id int) string {
	switch {
	case id >= 200 && id < 300:
		// Thunderstorm
		return "rain"
	case id >= 300 && id < 400:
		// Drizzle
		return "rain"
	case id >= 500 && id < 600:
		// Rain
		return "rain"
	case id >= 600 && id < 700:
		// Snow
		return "snow"
	case id >= 700 && id < 800:
		// Atmosphere (mist, fog, etc) - use cloud
		return "cloud"
	case id == 800:
		// Clear
		return "sun"
	case id >= 801 && id < 900:
		// Clouds
		return "cloud"
	default:
		return "sun"
	}
}

// GetWeather fetches current weather and forecast for given coordinates.
func (w *WeatherApi) GetWeather(lat, lon float64) (*WeatherResponse, error) {
	url := fmt.Sprintf(
		"https://api.openweathermap.org/data/3.0/onecall?lat=%f&lon=%f&appid=%s&units=metric",
		lat, lon, w.apiKey,
	)

	resp, err := w.client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("weather request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("weather API returned status %d", resp.StatusCode)
	}

	var result WeatherResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode weather response: %w", err)
	}

	return &result, nil
}
