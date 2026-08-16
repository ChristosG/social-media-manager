package redis

import (
	"context"
	"fmt"
	"log/slog"

	goredis "github.com/redis/go-redis/v9"
)

type Client struct {
	rdb    *goredis.Client
	logger *slog.Logger
}

func New(addr string, logger *slog.Logger) (*Client, error) {
	rdb := goredis.NewClient(&goredis.Options{
		Addr: addr,
	})
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		return nil, fmt.Errorf("redis ping: %w", err)
	}
	logger.Info("connected to redis", "addr", addr)
	return &Client{rdb: rdb, logger: logger}, nil
}

func (c *Client) Close() error {
	return c.rdb.Close()
}

func (c *Client) RDB() *goredis.Client {
	return c.rdb
}
