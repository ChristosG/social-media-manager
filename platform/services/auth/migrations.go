package auth

import "embed"

// Migrations contains the embedded SQL migration files for the auth service.
// These are used by golang-migrate to apply schema changes at startup.
//
//go:embed migrations/*.sql
var Migrations embed.FS
