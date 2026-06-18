package main

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/ledongthuc/pdf"
	"github.com/nguyenthenguyen/docx"
	"github.com/xuri/excelize/v2"
)

const (
	analyzerURL   = "http://localhost:3000/analyze"
	anonymizerURL = "http://localhost:3001/anonymize"
	maxUploadSize = 50 << 20
)

type AnalyzerResult struct {
	EntityType string  `json:"entity_type"`
	Start      int     `json:"start"`
	End        int     `json:"end"`
	Score      float64 `json:"score"`
}

type TextRequest struct {
	Text string `json:"text"`
}

type anonymizePayload struct {
	Text            string           `json:"text"`
	AnalyzerResults []AnalyzerResult `json:"analyzer_results"`
}

func analyzeText(text string) ([]AnalyzerResult, error) {
	body, _ := json.Marshal(map[string]string{
		"text":     text,
		"language": "en",
	})

	resp, err := http.Post(analyzerURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("analyzer unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		msg, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("analyzer error %d: %s", resp.StatusCode, msg)
	}

	var results []AnalyzerResult
	if err := json.NewDecoder(resp.Body).Decode(&results); err != nil {
		return nil, fmt.Errorf("bad analyzer response: %w", err)
	}
	return results, nil
}

func anonymizeText(text string, results []AnalyzerResult) (string, error) {
	payload := anonymizePayload{Text: text, AnalyzerResults: results}
	body, _ := json.Marshal(payload)

	resp, err := http.Post(anonymizerURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("anonymizer unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		msg, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("anonymizer error %d: %s", resp.StatusCode, msg)
	}

	var out struct {
		Text string `json:"text"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", fmt.Errorf("bad anonymizer response: %w", err)
	}
	return out.Text, nil
}

func extractText(filename string, data []byte) (string, error) {
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".txt", ".json", ".csv":
		return extractPlain(ext, data)
	case ".pdf":
		return extractPDF(data)
	case ".docx":
		return extractDOCX(data)
	case ".xlsx":
		return extractXLSX(data)
	default:
		return "", fmt.Errorf("unsupported file type: %s", ext)
	}
}

func extractPlain(ext string, data []byte) (string, error) {
	if ext == ".csv" {
		r := csv.NewReader(bytes.NewReader(data))
		r.FieldsPerRecord = -1
		rows, err := r.ReadAll()
		if err != nil {
			return "", err
		}
		var sb strings.Builder
		for _, row := range rows {
			sb.WriteString(strings.Join(row, " "))
			sb.WriteString("\n")
		}
		return sb.String(), nil
	}
	return string(data), nil
}

func extractPDF(data []byte) (string, error) {
	r, err := pdf.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return "", err
	}
	var sb strings.Builder
	for i := 1; i <= r.NumPage(); i++ {
		p := r.Page(i)
		if p.V.IsNull() {
			continue
		}
		txt, err := p.GetPlainText(nil)
		if err != nil {
			return "", err
		}
		sb.WriteString(txt)
	}
	out := sb.String()
	if strings.TrimSpace(out) == "" {
		return "", fmt.Errorf("no text layer found - this PDF may be scanned (OCR not supported yet)")
	}
	return out, nil
}

func extractDOCX(data []byte) (string, error) {
	r, err := docx.ReadDocxFromMemory(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return "", err
	}
	defer r.Close()
	return r.Editable().GetContent(), nil
}

func extractXLSX(data []byte) (string, error) {
	f, err := excelize.OpenReader(bytes.NewReader(data))
	if err != nil {
		return "", err
	}
	defer f.Close()
	var sb strings.Builder
	for _, sheet := range f.GetSheetList() {
		rows, err := f.GetRows(sheet)
		if err != nil {
			return "", err
		}
		for _, row := range rows {
			sb.WriteString(strings.Join(row, " "))
			sb.WriteString("\n")
		}
	}
	return sb.String(), nil
}

func getInputText(c *gin.Context) (string, error) {
	if file, err := c.FormFile("file"); err == nil {
		if file.Size > maxUploadSize {
			return "", fmt.Errorf("file too large (max %d MB)", maxUploadSize>>20)
		}
		f, err := file.Open()
		if err != nil {
			return "", err
		}
		defer f.Close()
		data, err := io.ReadAll(f)
		if err != nil {
			return "", err
		}
		return extractText(file.Filename, data)
	}

	var req TextRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		return "", fmt.Errorf("provide a 'file' upload or JSON body with 'text'")
	}
	if strings.TrimSpace(req.Text) == "" {
		return "", fmt.Errorf("text is empty")
	}
	return req.Text, nil
}

func handleAnalyze(c *gin.Context) {
	text, err := getInputText(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	results, err := analyzeText(text)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"text": text, "results": results})
}

func handleAnonymize(c *gin.Context) {
	text, err := getInputText(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	results, err := analyzeText(text)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	redacted, err := anonymizeText(text, results)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"text": redacted, "results": results})
}

func main() {
	r := gin.Default()
	r.MaxMultipartMemory = maxUploadSize

	r.Use(cors.New(cors.Config{
		AllowOrigins: []string{"http://localhost:5173"},
		AllowMethods: []string{"GET", "POST", "OPTIONS"},
		AllowHeaders: []string{"Content-Type"},
	}))

	r.GET("/health", func(c *gin.Context) {
		c.String(http.StatusOK, "Go server is up")
	})

	api := r.Group("/api")
	{
		api.POST("/analyze", handleAnalyze)
		api.POST("/anonymize", handleAnonymize)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	r.Run(":" + port)
}
