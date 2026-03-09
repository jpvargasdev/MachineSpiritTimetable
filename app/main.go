package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/spf13/cobra"

	"machine/internal/api"
	"machine/internal/bitmap"
	"machine/internal/display"
)

const defaultSiteID = 9293

func main() {
	root := &cobra.Command{
		Use:   "machine",
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
	departureCmd.Flags().IntVarP(&interval, "interval", "i", 60, "API refresh interval in seconds")
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

	// ── serve mode ─────────────────────────────────────────────────────
	var httpAddr string
	serveCmd := &cobra.Command{
		Use:   "serve",
		Short: "Start HTTP server with health endpoint",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runServe(httpAddr)
		},
	}
	serveCmd.Flags().StringVar(&httpAddr, "addr", ":8080", "HTTP listen address")

	// ── run mode (site + serve concurrently) ───────────────────────────
	var (
		runSiteID   int
		runInterval int
		runFont     string
		runColor    string
		runScroll   bool
		runAddress  string
		runHTTPAddr string
	)

	runCmd := &cobra.Command{
		Use:   "run",
		Short: "Start HTTP server and departure display concurrently",
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
			defer stop()

			errCh := make(chan error, 2)
			go func() {
				errCh <- runServe(runHTTPAddr)
			}()
			go func() {
				errCh <- runDepartures(ctx, runSiteID, runInterval, runColor, runFont, runScroll, false, runAddress)
			}()

			select {
			case <-ctx.Done():
				return nil
			case err := <-errCh:
				return err
			}
		},
	}
	runCmd.Flags().IntVarP(&runSiteID, "site", "s", defaultSiteID, "SL site ID")
	runCmd.Flags().IntVarP(&runInterval, "interval", "i", 30, "API refresh interval in seconds")
	runCmd.Flags().StringVarP(&runFont, "font", "f", "small", "Font size: small, medium, large")
	runCmd.Flags().StringVarP(&runColor, "color", "c", "red", fmt.Sprintf("Display color %v", colorNames()))
	runCmd.Flags().BoolVar(&runScroll, "scroll", false, "Enable scrolling animation")
	runCmd.Flags().StringVar(&runAddress, "address", "", "BLE device address (default: built-in)")
	runCmd.Flags().StringVar(&runHTTPAddr, "addr", ":8080", "HTTP listen address")

	root.AddCommand(departureCmd, textCmd, serveCmd, runCmd)

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

	// Preview mode — no BLE needed
	if preview {
		return runDeparturesPreview(ctx, slApi, siteID, interval, color, font, scroll)
	}

	// Real mode — connect with automatic reconnect on device power loss
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		screen := display.NewScreen(address)
		if err := screen.Connect(); err != nil {
			// Device not found — wait and retry
			select {
			case <-ctx.Done():
				return nil
			case <-time.After(5 * time.Minute):
			}
			continue
		}

		err := runDeparturesLoop(ctx, slApi, screen, siteID, interval, color, font, scroll)
		screen.Disconnect()

		if err == nil || ctx.Err() != nil {
			return nil
		}
		// BLE error (device powered off) — retry after 5 min
		select {
		case <-ctx.Done():
			return nil
		case <-time.After(5 * time.Minute):
		}
	}
}

// errBLE is returned when a BLE write fails so the outer loop can reconnect.
var errBLE = fmt.Errorf("ble error")

func runDeparturesLoop(ctx context.Context, slApi *api.SLApi, screen *display.Screen, siteID, interval int, color, font string, scroll bool) error {
	var cachedResp *api.DeparturesResponse
	var lastFetch time.Time

	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		if cachedResp == nil || time.Since(lastFetch) >= time.Duration(interval)*time.Second {
			resp, err := slApi.GetDepartures(siteID, "METRO")
			if err != nil {
				select {
				case <-ctx.Done():
					return nil
				case <-time.After(5 * time.Second):
				}
				continue
			}
			cachedResp = resp
			lastFetch = time.Now()
		}

		byDest := map[string][]api.Departure{}
		for _, d := range cachedResp.Departures {
			byDest[d.Destination] = append(byDest[d.Destination], d)
		}

		for _, dest := range destinations {
			select {
			case <-ctx.Done():
				return nil
			default:
			}

			deps := byDest[dest.name]
			var line1, line2 string
			var renderErr error

			switch font {
			case "large":
				if len(deps) > 0 {
					line1 = fmt.Sprintf("%s %s", dest.name, deps[0].Display)
				} else {
					line1 = fmt.Sprintf("%s --", dest.name)
				}
				_, renderErr = screen.Render(line1, color, scroll, 60, 255, 1, false)

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
				_, renderErr = screen.RenderTwoLines(line1, line2, color, scroll, 60, 255, true, false)

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
				_, renderErr = screen.RenderTwoLines(line1, line2, color, scroll, 60, 255, false, false)
			}

			if renderErr != nil {
				return errBLE
			}

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

func runDeparturesPreview(ctx context.Context, slApi *api.SLApi, siteID, interval int, color, font string, scroll bool) error {
	var cachedResp *api.DeparturesResponse
	var lastFetch time.Time

	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		if cachedResp == nil || time.Since(lastFetch) >= time.Duration(interval)*time.Second {
			resp, err := slApi.GetDepartures(siteID, "METRO")
			if err != nil {
				select {
				case <-ctx.Done():
					return nil
				case <-time.After(5 * time.Second):
				}
				continue
			}
			cachedResp = resp
			lastFetch = time.Now()
		}

		byDest := map[string][]api.Departure{}
		for _, d := range cachedResp.Departures {
			byDest[d.Destination] = append(byDest[d.Destination], d)
		}

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
				ascii, _ := display.NewScreen("").Render(line1, color, scroll, 60, 255, 1, true)
				fmt.Println(ascii)

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
				ascii, _ := display.NewScreen("").RenderTwoLines(line1, line2, color, scroll, 60, 255, true, true)
				fmt.Println(ascii)

			default:
				switch len(deps) {
				case 0:
					line1, line2 = dest.name, "No departures"
				case 1:
					line1, line2 = fmt.Sprintf("%s %s", dest.name, deps[0].Display), ""
				default:
					line1 = fmt.Sprintf("%s %s", dest.name, deps[0].Display)
					line2 = fmt.Sprintf("%s %s", dest.name, deps[1].Display)
				}
				ascii, _ := display.NewScreen("").RenderTwoLines(line1, line2, color, scroll, 60, 255, false, true)
				fmt.Println(ascii)
			}

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

	s := display.NewScreen(address)
	if err := s.Connect(); err != nil {
		return fmt.Errorf("connect: %w", err)
	}
	defer s.Disconnect()

	if _, err := s.Render(text, color, scroll, speed, brightness, scale, false); err != nil {
		return err
	}
	time.Sleep(2 * time.Second)
	return nil
}

// ── serve ──────────────────────────────────────────────────────────────────

func runServe(addr string) error {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})

	srv := &http.Server{Addr: addr, Handler: mux}

	errCh := make(chan error, 1)
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- err
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	select {
	case <-quit:
		return srv.Close()
	case err := <-errCh:
		return err
	}
}

// ── helpers ────────────────────────────────────────────────────────────────

func colorNames() []string {
	names := make([]string, 0, len(bitmap.Colors))
	for k := range bitmap.Colors {
		names = append(names, k)
	}
	return names
}
