package handler

import (
	"net/http"

	"github.com/microservices-agents/platform/pkg/health"
)

// HealthHandler returns an HTTP handler that reports the overall service health.
// It returns {"status": "ok"} when all checks pass, or {"status": "degraded", "checks": {...}}
// when any check fails.
func HealthHandler(checker *health.Checker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		results := checker.Check()

		healthy := true
		for _, v := range results {
			if v != "ok" {
				healthy = false
				break
			}
		}

		if healthy {
			writeJSON(w, http.StatusOK, map[string]interface{}{
				"status": "ok",
			})
		} else {
			writeJSON(w, http.StatusOK, map[string]interface{}{
				"status": "degraded",
				"checks": results,
			})
		}
	}
}

// ReadyHandler returns an HTTP handler that reports readiness.
// It returns 200 if all health checks pass, or 503 Service Unavailable if not.
func ReadyHandler(checker *health.Checker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if checker.IsHealthy() {
			writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
		} else {
			writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "not ready"})
		}
	}
}
