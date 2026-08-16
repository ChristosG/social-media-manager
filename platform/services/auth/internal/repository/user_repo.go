package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/microservices-agents/platform/services/auth/internal/model"
)

var (
	ErrUserNotFound      = errors.New("user not found")
	ErrEmailAlreadyExists = errors.New("email already exists")
)

type UserRepository interface {
	Create(ctx context.Context, user *model.User) error
	GetByID(ctx context.Context, id string) (*model.User, error)
	GetByEmail(ctx context.Context, email string) (*model.User, error)
	Update(ctx context.Context, user *model.User) error
	UpdateMFA(ctx context.Context, userID string, enabled bool, secret []byte) error
	UpdatePassword(ctx context.Context, userID string, passwordHash string) error
	VerifyEmail(ctx context.Context, userID string) error
}

type pgUserRepository struct {
	pool *pgxpool.Pool
}

func NewUserRepository(pool *pgxpool.Pool) UserRepository {
	return &pgUserRepository{pool: pool}
}

func (r *pgUserRepository) Create(ctx context.Context, user *model.User) error {
	metadata, err := json.Marshal(user.Metadata)
	if err != nil {
		return fmt.Errorf("marshal metadata: %w", err)
	}

	err = r.pool.QueryRow(ctx,
		`INSERT INTO users (email, email_verified, password_hash, display_name, tenant_id, metadata)
		 VALUES ($1, $2, $3, $4, $5, $6)
		 RETURNING id, created_at, updated_at`,
		user.Email, user.EmailVerified, user.PasswordHash, user.DisplayName, user.TenantID, metadata,
	).Scan(&user.ID, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		if isDuplicateKeyError(err) {
			return ErrEmailAlreadyExists
		}
		return fmt.Errorf("insert user: %w", err)
	}
	return nil
}

func (r *pgUserRepository) GetByID(ctx context.Context, id string) (*model.User, error) {
	return r.getUser(ctx, "SELECT id, email, email_verified, password_hash, display_name, tenant_id, mfa_enabled, mfa_secret, metadata, created_at, updated_at FROM users WHERE id = $1", id)
}

func (r *pgUserRepository) GetByEmail(ctx context.Context, email string) (*model.User, error) {
	return r.getUser(ctx, "SELECT id, email, email_verified, password_hash, display_name, tenant_id, mfa_enabled, mfa_secret, metadata, created_at, updated_at FROM users WHERE email = $1", email)
}

func (r *pgUserRepository) getUser(ctx context.Context, query string, arg interface{}) (*model.User, error) {
	var user model.User
	var metadataJSON []byte

	err := r.pool.QueryRow(ctx, query, arg).Scan(
		&user.ID, &user.Email, &user.EmailVerified, &user.PasswordHash,
		&user.DisplayName, &user.TenantID, &user.MFAEnabled, &user.MFASecret, &metadataJSON,
		&user.CreatedAt, &user.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrUserNotFound
		}
		return nil, fmt.Errorf("query user: %w", err)
	}

	if metadataJSON != nil {
		if err := json.Unmarshal(metadataJSON, &user.Metadata); err != nil {
			return nil, fmt.Errorf("unmarshal metadata: %w", err)
		}
	}
	if user.Metadata == nil {
		user.Metadata = make(map[string]string)
	}

	return &user, nil
}

func (r *pgUserRepository) Update(ctx context.Context, user *model.User) error {
	metadata, err := json.Marshal(user.Metadata)
	if err != nil {
		return fmt.Errorf("marshal metadata: %w", err)
	}

	tag, err := r.pool.Exec(ctx,
		`UPDATE users SET email = $1, display_name = $2, tenant_id = $3, metadata = $4, updated_at = NOW() WHERE id = $5`,
		user.Email, user.DisplayName, user.TenantID, metadata, user.ID,
	)
	if err != nil {
		return fmt.Errorf("update user: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrUserNotFound
	}
	return nil
}

func (r *pgUserRepository) UpdateMFA(ctx context.Context, userID string, enabled bool, secret []byte) error {
	tag, err := r.pool.Exec(ctx,
		`UPDATE users SET mfa_enabled = $1, mfa_secret = $2, updated_at = NOW() WHERE id = $3`,
		enabled, secret, userID,
	)
	if err != nil {
		return fmt.Errorf("update MFA: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrUserNotFound
	}
	return nil
}

func (r *pgUserRepository) UpdatePassword(ctx context.Context, userID string, passwordHash string) error {
	tag, err := r.pool.Exec(ctx,
		`UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2`,
		passwordHash, userID,
	)
	if err != nil {
		return fmt.Errorf("update password: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrUserNotFound
	}
	return nil
}

func (r *pgUserRepository) VerifyEmail(ctx context.Context, userID string) error {
	tag, err := r.pool.Exec(ctx,
		`UPDATE users SET email_verified = TRUE, updated_at = NOW() WHERE id = $1`,
		userID,
	)
	if err != nil {
		return fmt.Errorf("verify email: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrUserNotFound
	}
	return nil
}

// isDuplicateKeyError reports whether err is a Postgres unique-violation
// (SQLSTATE 23505) — used to map an insert race to ErrEmailAlreadyExists etc.
func isDuplicateKeyError(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}
