package config

import pkgconfig "github.com/microservices-agents/platform/pkg/config"

// Config holds all configuration for the API gateway service.
type Config struct {
	HTTPPort           int    `env:"GATEWAY_HTTP_PORT" envDefault:"8080"`
	AuthServiceAddr    string `env:"GATEWAY_AUTH_SERVICE_ADDR" envDefault:"localhost:50051"`
	JWTPublicKey       string `env:"JWT_PUBLIC_KEY,required"`
	CORSAllowedOrigins string `env:"GATEWAY_CORS_ALLOWED_ORIGINS" envDefault:"http://localhost:3000"`
	RateLimitRPS       int    `env:"GATEWAY_RATE_LIMIT_RPS" envDefault:"100"`

	// Redis (empty = disabled, falls back to in-memory)
	RedisAddr string `env:"REDIS_ADDR" envDefault:""`

	// Chat service (empty = chat disabled)
	ChatServiceAddr  string `env:"GATEWAY_CHAT_SERVICE_ADDR" envDefault:""`
	ChatServiceWSURL string `env:"GATEWAY_CHAT_SERVICE_WS_URL" envDefault:""`

	// Auth tenant HTTP endpoint (runs alongside gRPC in auth service)
	AuthTenantURL string `env:"GATEWAY_AUTH_TENANT_URL" envDefault:""`

	// Agent service (empty = disabled)
	AgentServiceURL   string `env:"GATEWAY_AGENT_SERVICE_URL" envDefault:""`   // http://agent-service:8085
	AgentServiceWSURL string `env:"GATEWAY_AGENT_SERVICE_WS_URL" envDefault:""` // agent-service:8085

	// Network ACL shared secret injected as X-Proxy-Secret on every request we proxy to agent-service
	// (HTTP + WS). agent-service rejects traffic without it. Empty = disabled. (nginx injects the same
	// secret on the routes it serves directly.)
	AgentProxySecret string `env:"AGENT_PROXY_SECRET" envDefault:""`
}

// Load reads configuration from environment variables.
func Load() (*Config, error) {
	cfg := &Config{}
	if err := pkgconfig.Load(cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}
