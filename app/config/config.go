package config

import (
	"log"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

func Load() {
	err := godotenv.Load()
	if err != nil {
		log.Println("No .env file found, relying on environment variables")
	}
}

func WeatherKey() string {
	return os.Getenv("WEATHER_KEY")
}

func Latitude() float64 {
	val, err := strconv.ParseFloat(os.Getenv("LATITUDE"), 64)
	if err != nil {
		return 0
	}
	return val
}

func Longitude() float64 {
	val, err := strconv.ParseFloat(os.Getenv("LONGITUDE"), 64)
	if err != nil {
		return 0
	}
	return val
}
