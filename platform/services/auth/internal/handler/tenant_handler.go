package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"github.com/microservices-agents/platform/pkg/jwt"
	"github.com/microservices-agents/platform/services/auth/internal/service"
)

type tenantRegisterRequest struct {
	TenantName  string `json:"tenant_name"`
	TenantSlug  string `json:"tenant_slug"`
	Email       string `json:"email"`
	Password    string `json:"password"`
	DisplayName string `json:"display_name"`
}

type tenantCreateRequest struct {
	TenantName   string   `json:"tenant_name"`
	TenantSlug   string   `json:"tenant_slug"`
	BusinessSize string   `json:"business_size"`
	Modules      []string `json:"modules"`
}

type tenantUpdateRequest struct {
	Name    string            `json:"name,omitempty"`
	Settings map[string]string `json:"settings,omitempty"`
}

// TenantRegisterHandler returns an HTTP handler for POST /tenants/register.
// Creates a tenant, default roles, owner user, and returns JWT with tenant claims.
func TenantRegisterHandler(tenantSvc *service.TenantService, tokenSvc *service.TokenService, jwtMgr *jwt.Manager, accessTTL time.Duration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			httpError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}

		var req tenantRegisterRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			httpError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		defer r.Body.Close()

		if req.TenantName == "" || req.TenantSlug == "" || req.Email == "" || req.Password == "" || req.DisplayName == "" {
			httpError(w, http.StatusBadRequest, "all fields required: tenant_name, tenant_slug, email, password, display_name")
			return
		}

		result, err := tenantSvc.RegisterTenant(r.Context(), service.TenantRegisterInput{
			TenantName:  req.TenantName,
			TenantSlug:  req.TenantSlug,
			Email:       req.Email,
			Password:    req.Password,
			DisplayName: req.DisplayName,
		})
		if err != nil {
			switch {
			case errors.Is(err, service.ErrTenantSlugTaken):
				httpError(w, http.StatusConflict, "tenant slug already taken")
			case errors.Is(err, service.ErrInvalidSlug):
				httpError(w, http.StatusBadRequest, err.Error())
			case errors.Is(err, service.ErrEmailAlreadyExists):
				httpError(w, http.StatusConflict, "email already registered")
			case errors.Is(err, service.ErrWeakPassword):
				httpError(w, http.StatusBadRequest, err.Error())
			default:
				httpError(w, http.StatusInternalServerError, "registration failed")
			}
			return
		}

		accessToken, err := jwtMgr.GenerateAccessToken(
			result.User.ID, result.User.Email,
			result.Tenant.ID, result.Roles, result.Perms,
			nil, accessTTL,
		)
		if err != nil {
			httpError(w, http.StatusInternalServerError, "failed to generate token")
			return
		}

		refreshToken, err := tokenSvc.CreateRefreshToken(r.Context(), result.User.ID, "")
		if err != nil {
			httpError(w, http.StatusInternalServerError, "failed to create refresh token")
			return
		}

		httpJSON(w, http.StatusCreated, map[string]interface{}{
			"access_token":  accessToken,
			"refresh_token": refreshToken,
			"tenant": map[string]interface{}{
				"id":   result.Tenant.ID,
				"name": result.Tenant.Name,
				"slug": result.Tenant.Slug,
				"plan": result.Tenant.Plan,
			},
			"user": map[string]interface{}{
				"id":           result.User.ID,
				"email":        result.User.Email,
				"display_name": result.User.DisplayName,
				"tenant_id":    result.Tenant.ID,
			},
			"roles":       result.Roles,
			"permissions": result.Perms,
		})
	}
}

// TenantCreateHandler returns an HTTP handler for POST /tenants/create.
// Creates a tenant for an already-authenticated user (via X-User-Id header from gateway).
func TenantCreateHandler(tenantSvc *service.TenantService, tokenSvc *service.TokenService, jwtMgr *jwt.Manager, accessTTL time.Duration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			httpError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}

		userID := r.Header.Get("X-User-Id")
		if userID == "" {
			httpError(w, http.StatusUnauthorized, "missing user context")
			return
		}

		var req tenantCreateRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			httpError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		defer r.Body.Close()

		if req.TenantName == "" || req.TenantSlug == "" {
			httpError(w, http.StatusBadRequest, "tenant_name and tenant_slug are required")
			return
		}

		result, err := tenantSvc.CreateTenantForUser(r.Context(), userID, service.CreateTenantInput{
			TenantName:   req.TenantName,
			TenantSlug:   req.TenantSlug,
			BusinessSize: req.BusinessSize,
			Modules:      req.Modules,
		})
		if err != nil {
			switch {
			case errors.Is(err, service.ErrTenantSlugTaken):
				httpError(w, http.StatusConflict, "tenant slug already taken")
			case errors.Is(err, service.ErrInvalidSlug):
				httpError(w, http.StatusBadRequest, err.Error())
			case errors.Is(err, service.ErrUserAlreadyHasTenant):
				httpError(w, http.StatusConflict, "user already belongs to a tenant")
			default:
				httpError(w, http.StatusInternalServerError, "tenant creation failed")
			}
			return
		}

		// Generate JWT with tenant claims including modules.
		modules := result.Tenant.Settings["modules"]
		customClaims := map[string]string{"modules": modules}

		accessToken, err := jwtMgr.GenerateAccessToken(
			result.User.ID, result.User.Email,
			result.Tenant.ID, result.Roles, result.Perms,
			customClaims, accessTTL,
		)
		if err != nil {
			httpError(w, http.StatusInternalServerError, "failed to generate token")
			return
		}

		refreshToken, err := tokenSvc.CreateRefreshToken(r.Context(), result.User.ID, "")
		if err != nil {
			httpError(w, http.StatusInternalServerError, "failed to create refresh token")
			return
		}

		httpJSON(w, http.StatusCreated, map[string]interface{}{
			"access_token":  accessToken,
			"refresh_token": refreshToken,
			"tenant": map[string]interface{}{
				"id":       result.Tenant.ID,
				"name":     result.Tenant.Name,
				"slug":     result.Tenant.Slug,
				"plan":     result.Tenant.Plan,
				"settings": result.Tenant.Settings,
			},
			"user": map[string]interface{}{
				"id":           result.User.ID,
				"email":        result.User.Email,
				"display_name": result.User.DisplayName,
				"tenant_id":    result.Tenant.ID,
			},
			"roles":       result.Roles,
			"permissions": result.Perms,
		})
	}
}

// TenantGetHandler returns an HTTP handler for GET /tenants/current.
// Returns the current tenant details (via X-Tenant-Id header from gateway).
func TenantGetHandler(tenantSvc *service.TenantService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			httpError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}

		tenantID := r.Header.Get("X-Tenant-Id")
		if tenantID == "" {
			httpError(w, http.StatusBadRequest, "no tenant context")
			return
		}

		tenant, err := tenantSvc.GetTenant(r.Context(), tenantID)
		if err != nil {
			httpError(w, http.StatusNotFound, "tenant not found")
			return
		}

		httpJSON(w, http.StatusOK, map[string]interface{}{
			"id":         tenant.ID,
			"name":       tenant.Name,
			"slug":       tenant.Slug,
			"plan":       tenant.Plan,
			"settings":   tenant.Settings,
			"active":     tenant.Active,
			"created_at": tenant.CreatedAt,
			"updated_at": tenant.UpdatedAt,
		})
	}
}

// TenantUpdateHandler returns an HTTP handler for PUT /tenants/current.
// Updates tenant settings (via X-Tenant-Id header from gateway).
func TenantUpdateHandler(tenantSvc *service.TenantService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPut {
			httpError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}

		tenantID := r.Header.Get("X-Tenant-Id")
		if tenantID == "" {
			httpError(w, http.StatusBadRequest, "no tenant context")
			return
		}

		var req tenantUpdateRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			httpError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		defer r.Body.Close()

		tenant, err := tenantSvc.UpdateTenantSettings(r.Context(), tenantID, service.UpdateTenantSettingsInput{
			Name:     req.Name,
			Settings: req.Settings,
		})
		if err != nil {
			httpError(w, http.StatusInternalServerError, "update failed")
			return
		}

		httpJSON(w, http.StatusOK, map[string]interface{}{
			"id":         tenant.ID,
			"name":       tenant.Name,
			"slug":       tenant.Slug,
			"plan":       tenant.Plan,
			"settings":   tenant.Settings,
			"active":     tenant.Active,
			"created_at": tenant.CreatedAt,
			"updated_at": tenant.UpdatedAt,
		})
	}
}

func httpError(w http.ResponseWriter, code int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}

func httpJSON(w http.ResponseWriter, code int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}
