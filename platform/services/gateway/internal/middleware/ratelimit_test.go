package middleware

import (
	"net/http"
	"testing"
)

// F5: a client-supplied X-Forwarded-For must never become the rate-limit key. The trusted nginx layer
// puts the real client in X-Real-IP; XFF is attacker-controllable (left-most value).

func TestExtractIP_PrefersXRealIP_OverSpoofedXFF(t *testing.T) {
	r, _ := http.NewRequest("GET", "/", nil)
	r.RemoteAddr = "10.0.0.5:1234"
	r.Header.Set("X-Real-IP", "203.0.113.7")    // set by trusted nginx
	r.Header.Set("X-Forwarded-For", "1.2.3.4")  // attacker-supplied — must be ignored
	if got := extractIP(r); got != "203.0.113.7" {
		t.Fatalf("expected key from X-Real-IP 203.0.113.7, got %q", got)
	}
}

func TestExtractIP_IgnoresSpoofedXFF_WithoutRealIP(t *testing.T) {
	r, _ := http.NewRequest("GET", "/", nil)
	r.RemoteAddr = "10.0.0.5:1234"
	r.Header.Set("X-Forwarded-For", "1.2.3.4") // must NOT become the key
	if got := extractIP(r); got != "10.0.0.5" {
		t.Fatalf("expected fallback to RemoteAddr host 10.0.0.5, got %q", got)
	}
}

func TestExtractIP_RotatingXFF_KeysToSameClient(t *testing.T) {
	// An attacker behind one real IP rotating XFF per request must still land on ONE bucket.
	mk := func(xff string) *http.Request {
		r, _ := http.NewRequest("GET", "/", nil)
		r.RemoteAddr = "10.0.0.9:1"
		r.Header.Set("X-Real-IP", "198.51.100.22")
		r.Header.Set("X-Forwarded-For", xff)
		return r
	}
	a, b := extractIP(mk("9.9.9.9")), extractIP(mk("8.8.8.8"))
	if a != b || a != "198.51.100.22" {
		t.Fatalf("rotating XFF produced different keys: %q vs %q", a, b)
	}
}
