package redis

import (
	"context"
	"fmt"
	"time"

	goredis "github.com/redis/go-redis/v9"
)

type TokenBlacklist struct {
	rdb *goredis.Client
}

func NewTokenBlacklist(client *Client) *TokenBlacklist {
	return &TokenBlacklist{rdb: client.RDB()}
}

// Blacklist adds a JTI to the blacklist with TTL = remaining access token lifetime.
func (b *TokenBlacklist) Blacklist(ctx context.Context, jti string, ttl time.Duration) error {
	if ttl <= 0 {
		return nil
	}
	key := fmt.Sprintf("auth:blacklist:%s", jti)
	return b.rdb.Set(ctx, key, "1", ttl).Err()
}

// IsBlacklisted checks if a JTI is in the blacklist.
func (b *TokenBlacklist) IsBlacklisted(ctx context.Context, jti string) (bool, error) {
	key := fmt.Sprintf("auth:blacklist:%s", jti)
	val, err := b.rdb.Exists(ctx, key).Result()
	if err != nil {
		return false, err
	}
	return val > 0, nil
}
