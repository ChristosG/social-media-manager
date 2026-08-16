package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/microservices-agents/platform/pkg/health"
	pkgjwt "github.com/microservices-agents/platform/pkg/jwt"
	"github.com/microservices-agents/platform/pkg/logger"
	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
	chatv1 "github.com/microservices-agents/platform/proto/gen/go/chat/v1"
	"github.com/microservices-agents/platform/services/gateway/internal/client"
	"github.com/microservices-agents/platform/services/gateway/internal/config"
	"github.com/microservices-agents/platform/services/gateway/internal/handler"
	"github.com/microservices-agents/platform/services/gateway/internal/middleware"
	"github.com/microservices-agents/platform/services/gateway/internal/router"
	"github.com/microservices-agents/platform/services/gateway/internal/server"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func main() {
	log := logger.New("gateway")

	if err := run(log); err != nil {
		log.Error("fatal error", "error", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	// 1. Load configuration
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}
	log.Info("configuration loaded",
		"http_port", cfg.HTTPPort,
		"auth_service_addr", cfg.AuthServiceAddr,
		"rate_limit_rps", cfg.RateLimitRPS,
		"redis_addr", cfg.RedisAddr,
		"chat_service_addr", cfg.ChatServiceAddr,
	)

	// 2. Create JWT validator (public key only, no signing)
	jwtManager, err := pkgjwt.NewValidatorOnly(cfg.JWTPublicKey)
	if err != nil {
		return fmt.Errorf("create jwt validator: %w", err)
	}

	// 3. Create auth gRPC client
	authClient, err := client.NewAuthClient(cfg.AuthServiceAddr)
	if err != nil {
		return fmt.Errorf("create auth client: %w", err)
	}
	defer authClient.Close()

	// 4. Create health checker with auth service connectivity check
	healthChecker := health.New()
	healthChecker.Register("auth_service", func() error {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		_, err := authClient.Client.ValidateToken(ctx, &authv1.ValidateTokenRequest{})
		if err != nil {
			st, ok := status.FromError(err)
			if ok && st.Code() == codes.Unavailable {
				return fmt.Errorf("auth service unavailable")
			}
		}
		return nil
	})

	// 5. Create handlers
	authHandler := handler.NewAuthHandler(authClient.Client)

	// 6. Create middleware
	authMW := middleware.Auth(jwtManager)
	corsMW := middleware.CORS(cfg.CORSAllowedOrigins)
	rateLimiter := middleware.NewRateLimiter(cfg.RateLimitRPS)
	defer rateLimiter.Stop()

	// 7. Create chat client + handler (conditional)
	var routerOpts router.Options
	if cfg.ChatServiceAddr != "" {
		chatClient, err := client.NewChatClient(cfg.ChatServiceAddr)
		if err != nil {
			log.Error("failed to create chat client", "error", err)
		} else {
			defer chatClient.Close()
			routerOpts.ChatHandler = handler.NewChatHandler(chatClient.Client)
			log.Info("chat service client connected", "addr", cfg.ChatServiceAddr)

			healthChecker.Register("chat_service", func() error {
				ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
				defer cancel()
				_, err := chatClient.Client.ListConversations(ctx, &chatv1.ListConversationsRequest{Limit: 1})
				if err != nil {
					st, ok := status.FromError(err)
					if ok && st.Code() == codes.Unavailable {
						return fmt.Errorf("chat service unavailable")
					}
				}
				return nil
			})
		}
	}

	// WS upstream: prefer agent-service when configured, otherwise fall back to chat-service
	wsUpstream := cfg.ChatServiceWSURL
	if cfg.AgentServiceWSURL != "" {
		wsUpstream = cfg.AgentServiceWSURL
	}

	if wsUpstream != "" {
		routerOpts.WSProxy = handler.NewWSProxy(wsUpstream, jwtManager, cfg.AgentProxySecret, log)
		log.Info("websocket proxy enabled", "upstream", wsUpstream)
	}

	// HTTP proxy for chat-service REST endpoints (attachments) — only when chat WS URL is set
	if cfg.ChatServiceWSURL != "" {
		chatHTTPURL := "http://" + cfg.ChatServiceWSURL
		chatProxy, err := handler.NewHTTPProxy(chatHTTPURL, "", "", log)
		if err != nil {
			log.Error("failed to create chat HTTP proxy", "error", err)
		} else {
			routerOpts.ChatHTTPProxy = chatProxy
			log.Info("chat HTTP proxy enabled", "upstream", chatHTTPURL)
		}
	}

	// 7.5. Create tenant registration proxy
	if cfg.AuthTenantURL != "" {
		proxy, err := handler.NewHTTPProxy(cfg.AuthTenantURL, "/api/v1/auth", "", log)
		if err != nil {
			log.Error("failed to create tenant proxy", "error", err)
		} else {
			routerOpts.TenantProxy = proxy
			log.Info("tenant registration proxy enabled", "upstream", cfg.AuthTenantURL)
		}
	}

	// 7.6. Create agent service HTTP proxy (conditional)
	if cfg.AgentServiceURL != "" {
		proxy, err := handler.NewHTTPProxy(cfg.AgentServiceURL, "", cfg.AgentProxySecret, log)
		if err != nil {
			return fmt.Errorf("create agent proxy: %w", err)
		}
		routerOpts.AgentProxy = proxy
		log.Info("agent proxy enabled", "upstream", cfg.AgentServiceURL)
	}

	// 8. Build router
	mux := router.New(authHandler, healthChecker, authMW, corsMW, rateLimiter, log, routerOpts)

	// 9. Start HTTP server
	srv := server.NewHTTPServer(mux, cfg.HTTPPort)

	errCh := make(chan error, 1)
	go func() {
		log.Info("starting HTTP server", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
		close(errCh)
	}()

	// 10. Graceful shutdown on SIGINT/SIGTERM
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-quit:
		log.Info("received shutdown signal", "signal", sig.String())
	case err := <-errCh:
		if err != nil {
			return fmt.Errorf("server error: %w", err)
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	log.Info("shutting down HTTP server")
	if err := srv.Shutdown(ctx); err != nil {
		return fmt.Errorf("server shutdown: %w", err)
	}

	log.Info("server stopped gracefully")
	return nil
}
