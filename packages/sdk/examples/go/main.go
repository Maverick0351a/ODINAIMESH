"""
ODIN Protocol Go SDK Example

Demonstrates how to interact with ODIN Protocol services using Go.
Shows SFT translation, Bridge Pro workflows, and Research Engine integration.
"""

package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ODIN Protocol Go SDK structures
type OdinClient struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

type SFTTranslationRequest struct {
	MapID      string                 `json:"map_id"`
	SourceData map[string]interface{} `json:"source_data"`
	Options    map[string]interface{} `json:"options,omitempty"`
}

type SFTTranslationResponse struct {
	TranslatedData map[string]interface{} `json:"translated_data"`
	CID            string                 `json:"cid"`
	Signature      string                 `json:"signature"`
	Timestamp      string                 `json:"timestamp"`
}

type BridgeProWorkflow struct {
	WorkflowID      string                 `json:"workflow_id"`
	SourceFormat    string                 `json:"source_format"`
	TargetFormat    string                 `json:"target_format"`
	PaymentRequired bool                   `json:"payment_required"`
	EstimatedCost   float64                `json:"estimated_cost"`
	Transformations []map[string]interface{} `json:"transformations"`
}

type ResearchProject struct {
	ProjectID   string                 `json:"project_id"`
	Title       string                 `json:"title"`
	Description string                 `json:"description"`
	BYOKToken   string                 `json:"byok_token,omitempty"`
	Parameters  map[string]interface{} `json:"parameters"`
}

// NewOdinClient creates a new ODIN Protocol client
func NewOdinClient(baseURL, apiKey string) *OdinClient {
	return &OdinClient{
		BaseURL: baseURL,
		APIKey:  apiKey,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// makeRequest makes an HTTP request to the ODIN API
func (c *OdinClient) makeRequest(method, endpoint string, body interface{}) (*http.Response, error) {
	var reqBody io.Reader
	
	if body != nil {
		jsonData, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %v", err)
		}
		reqBody = bytes.NewBuffer(jsonData)
	}
	
	req, err := http.NewRequest(method, c.BaseURL+endpoint, reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if c.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.APIKey)
	}
	
	return c.HTTPClient.Do(req)
}

// SFTTranslate performs SFT translation
func (c *OdinClient) SFTTranslate(mapID string, sourceData map[string]interface{}) (*SFTTranslationResponse, error) {
	request := SFTTranslationRequest{
		MapID:      mapID,
		SourceData: sourceData,
	}
	
	resp, err := c.makeRequest("POST", "/sft/translate", request)
	if err != nil {
		return nil, fmt.Errorf("SFT translation request failed: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("SFT translation failed with status: %d", resp.StatusCode)
	}
	
	var result SFTTranslationResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode SFT response: %v", err)
	}
	
	return &result, nil
}

// GetBridgeProWorkflow retrieves Bridge Pro workflow details
func (c *OdinClient) GetBridgeProWorkflow(workflowID string) (*BridgeProWorkflow, error) {
	resp, err := c.makeRequest("GET", "/bridge-pro/workflows/"+workflowID, nil)
	if err != nil {
		return nil, fmt.Errorf("Bridge Pro workflow request failed: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Bridge Pro workflow failed with status: %d", resp.StatusCode)
	}
	
	var workflow BridgeProWorkflow
	if err := json.NewDecoder(resp.Body).Decode(&workflow); err != nil {
		return nil, fmt.Errorf("failed to decode Bridge Pro response: %v", err)
	}
	
	return &workflow, nil
}

// ExecuteBridgeProWorkflow executes a Bridge Pro workflow
func (c *OdinClient) ExecuteBridgeProWorkflow(workflowID string, inputData map[string]interface{}) (map[string]interface{}, error) {
	request := map[string]interface{}{
		"workflow_id": workflowID,
		"input_data":  inputData,
	}
	
	resp, err := c.makeRequest("POST", "/bridge-pro/execute", request)
	if err != nil {
		return nil, fmt.Errorf("Bridge Pro execution request failed: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Bridge Pro execution failed with status: %d", resp.StatusCode)
	}
	
	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode execution response: %v", err)
	}
	
	return result, nil
}

// CreateResearchProject creates a new research project
func (c *OdinClient) CreateResearchProject(title, description string, parameters map[string]interface{}) (*ResearchProject, error) {
	request := map[string]interface{}{
		"title":       title,
		"description": description,
		"parameters":  parameters,
	}
	
	resp, err := c.makeRequest("POST", "/research/projects", request)
	if err != nil {
		return nil, fmt.Errorf("Research project creation failed: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("Research project creation failed with status: %d", resp.StatusCode)
	}
	
	var project ResearchProject
	if err := json.NewDecoder(resp.Body).Decode(&project); err != nil {
		return nil, fmt.Errorf("failed to decode research project response: %v", err)
	}
	
	return &project, nil
}

// GetResearchResults retrieves research project results
func (c *OdinClient) GetResearchResults(projectID string) (map[string]interface{}, error) {
	resp, err := c.makeRequest("GET", "/research/projects/"+projectID+"/results", nil)
	if err != nil {
		return nil, fmt.Errorf("Research results request failed: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Research results failed with status: %d", resp.StatusCode)
	}
	
	var results map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&results); err != nil {
		return nil, fmt.Errorf("failed to decode research results: %v", err)
	}
	
	return results, nil
}

// VerifyProofChain verifies a cryptographic proof chain
func (c *OdinClient) VerifyProofChain(proofData map[string]interface{}) (bool, error) {
	resp, err := c.makeRequest("POST", "/verify-proof", proofData)
	if err != nil {
		return false, fmt.Errorf("Proof verification request failed: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return false, fmt.Errorf("Proof verification failed with status: %d", resp.StatusCode)
	}
	
	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return false, fmt.Errorf("failed to decode verification response: %v", err)
	}
	
	valid, ok := result["valid"].(bool)
	if !ok {
		return false, fmt.Errorf("invalid verification response format")
	}
	
	return valid, nil
}

// ComputeDataHash computes SHA256 hash of data for integrity checks
func ComputeDataHash(data interface{}) (string, error) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return "", fmt.Errorf("failed to marshal data: %v", err)
	}
	
	hash := sha256.Sum256(jsonData)
	return base64.URLEncoding.EncodeToString(hash[:]), nil
}

// Example usage
func main() {
	// Initialize ODIN client
	client := NewOdinClient("https://api.odinprotocol.com", "your-api-key-here")
	
	// Example 1: SFT Translation
	fmt.Println("=== SFT Translation Example ===")
	sourceData := map[string]interface{}{
		"customer_id":   "12345",
		"amount":        "100.50",
		"currency":      "USD",
		"payment_type":  "credit_card",
	}
	
	translation, err := client.SFTTranslate("payment_iso20022", sourceData)
	if err != nil {
		fmt.Printf("SFT translation failed: %v\n", err)
	} else {
		fmt.Printf("Translation successful: %+v\n", translation)
	}
	
	// Example 2: Bridge Pro Workflow
	fmt.Println("\n=== Bridge Pro Workflow Example ===")
	workflow, err := client.GetBridgeProWorkflow("swift_iso20022_conversion")
	if err != nil {
		fmt.Printf("Bridge Pro workflow retrieval failed: %v\n", err)
	} else {
		fmt.Printf("Workflow details: %+v\n", workflow)
		
		// Execute workflow
		inputData := map[string]interface{}{
			"swift_message": "your-swift-message-here",
			"target_format": "iso20022",
		}
		
		result, err := client.ExecuteBridgeProWorkflow(workflow.WorkflowID, inputData)
		if err != nil {
			fmt.Printf("Bridge Pro execution failed: %v\n", err)
		} else {
			fmt.Printf("Execution result: %+v\n", result)
		}
	}
	
	// Example 3: Research Engine
	fmt.Println("\n=== Research Engine Example ===")
	parameters := map[string]interface{}{
		"model_type":     "classification",
		"dataset_size":   1000,
		"validation_split": 0.2,
		"max_epochs":     100,
	}
	
	project, err := client.CreateResearchProject(
		"Payment Fraud Detection",
		"ML model for detecting fraudulent payment transactions",
		parameters,
	)
	if err != nil {
		fmt.Printf("Research project creation failed: %v\n", err)
	} else {
		fmt.Printf("Research project created: %+v\n", project)
		
		// Simulate waiting for results (in real usage, you'd poll periodically)
		fmt.Println("Waiting for research results...")
		time.Sleep(5 * time.Second)
		
		results, err := client.GetResearchResults(project.ProjectID)
		if err != nil {
			fmt.Printf("Research results retrieval failed: %v\n", err)
		} else {
			fmt.Printf("Research results: %+v\n", results)
		}
	}
	
	// Example 4: Data Integrity Verification
	fmt.Println("\n=== Data Integrity Example ===")
	testData := map[string]interface{}{
		"transaction_id": "txn_123",
		"amount":         250.75,
		"timestamp":      time.Now().Unix(),
	}
	
	hash, err := ComputeDataHash(testData)
	if err != nil {
		fmt.Printf("Hash computation failed: %v\n", err)
	} else {
		fmt.Printf("Data hash: %s\n", hash)
		
		// Verify proof chain (example with mock data)
		proofData := map[string]interface{}{
			"data":      testData,
			"hash":      hash,
			"signature": "mock-signature",
			"timestamp": time.Now().Unix(),
		}
		
		valid, err := client.VerifyProofChain(proofData)
		if err != nil {
			fmt.Printf("Proof verification failed: %v\n", err)
		} else {
			fmt.Printf("Proof chain valid: %t\n", valid)
		}
	}
	
	fmt.Println("\n=== ODIN Protocol Go SDK Demo Complete ===")
}
