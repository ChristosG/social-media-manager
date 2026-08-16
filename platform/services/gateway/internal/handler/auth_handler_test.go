package handler

import (
	"testing"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
)

func TestParseProvider(t *testing.T) {
	tests := []struct {
		input    string
		expected authv1.AuthProvider
	}{
		{"google", authv1.AuthProvider_AUTH_PROVIDER_GOOGLE},
		{"facebook", authv1.AuthProvider_AUTH_PROVIDER_FACEBOOK},
		// github is removed — must return UNSPECIFIED
		{"github", authv1.AuthProvider_AUTH_PROVIDER_UNSPECIFIED},
		{"unknown", authv1.AuthProvider_AUTH_PROVIDER_UNSPECIFIED},
		{"", authv1.AuthProvider_AUTH_PROVIDER_UNSPECIFIED},
	}

	for _, tc := range tests {
		got := parseProvider(tc.input)
		if got != tc.expected {
			t.Errorf("parseProvider(%q) = %v, want %v", tc.input, got, tc.expected)
		}
	}
}
