package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"
	"github.com/jackc/pgx/v5/pgxpool"

	auth "github.com/microservices-agents/platform/services/auth"
	"github.com/microservices-agents/platform/services/auth/internal/config"
	"github.com/microservices-agents/platform/services/auth/internal/email"
	"github.com/microservices-agents/platform/services/auth/internal/handler"
	rediscache "github.com/microservices-agents/platform/services/auth/internal/redis"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
	"github.com/microservices-agents/platform/services/auth/internal/server"
	"github.com/microservices-agents/platform/services/auth/internal/service"

	"github.com/microservices-agents/platform/pkg/jwt"
	"github.com/microservices-agents/platform/pkg/logger"
)

func main() {
	log := logger.New("auth")

	// 1. Load configuration from environment variables.
	cfg, err := config.Load()
	if err != nil {
		log.Error("failed to load config", "error", err)
		os.Exit(1)
	}

	// 2. Connect to PostgreSQL with an explicitly bounded pool so auth's footprint stays well under
	// Postgres max_connections (shared with agent-service, the worker, and replicas).
	dbURL := cfg.DatabaseURL()
	poolCfg, err := pgxpool.ParseConfig(dbURL)
	if err != nil {
		log.Error("failed to parse database url", "error", err)
		os.Exit(1)
	}
	poolCfg.MaxConns = 20
	poolCfg.MinConns = 2
	pool, err := pgxpool.NewWithConfig(context.Background(), poolCfg)
	if err != nil {
		log.Error("failed to connect to database", "error", err)
		os.Exit(1)
	}
	defer pool.Close()

	if err := pool.Ping(context.Background()); err != nil {
		log.Error("failed to ping database", "error", err)
		os.Exit(1)
	}
	log.Info("connected to database")

	// 3. Run database migrations using embedded SQL files.
	if err := runMigrations(dbURL, log); err != nil {
		log.Error("failed to run migrations", "error", err)
		os.Exit(1)
	}

	// 4. Create repositories.
	userRepo := repository.NewUserRepository(pool)
	tokenRepo := repository.NewRefreshTokenRepository(pool)
	passwordResetRepo := repository.NewPasswordResetRepository(pool)
	tenantRepo := repository.NewTenantRepository(pool)
	roleRepo := repository.NewRoleRepository(pool)

	// 5. Create JWT manager.
	jwtMgr, err := jwt.NewManager(cfg.JWTPrivateKey, cfg.JWTPublicKey)
	if err != nil {
		log.Error("failed to create JWT manager", "error", err)
		os.Exit(1)
	}

	// 5.5. Connect to Redis (optional).
	var redisClient *rediscache.Client
	if cfg.RedisAddr != "" {
		redisClient, err = rediscache.New(cfg.RedisAddr, log)
		if err != nil {
			log.Warn("failed to connect to redis, continuing without cache", "error", err)
		} else {
			defer redisClient.Close()
			// Create cache instances (used by gateway and CDC consumers).
			_ = rediscache.NewTokenBlacklist(redisClient)
			_ = rediscache.NewUserCache(redisClient)
			_ = rediscache.NewRefreshCache(redisClient)
			log.Info("redis cache layer initialized")
		}
	} else {
		log.Info("REDIS_ADDR not set, caching disabled")
	}

	// 6. Create email sender.
	var emailSender email.Sender
	if cfg.EmailEnabled && cfg.EmailAPIKey != "" {
		client := email.NewClient(cfg.EmailServiceURL, cfg.EmailAPIKey, log)
		emailSender = email.NewRealSender(client)
		log.Info("email sending enabled", "url", cfg.EmailServiceURL)
	} else {
		emailSender = email.NewNoopSender(log)
		log.Info("email sending disabled")
	}

	// 8. Create services.
	authSvc := service.NewAuthService(userRepo, log, emailSender)
	tokenSvc := service.NewTokenService(tokenRepo, log, cfg.JWTRefreshTokenTTL)
	oauthSvc := service.NewOAuthService(service.OAuthConfig{
		GoogleClientID:       cfg.OAuthGoogleClientID,
		GoogleClientSecret:   cfg.OAuthGoogleClientSecret,
		GoogleRedirectURL:    cfg.OAuthGoogleRedirectURL,
		FacebookClientID:     cfg.OAuthFacebookClientID,
		FacebookClientSecret: cfg.OAuthFacebookClientSecret,
		FacebookRedirectURL:  cfg.OAuthFacebookRedirectURL,
	}, userRepo, log)
	mfaSvc := service.NewMFAService(userRepo, log, cfg.MFAEncryptionKey, "Platform")
	emailSvc := service.NewEmailService(userRepo, passwordResetRepo, log, emailSender, cfg.AppURL)

	// 9. Create gRPC handler.
	h := handler.NewAuthHandler(
		authSvc,
		tokenSvc,
		oauthSvc,
		mfaSvc,
		emailSvc,
		roleRepo,
		tenantRepo,
		jwtMgr,
		cfg.JWTAccessTokenTTL,
		cfg.JWTRefreshTokenTTL,
	)

	// 9.5. Create tenant service and HTTP handlers.
	tenantSvc := service.NewTenantService(tenantRepo, roleRepo, userRepo, authSvc, log)
	tenantRegHandler := handler.TenantRegisterHandler(tenantSvc, tokenSvc, jwtMgr, cfg.JWTAccessTokenTTL)
	tenantCreateHandler := handler.TenantCreateHandler(tenantSvc, tokenSvc, jwtMgr, cfg.JWTAccessTokenTTL)
	tenantGetHandler := handler.TenantGetHandler(tenantSvc)
	tenantUpdateHandler := handler.TenantUpdateHandler(tenantSvc)

	// Start tenant HTTP server (port = gRPC port + 1000, e.g., 51051).
	tenantMux := http.NewServeMux()
	tenantMux.HandleFunc("/tenants/register", tenantRegHandler)
	tenantMux.HandleFunc("/tenants/create", tenantCreateHandler)
	tenantMux.HandleFunc("/tenants/current", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			tenantGetHandler(w, r)
		case http.MethodPut:
			tenantUpdateHandler(w, r)
		default:
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusMethodNotAllowed)
			w.Write([]byte(`{"error":"method not allowed"}`))
		}
	})
	tenantHTTPPort := cfg.GRPCPort + 1000
	go func() {
		addr := fmt.Sprintf(":%d", tenantHTTPPort)
		log.Info("starting tenant HTTP server", "addr", addr)
		if err := http.ListenAndServe(addr, tenantMux); err != nil {
			log.Error("tenant HTTP server failed", "error", err)
		}
	}()

	// 10. Create and start the gRPC server.
	grpcSrv := server.NewGRPCServer(h, log)

	errCh := make(chan error, 1)
	go func() {
		errCh <- server.ListenAndServe(grpcSrv, cfg.GRPCPort, log)
	}()

	// 11. Wait for shutdown signal (SIGINT or SIGTERM) or server error.
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-quit:
		log.Info("received shutdown signal", "signal", sig.String())
	case err := <-errCh:
		log.Error("server error", "error", err)
	}

	// 12. Graceful shutdown.
	log.Info("shutting down gRPC server...")
	grpcSrv.GracefulStop()

	log.Info("auth service stopped")
}

// runMigrations applies all pending database migrations using the embedded SQL files.
func runMigrations(dbURL string, log *slog.Logger) error {
	source, err := iofs.New(auth.Migrations, "migrations")
	if err != nil {
		return err
	}

	m, err := migrate.NewWithSourceInstance("iofs", source, dbURL)
	if err != nil {
		return err
	}
	defer m.Close()

	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return err
	}

	version, dirty, _ := m.Version()
	log.Info("migrations applied", "version", version, "dirty", dirty)
	return nil
}
