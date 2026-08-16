package handler

import (
	"context"
	"encoding/json"
	"io"
	"net/http"

	"github.com/go-chi/chi/v5"
	chatv1 "github.com/microservices-agents/platform/proto/gen/go/chat/v1"
	"github.com/microservices-agents/platform/services/gateway/internal/middleware"
	"google.golang.org/grpc/metadata"
)

// ChatHandler translates REST/HTTP requests into gRPC calls to the chat service.
type ChatHandler struct {
	client chatv1.ChatServiceClient
}

// NewChatHandler creates a new ChatHandler backed by the given gRPC client.
func NewChatHandler(client chatv1.ChatServiceClient) *ChatHandler {
	return &ChatHandler{client: client}
}

// withUserMeta creates a gRPC context with user identity metadata.
func withUserMeta(r *http.Request) context.Context {
	ctx := r.Context()
	userID, _ := ctx.Value(middleware.UserIDKey).(string)
	email, _ := ctx.Value(middleware.EmailKey).(string)
	md := metadata.Pairs("x-user-id", userID, "x-email", email)
	return metadata.NewOutgoingContext(ctx, md)
}

// ---------- request types ----------

type createConversationRequest struct {
	Title        string `json:"title"`
	Model        string `json:"model"`
	SystemPrompt string `json:"system_prompt"`
}

type updateConversationRequest struct {
	Title        string `json:"title"`
	Model        string `json:"model"`
	SystemPrompt string `json:"system_prompt"`
}

type sendMessageRequest struct {
	Content string `json:"content"`
}

// ---------- handlers ----------

// CreateConversation handles POST /api/v1/chat/conversations.
func (h *ChatHandler) CreateConversation(w http.ResponseWriter, r *http.Request) {
	var req createConversationRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.CreateConversation(withUserMeta(r), &chatv1.CreateConversationRequest{
		Title:        req.Title,
		Model:        req.Model,
		SystemPrompt: req.SystemPrompt,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusCreated, map[string]interface{}{
		"conversation": conversationToMap(resp.Conversation),
	})
}

// ListConversations handles GET /api/v1/chat/conversations.
func (h *ChatHandler) ListConversations(w http.ResponseWriter, r *http.Request) {
	resp, err := h.client.ListConversations(withUserMeta(r), &chatv1.ListConversationsRequest{
		Limit:  intQueryParam(r, "limit", 50),
		Offset: intQueryParam(r, "offset", 0),
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	convos := make([]map[string]interface{}, 0, len(resp.Conversations))
	for _, c := range resp.Conversations {
		convos = append(convos, conversationToMap(c))
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"conversations": convos,
		"total":         resp.Total,
	})
}

// GetConversation handles GET /api/v1/chat/conversations/{id}.
func (h *ChatHandler) GetConversation(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	resp, err := h.client.GetConversation(withUserMeta(r), &chatv1.GetConversationRequest{
		Id:              id,
		IncludeMessages: true,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	msgs := make([]map[string]interface{}, 0, len(resp.Messages))
	for _, m := range resp.Messages {
		msgs = append(msgs, messageToMap(m))
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"conversation": conversationToMap(resp.Conversation),
		"messages":     msgs,
	})
}

// UpdateConversation handles PUT /api/v1/chat/conversations/{id}.
func (h *ChatHandler) UpdateConversation(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	var req updateConversationRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.UpdateConversation(withUserMeta(r), &chatv1.UpdateConversationRequest{
		Id:           id,
		Title:        req.Title,
		Model:        req.Model,
		SystemPrompt: req.SystemPrompt,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"conversation": conversationToMap(resp.Conversation),
	})
}

// DeleteConversation handles DELETE /api/v1/chat/conversations/{id}.
func (h *ChatHandler) DeleteConversation(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	_, err := h.client.DeleteConversation(withUserMeta(r), &chatv1.DeleteConversationRequest{
		Id: id,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "conversation deleted"})
}

// SendMessage handles POST /api/v1/chat/conversations/{id}/messages.
func (h *ChatHandler) SendMessage(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	var req sendMessageRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.SendMessage(withUserMeta(r), &chatv1.SendMessageRequest{
		ConversationId: id,
		Content:        req.Content,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"user_message":      messageToMap(resp.UserMessage),
		"assistant_message": messageToMap(resp.AssistantMessage),
	})
}

// SearchConversations handles GET /api/v1/chat/conversations/search.
func (h *ChatHandler) SearchConversations(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")

	resp, err := h.client.SearchConversations(withUserMeta(r), &chatv1.SearchConversationsRequest{
		Query:  query,
		Limit:  intQueryParam(r, "limit", 20),
		Offset: intQueryParam(r, "offset", 0),
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	convos := make([]map[string]interface{}, 0, len(resp.Conversations))
	for _, c := range resp.Conversations {
		convos = append(convos, conversationToMap(c))
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"conversations": convos,
		"total":         resp.Total,
	})
}

// StreamMessages handles POST /api/v1/chat/conversations/{id}/stream.
// Uses Server-Sent Events to stream tokens back to the client.
func (h *ChatHandler) StreamMessages(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	var req sendMessageRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	stream, err := h.client.StreamChat(withUserMeta(r), &chatv1.StreamChatRequest{
		ConversationId: id,
		Content:        req.Content,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "streaming not supported")
		return
	}

	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			writeSSEEvent(w, flusher, "error", `{"error":"stream interrupted"}`)
			break
		}

		switch evt := resp.Event.(type) {
		case *chatv1.StreamChatResponse_Token:
			writeSSEEvent(w, flusher, "token", evt.Token)
		case *chatv1.StreamChatResponse_Complete:
			data, _ := marshalJSON(messageToMap(evt.Complete))
			writeSSEEvent(w, flusher, "done", string(data))
		case *chatv1.StreamChatResponse_Error:
			writeSSEEvent(w, flusher, "error", evt.Error)
		}
	}
}

// ---------- helpers ----------

func conversationToMap(c *chatv1.Conversation) map[string]interface{} {
	if c == nil {
		return nil
	}
	result := map[string]interface{}{
		"id":    c.Id,
		"title": c.Title,
	}
	if c.Model != "" {
		result["model"] = c.Model
	}
	if c.SystemPrompt != "" {
		result["system_prompt"] = c.SystemPrompt
	}
	if c.CreatedAt != nil {
		result["created_at"] = c.CreatedAt.AsTime()
	}
	if c.UpdatedAt != nil {
		result["updated_at"] = c.UpdatedAt.AsTime()
	}
	return result
}

func messageToMap(m *chatv1.Message) map[string]interface{} {
	if m == nil {
		return nil
	}
	result := map[string]interface{}{
		"id":              m.Id,
		"conversation_id": m.ConversationId,
		"role":            m.Role.String(),
		"content":         m.Content,
	}
	if m.TokenCount > 0 {
		result["token_count"] = m.TokenCount
	}
	if m.CreatedAt != nil {
		result["created_at"] = m.CreatedAt.AsTime()
	}
	if len(m.Attachments) > 0 {
		atts := make([]map[string]interface{}, 0, len(m.Attachments))
		for _, a := range m.Attachments {
			atts = append(atts, map[string]interface{}{
				"id":                a.Id,
				"filename":          a.Filename,
				"original_filename": a.OriginalFilename,
				"mime_type":         a.MimeType,
				"file_size":         a.FileSize,
				"status":            a.Status,
			})
		}
		result["attachments"] = atts
	}
	return result
}

func intQueryParam(r *http.Request, name string, defaultVal int32) int32 {
	val := r.URL.Query().Get(name)
	if val == "" {
		return defaultVal
	}
	var n int32
	for _, c := range val {
		if c < '0' || c > '9' {
			return defaultVal
		}
		n = n*10 + int32(c-'0')
	}
	return n
}

func writeSSEEvent(w http.ResponseWriter, flusher http.Flusher, event string, data string) {
	w.Write([]byte("event: " + event + "\ndata: " + data + "\n\n"))
	flusher.Flush()
}

func marshalJSON(v interface{}) ([]byte, error) {
	return json.Marshal(v)
}
