package middleware

import (
	"net"
	"net/http"
	"sync"
	"time"

	"golang.org/x/time/rate"
)

type ipLimiter struct {
	limiter  *rate.Limiter
	lastSeen time.Time
}

// RateLimiter is an in-memory per-IP rate limiter backed by token buckets.
type RateLimiter struct {
	mu       sync.Mutex
	limiters map[string]*ipLimiter
	rps      int
	done     chan struct{}
}

// NewRateLimiter creates a new per-IP rate limiter that allows rps requests
// per second per IP with a burst size equal to rps. It starts a background
// goroutine that cleans up stale entries every minute.
func NewRateLimiter(rps int) *RateLimiter {
	rl := &RateLimiter{
		limiters: make(map[string]*ipLimiter),
		rps:      rps,
		done:     make(chan struct{}),
	}
	go rl.cleanup()
	return rl
}

// getLimiter returns the rate.Limiter for the given IP, creating one if needed.
func (rl *RateLimiter) getLimiter(ip string) *rate.Limiter {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	entry, exists := rl.limiters[ip]
	if !exists {
		limiter := rate.NewLimiter(rate.Limit(rl.rps), rl.rps)
		rl.limiters[ip] = &ipLimiter{limiter: limiter, lastSeen: time.Now()}
		return limiter
	}

	entry.lastSeen = time.Now()
	return entry.limiter
}

// cleanup removes limiters that have not been seen for more than 3 minutes.
func (rl *RateLimiter) cleanup() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			rl.mu.Lock()
			for ip, entry := range rl.limiters {
				if time.Since(entry.lastSeen) > 3*time.Minute {
					delete(rl.limiters, ip)
				}
			}
			rl.mu.Unlock()
		case <-rl.done:
			return
		}
	}
}

// Stop signals the background cleanup goroutine to exit.
func (rl *RateLimiter) Stop() {
	close(rl.done)
}

// Handler returns HTTP middleware that enforces per-IP rate limits.
// Requests exceeding the limit receive a 429 Too Many Requests response.
func (rl *RateLimiter) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := extractIP(r)
		limiter := rl.getLimiter(ip)

		if !limiter.Allow() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusTooManyRequests)
			w.Write([]byte(`{"error":"rate limit exceeded"}`))
			return
		}

		next.ServeHTTP(w, r)
	})
}

// extractIP returns the client IP used to key the per-IP limiter.
//
// It trusts ONLY X-Real-IP, which the trusted reverse-proxy chain sets to the true client: the host nginx
// runs Cloudflare real_ip (real_ip_header CF-Connecting-IP) and forwards the recovered client as X-Real-IP,
// and the docker nginx re-sets X-Real-IP to its own recovered $remote_addr. X-Forwarded-For is deliberately
// NOT trusted: it is built with $proxy_add_x_forwarded_for, so its left-most entry is whatever the client
// sent — keying on it let an attacker rotate the header per request to mint a fresh bucket and defeat the
// login brute-force / credential-stuffing limit (audit F5).
func extractIP(r *http.Request) string {
	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}
	ip, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return ip
}
