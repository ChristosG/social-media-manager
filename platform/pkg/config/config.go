package config

import (
	"github.com/caarlos0/env/v11"
)

// Load parses environment variables into the provided struct.
// The cfg argument must be a pointer to a struct with `env` tags.
func Load(cfg interface{}) error {
	return env.Parse(cfg)
}
