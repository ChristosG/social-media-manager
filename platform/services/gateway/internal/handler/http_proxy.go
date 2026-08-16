package handler

import (
	"log/slog"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"github.com/microservices-agents/platform/services/gateway/internal/middleware"
)

// upstreamTransport bounds every hop to an upstream so a wedged backend can't pin gateway goroutines
// until OS keepalive (hours). ResponseHeaderTimeout is generous because FLUX image generation behind
// /api/v1/agent can legitimately take ~2 minutes to send the first byte; response-body streaming after
// the headers arrive is not bounded by it.
var upstreamTransport http.RoundTripper = &http.Transport{
	Proxy:                 http.ProxyFromEnvironment,
	DialContext:           (&net.Dialer{Timeout: 5 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
	ForceAttemptHTTP2:     true,
	MaxIdleConns:          100,
	MaxIdleConnsPerHost:   100,
	IdleConnTimeout:       90 * time.Second,
	TLSHandshakeTimeout:   10 * time.Second,
	ExpectContinueTimeout: 1 * time.Second,
	ResponseHeaderTimeout: 180 * time.Second,
}

// NewHTTPProxy creates a reverse proxy that forwards requests to the given upstream URL.
// It strips the gateway prefix (e.g., /api/v1/auth) and injects user/tenant headers from JWT context.
// proxySecret, when non-empty, is injected as X-Proxy-Secret so the upstream can enforce a network ACL
// (only the gateway/nginx may reach it). Pass "" for upstreams that don't require it.
func NewHTTPProxy(upstream string, stripPrefix string, proxySecret string, logger *slog.Logger) (http.Handler, error) {
	target, err := url.Parse(upstream)
	if err != nil {
		return nil, err
	}

	proxy := &httputil.ReverseProxy{
		Transport: upstreamTransport,
		Director: func(req *http.Request) {
			req.URL.Scheme = target.Scheme
			req.URL.Host = target.Host
			req.Host = target.Host

			// Strip the gateway prefix so upstream receives its native paths.
			// e.g., /api/v1/auth/tenants/create → /tenants/create
			originalPath := req.URL.Path
			if stripPrefix != "" {
				req.URL.Path = strings.TrimPrefix(req.URL.Path, stripPrefix)
				if req.URL.Path == "" {
					req.URL.Path = "/"
				}
			}

			// SECURITY: unconditionally strip any client-supplied identity / trust headers so they can
			// never be smuggled through to an upstream service (cross-tenant impersonation / IDOR, or
			// forging the network-ACL secret). Only the gateway sets these, after validating the JWT.
			req.Header.Del("X-User-Id")
			req.Header.Del("X-Tenant-Id")
			req.Header.Del("X-Email")
			req.Header.Del("X-Roles")
			req.Header.Del("X-Permissions")
			req.Header.Del("X-Proxy-Secret")
			req.Header.Del("X-Auth-Token")

			// Network ACL: prove this request came through the gateway.
			if proxySecret != "" {
				req.Header.Set("X-Proxy-Secret", proxySecret)
			}

			// Inject user context headers from the validated JWT claims.
			ctx := req.Context()
			if userID, ok := ctx.Value(middleware.UserIDKey).(string); ok {
				req.Header.Set("X-User-Id", userID)
			}
			if tenantID, ok := ctx.Value(middleware.TenantIDKey).(string); ok {
				req.Header.Set("X-Tenant-Id", tenantID)
			}
			if roles, ok := ctx.Value(middleware.RolesKey).([]string); ok && len(roles) > 0 {
				req.Header.Set("X-Roles", strings.Join(roles, ","))
			}

			logger.Debug("proxying request",
				"original_path", originalPath,
				"upstream_path", req.URL.Path,
				"upstream_host", target.Host,
			)
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			logger.Error("proxy error", "error", err, "path", r.URL.Path)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			w.Write([]byte(`{"error":"upstream service unavailable"}`))
		},
	}

	return proxy, nil
}
