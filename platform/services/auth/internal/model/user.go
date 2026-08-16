package model

import (
	"time"
)

type User struct {
	ID            string            `json:"id"`
	Email         string            `json:"email"`
	EmailVerified bool              `json:"email_verified"`
	PasswordHash  *string           `json:"password_hash,omitempty"`
	DisplayName   string            `json:"display_name"`
	TenantID      *string           `json:"tenant_id,omitempty"`
	MFAEnabled    bool              `json:"mfa_enabled"`
	MFASecret     []byte            `json:"-"`
	Metadata      map[string]string `json:"metadata"`
	CreatedAt     time.Time         `json:"created_at"`
	UpdatedAt     time.Time         `json:"updated_at"`
}
