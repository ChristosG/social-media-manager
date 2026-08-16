package router

import (
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"
	"github.com/microservices-agents/platform/pkg/health"
	"github.com/microservices-agents/platform/services/gateway/internal/handler"
	"github.com/microservices-agents/platform/services/gateway/internal/middleware"
)

// Options holds optional handler/proxy dependencies for conditional routing.
type Options struct {
	ChatHandler   *handler.ChatHandler
	ChatHTTPProxy http.Handler
	WSProxy       http.HandlerFunc
	TenantProxy   http.Handler
	AgentProxy    http.Handler
}

// New builds and returns the chi router with all routes and middleware configured.
func New(
	authHandler *handler.AuthHandler,
	healthChecker *health.Checker,
	authMiddleware func(http.Handler) http.Handler,
	corsMiddleware func(http.Handler) http.Handler,
	rateLimiter *middleware.RateLimiter,
	logger *slog.Logger,
	opts ...Options,
) *chi.Mux {
	r := chi.NewRouter()

	// Global middleware stack
	r.Use(middleware.RequestID)
	r.Use(middleware.Logging(logger))
	r.Use(corsMiddleware)
	r.Use(rateLimiter.Handler)
	r.Use(chimiddleware.Recoverer)

	// Health check routes (outside /api/v1)
	r.Get("/healthz", handler.HealthHandler(healthChecker))
	r.Get("/readyz", handler.ReadyHandler(healthChecker))

	// Resolve options
	var opt Options
	if len(opts) > 0 {
		opt = opts[0]
	}

	// API v1
	r.Route("/api/v1", func(r chi.Router) {
		// Auth routes
		r.Route("/auth", func(r chi.Router) {
			// Tenant registration (public, proxy to auth HTTP)
			if opt.TenantProxy != nil {
				r.Post("/tenants/register", opt.TenantProxy.ServeHTTP)
			}

			// Public routes
			r.Post("/register", authHandler.Register)
			r.Post("/login", authHandler.Login)
			r.Post("/refresh", authHandler.RefreshToken)
			r.Post("/forgot-password", authHandler.ForgotPassword)
			r.Post("/reset-password", authHandler.ResetPassword)
			r.Post("/verify-email", authHandler.VerifyEmail)
			r.Post("/resend-verification", authHandler.ResendVerification)
			r.Get("/oauth/{provider}", authHandler.OAuthURL)
			r.Get("/oauth/{provider}/callback", authHandler.OAuthCallback)
			r.Post("/mfa/verify", authHandler.VerifyMFA)

			// Protected routes (require valid JWT)
			r.Group(func(r chi.Router) {
				r.Use(authMiddleware)
				r.Post("/logout", authHandler.Logout)
				r.Get("/me", authHandler.GetMe)
				r.Post("/mfa/enable", authHandler.EnableMFA)
				r.Post("/mfa/disable", authHandler.DisableMFA)

				// Tenant management (authenticated, proxy to auth HTTP)
				if opt.TenantProxy != nil {
					r.Post("/tenants/create", opt.TenantProxy.ServeHTTP)
					r.Get("/tenants/current", opt.TenantProxy.ServeHTTP)
					r.Put("/tenants/current", opt.TenantProxy.ServeHTTP)
				}
			})
		})

		// Chat routes (conditional — only when chat service is configured)
		if opt.ChatHandler != nil {
			r.Route("/chat", func(r chi.Router) {
				r.Use(authMiddleware)
				r.Post("/conversations", opt.ChatHandler.CreateConversation)
				r.Get("/conversations", opt.ChatHandler.ListConversations)
				r.Get("/conversations/search", opt.ChatHandler.SearchConversations)
				r.Get("/conversations/{id}", opt.ChatHandler.GetConversation)
				r.Put("/conversations/{id}", opt.ChatHandler.UpdateConversation)
				r.Delete("/conversations/{id}", opt.ChatHandler.DeleteConversation)
				r.Post("/conversations/{id}/messages", opt.ChatHandler.SendMessage)
				r.Post("/conversations/{id}/stream", opt.ChatHandler.StreamMessages)

				// Attachment routes (HTTP proxy to chat-service REST API)
				if opt.ChatHTTPProxy != nil {
					r.Post("/attachments", opt.ChatHTTPProxy.ServeHTTP)
					r.Get("/attachments/{id}/download", opt.ChatHTTPProxy.ServeHTTP)
				}
			})
		}

		// Agent service proxy (conditional — only when agent service URL is configured)
		if opt.AgentProxy != nil {
			r.Route("/agent", func(r chi.Router) {
				r.Use(authMiddleware)
				r.Handle("/*", http.StripPrefix("/api/v1/agent", opt.AgentProxy))
			})
		}
	})

	// WebSocket endpoint (JWT validated in handler, not middleware)
	if opt.WSProxy != nil {
		r.Get("/ws/chat", opt.WSProxy)
	}

	return r
}
