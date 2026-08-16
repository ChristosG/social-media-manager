package logger

import (
	"log/slog"
	"os"
)

// New creates a structured JSON logger tagged with the given service name.
func New(service string) *slog.Logger {
	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})
	return slog.New(handler).With("service", service)
}
