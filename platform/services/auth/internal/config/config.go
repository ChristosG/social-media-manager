package config

import (
	"time"

	"github.com/microservices-agents/platform/pkg/config"
)

type Config struct {
	GRPCPort  int    `env:"AUTH_GRPC_PORT" envDefault:"50051"`
	DBHost    string `env:"AUTH_DB_HOST" envDefault:"localhost"`
	DBPort    int    `env:"AUTH_DB_PORT" envDefault:"5432"`
	DBUser    string `env:"AUTH_DB_USER" envDefault:"platform"`
	DBPass    string `env:"AUTH_DB_PASSWORD" envDefault:"changeme"`
	DBName    string `env:"AUTH_DB_NAME" envDefault:"auth_db"`
	DBSSLMode string `env:"AUTH_DB_SSLMODE" envDefault:"disable"`

	JWTPrivateKey      string        `env:"JWT_PRIVATE_KEY,required"`
	JWTPublicKey       string        `env:"JWT_PUBLIC_KEY,required"`
	JWTAccessTokenTTL  time.Duration `env:"JWT_ACCESS_TOKEN_TTL" envDefault:"15m"`
	JWTRefreshTokenTTL time.Duration `env:"JWT_REFRESH_TOKEN_TTL" envDefault:"168h"`

	MFAEncryptionKey string `env:"MFA_ENCRYPTION_KEY" envDefault:""`

	OAuthGoogleClientID       string `env:"OAUTH_GOOGLE_CLIENT_ID" envDefault:""`
	OAuthGoogleClientSecret   string `env:"OAUTH_GOOGLE_CLIENT_SECRET" envDefault:""`
	OAuthGoogleRedirectURL    string `env:"OAUTH_GOOGLE_REDIRECT_URL" envDefault:""`
	OAuthFacebookClientID     string `env:"OAUTH_FACEBOOK_CLIENT_ID" envDefault:""`
	OAuthFacebookClientSecret string `env:"OAUTH_FACEBOOK_CLIENT_SECRET" envDefault:""`
	OAuthFacebookRedirectURL  string `env:"OAUTH_FACEBOOK_REDIRECT_URL" envDefault:""`

	RedisAddr string `env:"REDIS_ADDR" envDefault:""`

	EmailEnabled    bool   `env:"EMAIL_ENABLED" envDefault:"false"`
	EmailServiceURL string `env:"EMAIL_SERVICE_URL" envDefault:"http://email-service:8025"`
	EmailAPIKey     string `env:"EMAIL_API_KEY" envDefault:""`
	AppURL          string `env:"APP_URL" envDefault:"http://localhost:3000"`
}

func (c Config) DatabaseURL() string {
	return "postgres://" + c.DBUser + ":" + c.DBPass + "@" + c.DBHost + ":" +
		itoa(c.DBPort) + "/" + c.DBName + "?sslmode=" + c.DBSSLMode
}

func itoa(i int) string {
	if i == 0 {
		return "0"
	}
	s := ""
	for i > 0 {
		s = string(rune('0'+i%10)) + s
		i /= 10
	}
	return s
}

func Load() (*Config, error) {
	cfg := &Config{}
	if err := config.Load(cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}
