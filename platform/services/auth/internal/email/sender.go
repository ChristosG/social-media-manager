package email

import (
	"context"
	"log/slog"
)

// Sender defines the interface for sending transactional emails.
type Sender interface {
	SendForgotPassword(ctx context.Context, toEmail, name, resetURL string) error
	SendWelcome(ctx context.Context, toEmail, name string) error
	SendPasswordChanged(ctx context.Context, toEmail, name string) error
}

// RealSender sends emails via the email service HTTP API.
type RealSender struct {
	client *Client
}

// NewRealSender creates a Sender that calls the email service.
func NewRealSender(client *Client) Sender {
	return &RealSender{client: client}
}

func (s *RealSender) SendForgotPassword(ctx context.Context, toEmail, name, resetURL string) error {
	return s.client.Send(ctx, toEmail, "forgot_password", map[string]any{
		"name":      name,
		"reset_url": resetURL,
	})
}

func (s *RealSender) SendWelcome(ctx context.Context, toEmail, name string) error {
	return s.client.Send(ctx, toEmail, "welcome", map[string]any{
		"name": name,
	})
}

func (s *RealSender) SendPasswordChanged(ctx context.Context, toEmail, name string) error {
	return s.client.Send(ctx, toEmail, "password_changed", map[string]any{
		"name": name,
	})
}

// NoopSender logs email events without sending. Used when EMAIL_ENABLED=false.
type NoopSender struct {
	logger *slog.Logger
}

// NewNoopSender creates a Sender that only logs.
func NewNoopSender(logger *slog.Logger) Sender {
	return &NoopSender{logger: logger}
}

func (s *NoopSender) SendForgotPassword(ctx context.Context, toEmail, name, resetURL string) error {
	s.logger.Info("noop: would send forgot_password email", "to", toEmail)
	return nil
}

func (s *NoopSender) SendWelcome(ctx context.Context, toEmail, name string) error {
	s.logger.Info("noop: would send welcome email", "to", toEmail)
	return nil
}

func (s *NoopSender) SendPasswordChanged(ctx context.Context, toEmail, name string) error {
	s.logger.Info("noop: would send password_changed email", "to", toEmail)
	return nil
}
