# Stage 1: Build
FROM golang:1.23-alpine AS builder

WORKDIR /app

RUN apk add --no-cache gcc musl-dev bluez-dev dbus-dev pkgconf

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=1 GOOS=linux go build -o machine .

# Stage 2: Runtime
FROM alpine:latest

RUN apk add --no-cache bluez dbus

WORKDIR /app

COPY --from=builder /app/machine .

# Expose ports for Go app
EXPOSE 8080

ENTRYPOINT ["./machine"]
CMD ["run"]

