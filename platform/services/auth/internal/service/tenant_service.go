package service

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"strings"

	"github.com/microservices-agents/platform/services/auth/internal/model"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
)

var (
	ErrTenantSlugTaken      = errors.New("tenant slug already taken")
	ErrInvalidSlug          = errors.New("slug must be lowercase alphanumeric with hyphens, 3-100 chars")
	ErrUserAlreadyHasTenant = errors.New("user already belongs to a tenant")
	slugRegex               = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$`)
)

// DefaultRoles defines the roles created for every new tenant.
var DefaultRoles = []struct {
	Name        string
	Permissions []string
}{
	{
		Name: "owner",
		Permissions: []string{
			"content:read", "content:write", "content:delete",
			"memory:read", "memory:write",
			"tenant:manage", "users:manage", "roles:manage",
		},
	},
	{
		Name: "admin",
		Permissions: []string{
			"content:read", "content:write", "content:delete",
			"memory:read", "memory:write",
			"users:manage",
		},
	},
	{
		Name: "member",
		Permissions: []string{
			"content:read", "content:write",
			"memory:read",
		},
	},
}

type TenantService struct {
	tenantRepo repository.TenantRepository
	roleRepo   repository.RoleRepository
	userRepo   repository.UserRepository
	authSvc    *AuthService
	logger     *slog.Logger
}

func NewTenantService(
	tenantRepo repository.TenantRepository,
	roleRepo repository.RoleRepository,
	userRepo repository.UserRepository,
	authSvc *AuthService,
	logger *slog.Logger,
) *TenantService {
	return &TenantService{
		tenantRepo: tenantRepo,
		roleRepo:   roleRepo,
		userRepo:   userRepo,
		authSvc:    authSvc,
		logger:     logger,
	}
}

// TenantRegisterInput holds the input for creating a tenant with its first user.
type TenantRegisterInput struct {
	TenantName  string
	TenantSlug  string
	Email       string
	Password    string
	DisplayName string
}

// TenantRegisterResult holds the result of tenant registration.
type TenantRegisterResult struct {
	Tenant *model.Tenant
	User   *model.User
	Roles  []string
	Perms  []string
}

// RegisterTenant creates a new tenant, default roles, the first user (owner), and assigns the owner role.
func (s *TenantService) RegisterTenant(ctx context.Context, input TenantRegisterInput) (*TenantRegisterResult, error) {
	// Validate slug.
	slug := strings.ToLower(strings.TrimSpace(input.TenantSlug))
	if !slugRegex.MatchString(slug) {
		return nil, ErrInvalidSlug
	}

	// 1. Create tenant.
	tenant := &model.Tenant{
		Name:   input.TenantName,
		Slug:   slug,
		Plan:   "free",
		Active: true,
	}
	if err := s.tenantRepo.Create(ctx, tenant); err != nil {
		if errors.Is(err, repository.ErrSlugAlreadyExists) {
			return nil, ErrTenantSlugTaken
		}
		return nil, fmt.Errorf("create tenant: %w", err)
	}

	// 2. Create default roles.
	roleMap := make(map[string]*model.Role)
	for _, def := range DefaultRoles {
		role := &model.Role{
			TenantID:    tenant.ID,
			Name:        def.Name,
			Permissions: def.Permissions,
		}
		if err := s.roleRepo.Create(ctx, role); err != nil {
			return nil, fmt.Errorf("create role %s: %w", def.Name, err)
		}
		roleMap[def.Name] = role
	}

	// 3. Register user with tenant_id.
	user, err := s.authSvc.Register(ctx, input.Email, input.Password, input.DisplayName, nil)
	if err != nil {
		return nil, fmt.Errorf("register user: %w", err)
	}

	// 4. Set user's tenant_id.
	user.TenantID = &tenant.ID
	if err := s.userRepo.Update(ctx, user); err != nil {
		return nil, fmt.Errorf("set user tenant: %w", err)
	}

	// 5. Assign owner role.
	ownerRole := roleMap["owner"]
	if err := s.roleRepo.AssignRole(ctx, user.ID, ownerRole.ID); err != nil {
		return nil, fmt.Errorf("assign owner role: %w", err)
	}

	s.logger.Info("tenant registered",
		"tenant_id", tenant.ID,
		"tenant_slug", tenant.Slug,
		"user_id", user.ID,
		"email", user.Email,
	)

	return &TenantRegisterResult{
		Tenant: tenant,
		User:   user,
		Roles:  []string{"owner"},
		Perms:  ownerRole.Permissions,
	}, nil
}

// CreateTenantInput holds the input for creating a tenant for an existing user.
type CreateTenantInput struct {
	TenantName   string
	TenantSlug   string
	BusinessSize string   // "solo", "small", "medium", "large", "enterprise"
	Modules      []string // e.g. ["chat","studio"] — chat always added
}

// CreateTenantResult holds the result of tenant creation for an existing user.
type CreateTenantResult struct {
	Tenant *model.Tenant
	User   *model.User
	Roles  []string
	Perms  []string
}

// CreateTenantForUser creates a tenant for an already-registered user.
func (s *TenantService) CreateTenantForUser(ctx context.Context, userID string, input CreateTenantInput) (*CreateTenantResult, error) {
	// Validate slug.
	slug := strings.ToLower(strings.TrimSpace(input.TenantSlug))
	if !slugRegex.MatchString(slug) {
		return nil, ErrInvalidSlug
	}

	// Fetch user, verify no existing tenant.
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("get user: %w", err)
	}
	if user.TenantID != nil {
		return nil, ErrUserAlreadyHasTenant
	}

	// Ensure "chat" is always included in modules.
	modules := input.Modules
	hasChat := false
	for _, m := range modules {
		if m == "chat" {
			hasChat = true
			break
		}
	}
	if !hasChat {
		modules = append([]string{"chat"}, modules...)
	}
	moduleStr := strings.Join(modules, ",")

	// 1. Create tenant.
	tenant := &model.Tenant{
		Name:   input.TenantName,
		Slug:   slug,
		Plan:   "free",
		Active: true,
		Settings: map[string]string{
			"business_size": input.BusinessSize,
			"modules":       moduleStr,
		},
	}
	if err := s.tenantRepo.Create(ctx, tenant); err != nil {
		if errors.Is(err, repository.ErrSlugAlreadyExists) {
			return nil, ErrTenantSlugTaken
		}
		return nil, fmt.Errorf("create tenant: %w", err)
	}

	// 2. Create default roles.
	roleMap := make(map[string]*model.Role)
	for _, def := range DefaultRoles {
		role := &model.Role{
			TenantID:    tenant.ID,
			Name:        def.Name,
			Permissions: def.Permissions,
		}
		if err := s.roleRepo.Create(ctx, role); err != nil {
			return nil, fmt.Errorf("create role %s: %w", def.Name, err)
		}
		roleMap[def.Name] = role
	}

	// 3. Set user's tenant_id.
	user.TenantID = &tenant.ID
	if err := s.userRepo.Update(ctx, user); err != nil {
		return nil, fmt.Errorf("set user tenant: %w", err)
	}

	// 4. Assign owner role.
	ownerRole := roleMap["owner"]
	if err := s.roleRepo.AssignRole(ctx, user.ID, ownerRole.ID); err != nil {
		return nil, fmt.Errorf("assign owner role: %w", err)
	}

	s.logger.Info("tenant created for existing user",
		"tenant_id", tenant.ID,
		"tenant_slug", tenant.Slug,
		"user_id", user.ID,
		"modules", moduleStr,
	)

	return &CreateTenantResult{
		Tenant: tenant,
		User:   user,
		Roles:  []string{"owner"},
		Perms:  ownerRole.Permissions,
	}, nil
}

// GetTenant returns a tenant by ID.
func (s *TenantService) GetTenant(ctx context.Context, tenantID string) (*model.Tenant, error) {
	return s.tenantRepo.GetByID(ctx, tenantID)
}

// UpdateTenantSettingsInput holds partial settings to update.
type UpdateTenantSettingsInput struct {
	Name     string            // optional — empty means no change
	Settings map[string]string // merged into existing settings
}

// UpdateTenantSettings updates tenant settings.
func (s *TenantService) UpdateTenantSettings(ctx context.Context, tenantID string, input UpdateTenantSettingsInput) (*model.Tenant, error) {
	tenant, err := s.tenantRepo.GetByID(ctx, tenantID)
	if err != nil {
		return nil, err
	}

	if input.Name != "" {
		tenant.Name = input.Name
	}

	if tenant.Settings == nil {
		tenant.Settings = make(map[string]string)
	}
	for k, v := range input.Settings {
		tenant.Settings[k] = v
	}

	if err := s.tenantRepo.Update(ctx, tenant); err != nil {
		return nil, err
	}

	return tenant, nil
}
