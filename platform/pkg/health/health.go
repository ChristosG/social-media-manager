package health

import "sync"

// Checker aggregates named health checks and reports their status.
type Checker struct {
	mu     sync.RWMutex
	checks map[string]func() error
}

// New creates a new Checker with no registered checks.
func New() *Checker {
	return &Checker{
		checks: make(map[string]func() error),
	}
}

// Register adds a named health check function. If a check with the same name
// already exists, it is replaced.
func (c *Checker) Register(name string, check func() error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.checks[name] = check
}

// Check runs all registered health checks and returns a map of check name
// to result. A passing check maps to "ok"; a failing check maps to the
// error string.
func (c *Checker) Check() map[string]string {
	c.mu.RLock()
	defer c.mu.RUnlock()

	results := make(map[string]string, len(c.checks))
	for name, check := range c.checks {
		if err := check(); err != nil {
			results[name] = err.Error()
		} else {
			results[name] = "ok"
		}
	}
	return results
}

// IsHealthy returns true only if all registered checks pass.
func (c *Checker) IsHealthy() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	for _, check := range c.checks {
		if err := check(); err != nil {
			return false
		}
	}
	return true
}
