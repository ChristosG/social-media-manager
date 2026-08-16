package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	goredis "github.com/redis/go-redis/v9"
)

const userCacheTTL = 15 * time.Minute

type CachedUser struct {
	ID            string            `json:"id"`
	Email         string            `json:"email"`
	EmailVerified bool              `json:"email_verified"`
	DisplayName   string            `json:"display_name"`
	MFAEnabled    bool              `json:"mfa_enabled"`
	Metadata      map[string]string `json:"metadata"`
	CreatedAt     time.Time         `json:"created_at"`
	UpdatedAt     time.Time         `json:"updated_at"`
}

type UserCache struct {
	rdb *goredis.Client
}

func NewUserCache(client *Client) *UserCache {
	return &UserCache{rdb: client.RDB()}
}

func (c *UserCache) Get(ctx context.Context, userID string) (*CachedUser, error) {
	key := fmt.Sprintf("auth:user:%s", userID)
	data, err := c.rdb.Get(ctx, key).Bytes()
	if err != nil {
		if err == goredis.Nil {
			return nil, nil // cache miss
		}
		return nil, err
	}
	var user CachedUser
	if err := json.Unmarshal(data, &user); err != nil {
		return nil, err
	}
	return &user, nil
}

func (c *UserCache) Set(ctx context.Context, user *CachedUser) error {
	key := fmt.Sprintf("auth:user:%s", user.ID)
	data, err := json.Marshal(user)
	if err != nil {
		return err
	}
	return c.rdb.Set(ctx, key, data, userCacheTTL).Err()
}

func (c *UserCache) Invalidate(ctx context.Context, userID string) error {
	key := fmt.Sprintf("auth:user:%s", userID)
	return c.rdb.Del(ctx, key).Err()
}
