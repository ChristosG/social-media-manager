package handler

import (
	"testing"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
)

func TestProviderToString(t *testing.T) {
	tests := []struct {
		input    authv1.AuthProvider
		expected string
	}{
		{authv1.AuthProvider_AUTH_PROVIDER_GOOGLE, "google"},
		{authv1.AuthProvider_AUTH_PROVIDER_FACEBOOK, "facebook"},
		{authv1.AuthProvider_AUTH_PROVIDER_UNSPECIFIED, ""},
		{authv1.AuthProvider_AUTH_PROVIDER_LOCAL, ""},
	}

	for _, tc := range tests {
		got := providerToString(tc.input)
		if got != tc.expected {
			t.Errorf("providerToString(%v) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}
