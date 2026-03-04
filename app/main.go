package main

import (
	"log"

  "xyaod/config"
)

func main() {
  config.Load()
	log.Println("Hello, World!")
}
