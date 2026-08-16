package handler

import (
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"time"

	pkgjwt "github.com/microservices-agents/platform/pkg/jwt"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // CORS handled by middleware
	},
}

// upstreamDialer bounds the upstream WS handshake so an unresponsive agent-service can't hang the
// upgrade until TCP RST (the default dialer has no handshake timeout).
var upstreamDialer = &websocket.Dialer{HandshakeTimeout: 10 * time.Second}

// NewWSProxy returns an http.HandlerFunc that validates the JWT from the
// ?token= query param, upgrades to WebSocket, and bidirectionally proxies
// frames to the upstream chat service WebSocket.
func NewWSProxy(upstreamWSURL string, jwtManager *pkgjwt.Manager, proxySecret string, logger *slog.Logger) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// 1. Validate JWT from query param
		token := r.URL.Query().Get("token")
		if token == "" {
			http.Error(w, `{"error":"missing token"}`, http.StatusUnauthorized)
			return
		}

		claims, err := jwtManager.ValidateToken(token)
		if err != nil {
			http.Error(w, `{"error":"invalid token"}`, http.StatusUnauthorized)
			return
		}
		// A first-factor-only "mfa:pending" token is not a credential (see middleware.Auth).
		if claims.Custom["mfa"] == "pending" {
			http.Error(w, `{"error":"MFA verification required"}`, http.StatusUnauthorized)
			return
		}

		// 2. Upgrade client connection
		clientConn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			logger.Error("websocket upgrade failed", "error", err)
			return
		}
		defer clientConn.Close()

		// 3. Dial upstream
		upstreamURL := url.URL{
			Scheme: "ws",
			Host:   upstreamWSURL,
			Path:   "/ws/chat",
		}
		reqHeader := http.Header{}
		reqHeader.Set("X-User-Id", claims.Subject)
		reqHeader.Set("X-Email", claims.Email)
		if claims.TenantID != "" {
			reqHeader.Set("X-Tenant-Id", claims.TenantID)
		}
		// Forward the validated token so agent-service can verify it too (defense in depth). Browsers
		// can't set Authorization on a WS upgrade, so the client sends it as ?token=; we relay it as a
		// header. The HTTP path forwards Authorization the same way via the reverse proxy.
		reqHeader.Set("X-Auth-Token", token)
		// Network ACL: prove this upgrade came through the gateway.
		if proxySecret != "" {
			reqHeader.Set("X-Proxy-Secret", proxySecret)
		}

		upstreamConn, _, err := upstreamDialer.Dial(upstreamURL.String(), reqHeader)
		if err != nil {
			logger.Error("upstream websocket dial failed", "error", err, "url", upstreamURL.String())
			clientConn.WriteMessage(websocket.CloseMessage,
				websocket.FormatCloseMessage(websocket.CloseInternalServerErr, "upstream unavailable"))
			return
		}
		defer upstreamConn.Close()

		logger.Debug("websocket proxy established",
			"user_id", claims.Subject,
			"upstream", upstreamURL.String(),
		)

		// 4. Bidirectional proxy
		errCh := make(chan error, 2)

		// Client → Upstream
		go func() {
			errCh <- proxyFrames(clientConn, upstreamConn)
		}()

		// Upstream → Client
		go func() {
			errCh <- proxyFrames(upstreamConn, clientConn)
		}()

		// Wait for either direction to finish
		<-errCh
	}
}

// proxyFrames copies WebSocket frames from src to dst until an error occurs.
func proxyFrames(src, dst *websocket.Conn) error {
	for {
		msgType, msg, err := src.ReadMessage()
		if err != nil {
			if websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
				return nil
			}
			if err == io.EOF {
				return nil
			}
			return err
		}
		if err := dst.WriteMessage(msgType, msg); err != nil {
			return err
		}
	}
}
