package server

import (
	"fmt"
	"net/http"
	"time"
)

// NewHTTPServer creates a configured *http.Server with sensible timeouts.
func NewHTTPServer(handler http.Handler, port int) *http.Server {
	return &http.Server{
		Addr:         fmt.Sprintf(":%d", port),
		Handler:      handler,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 120 * time.Second, // longer for SSE streaming
		IdleTimeout:  120 * time.Second,
	}
}
