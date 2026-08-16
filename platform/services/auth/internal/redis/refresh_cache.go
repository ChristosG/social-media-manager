package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	goredis "github.com/redis/go-redis/v9"
)

type CachedRefreshToken struct {
	UserID    string    `json:"user_id"`
	FamilyID  string    `json:"family_id"`
	Revoked   bool      `json:"revoked"`
	ExpiresAt time.Time `json:"expires_at"`
}

type RefreshCache struct {
	rdb *goredis.Client
}

func NewRefreshCache(client *Client) *RefreshCache {
	return &RefreshCache{rdb: client.RDB()}
}

func (c *RefreshCache) Get(ctx context.Context, tokenHash string) (*CachedRefreshToken, error) {
	key := fmt.Sprintf("auth:refresh:%s", tokenHash)
	data, err := c.rdb.Get(ctx, key).Bytes()
	if err != nil {
		if err == goredis.Nil {
			return nil, nil
		}
		return nil, err
	}
	var token CachedRefreshToken
	if err := json.Unmarshal(data, &token); err != nil {
		return nil, err
	}
	return &token, nil
}

func (c *RefreshCache) Set(ctx context.Context, tokenHash string, token *CachedRefreshToken, ttl time.Duration) error {
	key := fmt.Sprintf("auth:refresh:%s", tokenHash)
	data, err := json.Marshal(token)
	if err != nil {
		return err
	}
	return c.rdb.Set(ctx, key, data, ttl).Err()
}

func (c *RefreshCache) Invalidate(ctx context.Context, tokenHash string) error {
	key := fmt.Sprintf("auth:refresh:%s", tokenHash)
	return c.rdb.Del(ctx, key).Err()
}
