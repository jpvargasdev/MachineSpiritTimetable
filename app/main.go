package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/spf13/cobra"

	"xyaod/internal/api"
	"xyaod/internal/bitmap"
	"xyaod/internal/display"
)

const defaultSiteID = 9293

func main() {
	root := &cobra.Command{
		Use:   "xyaod",
		Short: "Display SL departures or custom text on XyaoLED",
	}

	// ── departure mode ─────────────────────────────────────────────────
	var (
		siteID   int
		interval int
		font     string
		color    string
		scroll   bool
		preview  bool
		address  string
	)

	departureCmd := &cobra.Command{
		Use:   "site",
		Short: "Display SL departures",
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
			defer stop()
			return runDepartures(ctx, siteID, interval, color, font, scroll, preview, address)
		},
	}
	departureCmd.Flags().IntVarP(&siteID, "site", "s", defaultSiteID, "SL site ID")
	departureCmd.Flags().IntVarP(&interval, "interval", "i", 30, "API refresh interval in seconds")
	departureCmd.Flags().StringVarP(&font, "font", "f", "small", "Font size: small, medium, large")
	departureCmd.Flags().StringVarP(&color, "color", "c", "red", fmt.Sprintf("Display color %v", colorNames()))
	departureCmd.Flags().BoolVar(&scroll, "scroll", false, "Enable scrolling animation")
	departureCmd.Flags().BoolVarP(&preview, "preview", "p", false, "Preview only (don't send to device)")
	departureCmd.Flags().StringVar(&address, "address", "", "BLE device address (default: built-in)")

	// ── text mode ──────────────────────────────────────────────────────
	var (
		text       string
		size       string
		speed      int
		brightness int
		tColor     string
		tScroll    bool
		tPreview   bool
		tAddress   string
	)

	textCmd := &cobra.Command{
		Use:   "text",
		Short: "Display custom text",
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
			defer stop()
			return runText(ctx, text, tColor, size, tScroll, tPreview, tAddress, uint8(speed), uint8(brightness))
		},
	}
	textCmd.Flags().StringVarP(&text, "text", "t", "", "Text to display")
	textCmd.MarkFlagRequired("text")
	textCmd.Flags().StringVarP(&tColor, "color", "c", "red", fmt.Sprintf("Display color %v", colorNames()))
	textCmd.Flags().StringVarP(&size, "size", "s", "small", "Font size: small, large")
	textCmd.Flags().BoolVar(&tScroll, "scroll", false, "Enable scrolling animation")
	textCmd.Flags().BoolVarP(&tPreview, "preview", "p", false, "Preview only (don't send to device)")
	textCmd.Flags().IntVar(&speed, "speed", 60, "Scroll speed 1-255")
	textCmd.Flags().IntVar(&brightness, "brightness", 255, "Brightness 0-255")
	textCmd.Flags().StringVar(&tAddress, "address", "", "BLE device address (default: built-in)")

	root.AddCommand(departureCmd, textCmd)

	if err := root.Execute(); err != nil {
		os.Exit(1)
	}
}

// ── departure display loop ─────────────────────────────────────────────────

type destination struct {
	name    string
	seconds int
}

var destinations = []destination{
	{"Ropsten", 10},
	{"Norsborg", 5},
}

func runDepartures(ctx context.Context, siteID, interval int, color, font string, scroll, preview bool, address string) error {
	slApi := api.NewSLApi()

	var screen *display.Screen
	if !preview {
		screen = display.NewScreen(address)
		log.Println("Connecting to LED display...")
		if err := screen.Connect(); err != nil {
			return fmt.Errorf("connect: %w", err)
		}
		log.Println("Connected!")
		defer func() {
			screen.Disconnect()
			log.Println("Disconnected.")
		}()
	}

	log.Printf("Fetching departures for site %d every %ds\n", siteID, interval)

	var cachedResp *api.DeparturesResponse
	var lastFetch time.Time

	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		// Refresh cache if expired
		if cachedResp == nil || time.Since(lastFetch) >= time.Duration(interval)*time.Second {
			log.Println("Fetching departures...")
			resp, err := slApi.GetDepartures(siteID, "METRO")
			if err != nil {
				log.Printf("API error: %v — retrying in 5s\n", err)
				select {
				case <-ctx.Done():
					return nil
				case <-time.After(5 * time.Second):
				}
				continue
			}
			cachedResp = resp
			lastFetch = time.Now()
			log.Printf("Got %d departures\n", len(cachedResp.Departures))
		}

		// Group by destination
		byDest := map[string][]api.Departure{}
		for _, d := range cachedResp.Departures {
			byDest[d.Destination] = append(byDest[d.Destination], d)
		}

		// Cycle through destinations
		for _, dest := range destinations {
			select {
			case <-ctx.Done():
				return nil
			default:
			}

			deps := byDest[dest.name]
			var line1, line2 string

			switch font {
			case "large":
				if len(deps) > 0 {
					line1 = fmt.Sprintf("%s %s", dest.name, deps[0].Display)
				} else {
					line1 = fmt.Sprintf("%s --", dest.name)
				}
				log.Printf("[%s] %s\n", dest.name, line1)
				if preview {
					ascii, _ := display.NewScreen("").Render(line1, color, scroll, 60, 255, 1, true)
					fmt.Println(ascii)
				} else if screen != nil {
					if _, err := screen.Render(line1, color, scroll, 60, 255, 1, false); err != nil {
						log.Printf("render error: %v\n", err)
					}
				}

			case "medium":
				line1 = dest.name
				switch len(deps) {
				case 0:
					line2 = "--"
				case 1:
					line2 = deps[0].Display
				default:
					line2 = fmt.Sprintf("%s - %s", deps[0].Display, deps[1].Display)
				}
				log.Printf("[%s] %s | %s\n", dest.name, line1, line2)
				if preview {
					ascii, _ := display.NewScreen("").RenderTwoLines(line1, line2, color, scroll, 60, 255, true, true)
					fmt.Println(ascii)
				} else if screen != nil {
					if _, err := screen.RenderTwoLines(line1, line2, color, scroll, 60, 255, true, false); err != nil {
						log.Printf("render error: %v\n", err)
					}
				}

			default: // small
				switch len(deps) {
				case 0:
					line1, line2 = dest.name, "No departures"
				case 1:
					line1, line2 = fmt.Sprintf("%s %s", dest.name, deps[0].Display), ""
				default:
					line1 = fmt.Sprintf("%s %s", dest.name, deps[0].Display)
					line2 = fmt.Sprintf("%s %s", dest.name, deps[1].Display)
				}
				log.Printf("[%s] %s | %s\n", dest.name, line1, line2)
				if preview {
					ascii, _ := display.NewScreen("").RenderTwoLines(line1, line2, color, scroll, 60, 255, false, true)
					fmt.Println(ascii)
				} else if screen != nil {
					if _, err := screen.RenderTwoLines(line1, line2, color, scroll, 60, 255, false, false); err != nil {
						log.Printf("render error: %v\n", err)
					}
				}
			}

			// Wait display duration, checking for cancel every second
			for i := 0; i < dest.seconds; i++ {
				select {
				case <-ctx.Done():
					return nil
				case <-time.After(time.Second):
				}
			}
		}
	}
}

// ── text mode ──────────────────────────────────────────────────────────────

func runText(_ context.Context, text, color, size string, scroll, preview bool, address string, speed, brightness uint8) error {
	scale := 1
	if size == "large" {
		scale = 2
	}

	if preview {
		s := display.NewScreen("")
		ascii, err := s.Render(text, color, scroll, speed, brightness, scale, true)
		if err != nil {
			return err
		}
		fmt.Printf("Text:   %q\n", text)
		fmt.Printf("Color:  %s\n", color)
		fmt.Printf("Scroll: %v\n\n", scroll)
		fmt.Println(ascii)
		return nil
	}

	log.Println("Connecting to LED display...")
	s := display.NewScreen(address)
	if err := s.Connect(); err != nil {
		return fmt.Errorf("connect: %w", err)
	}
	defer func() {
		s.Disconnect()
		log.Println("Disconnected.")
	}()

	log.Printf("Sending: %q\n", text)
	if _, err := s.Render(text, color, scroll, speed, brightness, scale, false); err != nil {
		return err
	}
	log.Println("Sent!")
	time.Sleep(2 * time.Second)
	return nil
}

// ── helpers ────────────────────────────────────────────────────────────────

func colorNames() []string {
	names := make([]string, 0, len(bitmap.Colors))
	for k := range bitmap.Colors {
		names = append(names, k)
	}
	return names
}
