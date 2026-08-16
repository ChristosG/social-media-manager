package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/microservices-agents/platform/services/auth/internal/model"
)

var (
	ErrTenantNotFound    = errors.New("tenant not found")
	ErrSlugAlreadyExists = errors.New("slug already exists")
)

type TenantRepository interface {
	Create(ctx context.Context, tenant *model.Tenant) error
	GetByID(ctx context.Context, id string) (*model.Tenant, error)
	GetBySlug(ctx context.Context, slug string) (*model.Tenant, error)
	Update(ctx context.Context, tenant *model.Tenant) error
}

type pgTenantRepository struct {
	pool *pgxpool.Pool
}

func NewTenantRepository(pool *pgxpool.Pool) TenantRepository {
	return &pgTenantRepository{pool: pool}
}

func (r *pgTenantRepository) Create(ctx context.Context, tenant *model.Tenant) error {
	settings, err := json.Marshal(tenant.Settings)
	if err != nil {
		return fmt.Errorf("marshal settings: %w", err)
	}

	err = r.pool.QueryRow(ctx,
		`INSERT INTO tenants (name, slug, plan, settings, active)
		 VALUES ($1, $2, $3, $4, $5)
		 RETURNING id, created_at, updated_at`,
		tenant.Name, tenant.Slug, tenant.Plan, settings, tenant.Active,
	).Scan(&tenant.ID, &tenant.CreatedAt, &tenant.UpdatedAt)
	if err != nil {
		if isDuplicateKeyError(err) {
			return ErrSlugAlreadyExists
		}
		return fmt.Errorf("insert tenant: %w", err)
	}
	return nil
}

func (r *pgTenantRepository) GetByID(ctx context.Context, id string) (*model.Tenant, error) {
	return r.getTenant(ctx,
		"SELECT id, name, slug, plan, settings, active, created_at, updated_at FROM tenants WHERE id = $1", id)
}

func (r *pgTenantRepository) GetBySlug(ctx context.Context, slug string) (*model.Tenant, error) {
	return r.getTenant(ctx,
		"SELECT id, name, slug, plan, settings, active, created_at, updated_at FROM tenants WHERE slug = $1", slug)
}

func (r *pgTenantRepository) getTenant(ctx context.Context, query string, arg interface{}) (*model.Tenant, error) {
	var tenant model.Tenant
	var settingsJSON []byte

	err := r.pool.QueryRow(ctx, query, arg).Scan(
		&tenant.ID, &tenant.Name, &tenant.Slug, &tenant.Plan,
		&settingsJSON, &tenant.Active, &tenant.CreatedAt, &tenant.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrTenantNotFound
		}
		return nil, fmt.Errorf("query tenant: %w", err)
	}

	if settingsJSON != nil {
		if err := json.Unmarshal(settingsJSON, &tenant.Settings); err != nil {
			return nil, fmt.Errorf("unmarshal settings: %w", err)
		}
	}
	if tenant.Settings == nil {
		tenant.Settings = make(map[string]string)
	}

	return &tenant, nil
}

func (r *pgTenantRepository) Update(ctx context.Context, tenant *model.Tenant) error {
	settings, err := json.Marshal(tenant.Settings)
	if err != nil {
		return fmt.Errorf("marshal settings: %w", err)
	}

	tag, err := r.pool.Exec(ctx,
		`UPDATE tenants SET name = $1, slug = $2, plan = $3, settings = $4, active = $5, updated_at = NOW()
		 WHERE id = $6`,
		tenant.Name, tenant.Slug, tenant.Plan, settings, tenant.Active, tenant.ID,
	)
	if err != nil {
		return fmt.Errorf("update tenant: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrTenantNotFound
	}
	return nil
}
