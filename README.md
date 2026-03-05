# machinespirittimetable

Displays Stockholm public transit (SL) departure times on a XyaoLED BLE LED matrix display. Runs as a single Go binary on a Linux server with Bluetooth (BlueZ).

## Features

- Fetches live departures from the SL Transport API
- Renders text to the LED matrix over BLE
- Automatic reconnect if the display is powered off (retries every 5 minutes)
- HTTP health endpoint at `GET /health`
- Single binary, Docker-ready, multi-arch (linux/amd64, linux/arm64)

## Commands

```
xyaod run     # Start departure display + HTTP server concurrently (default)
xyaod site    # Departure display loop only
xyaod text    # Send custom text to the display
xyaod serve   # HTTP server only
```

### `run` (recommended)

Starts both the departure loop and the HTTP health server in the same process.

```
xyaod run [flags]

Flags:
  -s, --site int        SL site ID (default 9293)
  -i, --interval int    API refresh interval in seconds (default 30)
  -f, --font string     Font size: small, medium, large (default "small")
  -c, --color string    Display color: red, green, blue, yellow, white, ... (default "red")
      --scroll          Enable scrolling animation
      --address string  BLE device address (default: scan by name)
      --addr string     HTTP listen address (default ":8080")
```

### `text`

Send a one-shot message to the display.

```
xyaod text -t "Hello" -c yellow --scroll
```

### Preview mode

Add `--preview` / `-p` to any command to render an ASCII preview in the terminal without connecting to the device.

```
xyaod site --preview -f medium -c yellow
xyaod text -t "Hello" --preview
```

## Configuration

Create a `.env` file in the working directory:

```env
SL_API_KEY=your_api_key_here
```

## BLE device

- Device name: `XyaoLED_44BF`
- Write characteristic: `0000ae01-0000-1000-8000-00805f9b34fb`
- Service: `0000ae30-0000-1000-8000-00805f9b34fb`

## Docker

The image defaults to `xyaod run`. Override the command to pass flags:

```yaml
image: ghcr.io/jpvargasdev/machinespirittimetable:latest
command: ["run", "-f", "medium", "-c", "yellow"]
```

### Production compose snippet

```yaml
machinespirittimetable:
  image: ghcr.io/jpvargasdev/machinespirittimetable:0.0.3
  container_name: machinespirittimetable
  privileged: true
  network_mode: host
  volumes:
    - /var/run/dbus:/var/run/dbus
  environment:
    DBUS_SYSTEM_BUS_ADDRESS: "unix:path=/var/run/dbus/system_bus_socket"
  env_file:
    - machinespirittimetable.env
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/health || exit 1"]
    interval: 2m
    timeout: 3s
    retries: 2
    start_period: 30s
  restart: unless-stopped
  command: ["run", "-f", "medium", "-c", "yellow"]
```

## Building

```
cd app
go build -o xyaod .
```

Requires CGO and BlueZ/dbus headers on Linux:

```
apt install libbluetooth-dev libdbus-1-dev
```

## Releasing

Push a version tag to trigger the GitHub Actions workflow, which builds and pushes a multi-arch image to GHCR:

```
git tag v0.0.4
git push origin v0.0.4
```
