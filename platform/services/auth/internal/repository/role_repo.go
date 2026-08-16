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
	ErrRoleNotFound      = errors.New("role not found")
	ErrRoleAlreadyExists = errors.New("role already exists for tenant")
)

type RoleRepository interface {
	Create(ctx context.Context, role *model.Role) error
	GetByID(ctx context.Context, id string) (*model.Role, error)
	GetRolesForUser(ctx context.Context, userID string) ([]*model.Role, error)
	AssignRole(ctx context.Context, userID, roleID string) error
	RemoveRole(ctx context.Context, userID, roleID string) error
}

type pgRoleRepository struct {
	pool *pgxpool.Pool
}

func NewRoleRepository(pool *pgxpool.Pool) RoleRepository {
	return &pgRoleRepository{pool: pool}
}

func (r *pgRoleRepository) Create(ctx context.Context, role *model.Role) error {
	permissions, err := json.Marshal(role.Permissions)
	if err != nil {
		return fmt.Errorf("marshal permissions: %w", err)
	}

	err = r.pool.QueryRow(ctx,
		`INSERT INTO roles (tenant_id, name, permissions)
		 VALUES ($1, $2, $3)
		 RETURNING id, created_at, updated_at`,
		role.TenantID, role.Name, permissions,
	).Scan(&role.ID, &role.CreatedAt, &role.UpdatedAt)
	if err != nil {
		if isDuplicateKeyError(err) {
			return ErrRoleAlreadyExists
		}
		return fmt.Errorf("insert role: %w", err)
	}
	return nil
}

func (r *pgRoleRepository) GetByID(ctx context.Context, id string) (*model.Role, error) {
	var role model.Role
	var permissionsJSON []byte

	err := r.pool.QueryRow(ctx,
		"SELECT id, tenant_id, name, permissions, created_at, updated_at FROM roles WHERE id = $1", id,
	).Scan(&role.ID, &role.TenantID, &role.Name, &permissionsJSON, &role.CreatedAt, &role.UpdatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrRoleNotFound
		}
		return nil, fmt.Errorf("query role: %w", err)
	}

	if permissionsJSON != nil {
		if err := json.Unmarshal(permissionsJSON, &role.Permissions); err != nil {
			return nil, fmt.Errorf("unmarshal permissions: %w", err)
		}
	}
	return &role, nil
}

func (r *pgRoleRepository) GetRolesForUser(ctx context.Context, userID string) ([]*model.Role, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT r.id, r.tenant_id, r.name, r.permissions, r.created_at, r.updated_at
		 FROM roles r
		 JOIN user_roles ur ON ur.role_id = r.id
		 WHERE ur.user_id = $1`, userID,
	)
	if err != nil {
		return nil, fmt.Errorf("query user roles: %w", err)
	}
	defer rows.Close()

	var roles []*model.Role
	for rows.Next() {
		var role model.Role
		var permissionsJSON []byte
		if err := rows.Scan(&role.ID, &role.TenantID, &role.Name, &permissionsJSON, &role.CreatedAt, &role.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan role: %w", err)
		}
		if permissionsJSON != nil {
			if err := json.Unmarshal(permissionsJSON, &role.Permissions); err != nil {
				return nil, fmt.Errorf("unmarshal permissions: %w", err)
			}
		}
		roles = append(roles, &role)
	}
	return roles, rows.Err()
}

func (r *pgRoleRepository) AssignRole(ctx context.Context, userID, roleID string) error {
	_, err := r.pool.Exec(ctx,
		`INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING`,
		userID, roleID,
	)
	if err != nil {
		return fmt.Errorf("assign role: %w", err)
	}
	return nil
}

func (r *pgRoleRepository) RemoveRole(ctx context.Context, userID, roleID string) error {
	_, err := r.pool.Exec(ctx,
		`DELETE FROM user_roles WHERE user_id = $1 AND role_id = $2`,
		userID, roleID,
	)
	if err != nil {
		return fmt.Errorf("remove role: %w", err)
	}
	return nil
}
