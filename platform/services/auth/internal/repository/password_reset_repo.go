package repository

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/microservices-agents/platform/services/auth/internal/model"
)

var ErrPasswordResetNotFound = errors.New("password reset token not found")

type PasswordResetRepository interface {
	Create(ctx context.Context, reset *model.PasswordReset) error
	GetByTokenHash(ctx context.Context, tokenHash string) (*model.PasswordReset, error)
	MarkUsed(ctx context.Context, id string) error
	DeleteExpired(ctx context.Context) (int64, error)
}

type pgPasswordResetRepository struct {
	pool *pgxpool.Pool
}

func NewPasswordResetRepository(pool *pgxpool.Pool) PasswordResetRepository {
	return &pgPasswordResetRepository{pool: pool}
}

func (r *pgPasswordResetRepository) Create(ctx context.Context, reset *model.PasswordReset) error {
	err := r.pool.QueryRow(ctx,
		`INSERT INTO password_resets (user_id, token_hash, expires_at)
		 VALUES ($1, $2, $3)
		 RETURNING id, created_at`,
		reset.UserID, reset.TokenHash, reset.ExpiresAt,
	).Scan(&reset.ID, &reset.CreatedAt)
	if err != nil {
		return fmt.Errorf("insert password reset: %w", err)
	}
	return nil
}

func (r *pgPasswordResetRepository) GetByTokenHash(ctx context.Context, tokenHash string) (*model.PasswordReset, error) {
	var reset model.PasswordReset
	err := r.pool.QueryRow(ctx,
		`SELECT id, user_id, token_hash, expires_at, used, created_at
		 FROM password_resets WHERE token_hash = $1`,
		tokenHash,
	).Scan(&reset.ID, &reset.UserID, &reset.TokenHash,
		&reset.ExpiresAt, &reset.Used, &reset.CreatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrPasswordResetNotFound
		}
		return nil, fmt.Errorf("query password reset: %w", err)
	}
	return &reset, nil
}

func (r *pgPasswordResetRepository) MarkUsed(ctx context.Context, id string) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE password_resets SET used = TRUE WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("mark password reset used: %w", err)
	}
	return nil
}

func (r *pgPasswordResetRepository) DeleteExpired(ctx context.Context) (int64, error) {
	tag, err := r.pool.Exec(ctx,
		`DELETE FROM password_resets WHERE expires_at < NOW()`)
	if err != nil {
		return 0, fmt.Errorf("delete expired resets: %w", err)
	}
	return tag.RowsAffected(), nil
}
