# ODIN Protocol Rust SDK Example

This example demonstrates how to integrate with ODIN Protocol services using Rust.

```rust
//! ODIN Protocol Rust SDK Example
//! 
//! Demonstrates how to interact with ODIN Protocol services using Rust.
//! Shows SFT translation, Bridge Pro workflows, and Research Engine integration.

use serde::{Deserialize, Serialize};
use reqwest::{Client, Response};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};
use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};

// ODIN Protocol Rust SDK structures
#[derive(Debug, Clone)]
pub struct OdinClient {
    base_url: String,
    api_key: String,
    client: Client,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SftTranslationRequest {
    pub map_id: String,
    pub source_data: HashMap<String, serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SftTranslationResponse {
    pub translated_data: HashMap<String, serde_json::Value>,
    pub cid: String,
    pub signature: String,
    pub timestamp: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct BridgeProWorkflow {
    pub workflow_id: String,
    pub source_format: String,
    pub target_format: String,
    pub payment_required: bool,
    pub estimated_cost: f64,
    pub transformations: Vec<HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ResearchProject {
    pub project_id: String,
    pub title: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub byok_token: Option<String>,
    pub parameters: HashMap<String, serde_json::Value>,
}

#[derive(Debug)]
pub enum OdinError {
    NetworkError(reqwest::Error),
    SerializationError(serde_json::Error),
    ApiError { status: u16, message: String },
    HashError(String),
}

impl std::fmt::Display for OdinError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OdinError::NetworkError(e) => write!(f, "Network error: {}", e),
            OdinError::SerializationError(e) => write!(f, "Serialization error: {}", e),
            OdinError::ApiError { status, message } => write!(f, "API error {}: {}", status, message),
            OdinError::HashError(e) => write!(f, "Hash error: {}", e),
        }
    }
}

impl std::error::Error for OdinError {}

impl From<reqwest::Error> for OdinError {
    fn from(error: reqwest::Error) -> Self {
        OdinError::NetworkError(error)
    }
}

impl From<serde_json::Error> for OdinError {
    fn from(error: serde_json::Error) -> Self {
        OdinError::SerializationError(error)
    }
}

impl OdinClient {
    /// Create a new ODIN Protocol client
    pub fn new(base_url: String, api_key: String) -> Self {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");
            
        Self {
            base_url,
            api_key,
            client,
        }
    }
    
    /// Make an HTTP request to the ODIN API
    async fn make_request<T: Serialize>(
        &self,
        method: &str,
        endpoint: &str,
        body: Option<&T>,
    ) -> Result<Response, OdinError> {
        let url = format!("{}{}", self.base_url, endpoint);
        
        let mut request = match method {
            "GET" => self.client.get(&url),
            "POST" => self.client.post(&url),
            "PUT" => self.client.put(&url),
            "DELETE" => self.client.delete(&url),
            _ => return Err(OdinError::ApiError {
                status: 400,
                message: format!("Unsupported HTTP method: {}", method),
            }),
        };
        
        request = request
            .header("Content-Type", "application/json")
            .header("Accept", "application/json");
            
        if !self.api_key.is_empty() {
            request = request.header("Authorization", format!("Bearer {}", self.api_key));
        }
        
        if let Some(body) = body {
            request = request.json(body);
        }
        
        Ok(request.send().await?)
    }
    
    /// Perform SFT translation
    pub async fn sft_translate(
        &self,
        map_id: &str,
        source_data: HashMap<String, serde_json::Value>,
    ) -> Result<SftTranslationResponse, OdinError> {
        let request = SftTranslationRequest {
            map_id: map_id.to_string(),
            source_data,
            options: None,
        };
        
        let response = self.make_request("POST", "/sft/translate", Some(&request)).await?;
        
        if !response.status().is_success() {
            return Err(OdinError::ApiError {
                status: response.status().as_u16(),
                message: format!("SFT translation failed"),
            });
        }
        
        let result: SftTranslationResponse = response.json().await?;
        Ok(result)
    }
    
    /// Get Bridge Pro workflow details
    pub async fn get_bridge_pro_workflow(
        &self,
        workflow_id: &str,
    ) -> Result<BridgeProWorkflow, OdinError> {
        let endpoint = format!("/bridge-pro/workflows/{}", workflow_id);
        let response = self.make_request::<()>("GET", &endpoint, None).await?;
        
        if !response.status().is_success() {
            return Err(OdinError::ApiError {
                status: response.status().as_u16(),
                message: format!("Bridge Pro workflow retrieval failed"),
            });
        }
        
        let workflow: BridgeProWorkflow = response.json().await?;
        Ok(workflow)
    }
    
    /// Execute Bridge Pro workflow
    pub async fn execute_bridge_pro_workflow(
        &self,
        workflow_id: &str,
        input_data: HashMap<String, serde_json::Value>,
    ) -> Result<HashMap<String, serde_json::Value>, OdinError> {
        let mut request_body = HashMap::new();
        request_body.insert("workflow_id".to_string(), serde_json::Value::String(workflow_id.to_string()));
        request_body.insert("input_data".to_string(), serde_json::Value::Object(
            input_data.into_iter().collect()
        ));
        
        let response = self.make_request("POST", "/bridge-pro/execute", Some(&request_body)).await?;
        
        if !response.status().is_success() {
            return Err(OdinError::ApiError {
                status: response.status().as_u16(),
                message: format!("Bridge Pro execution failed"),
            });
        }
        
        let result: HashMap<String, serde_json::Value> = response.json().await?;
        Ok(result)
    }
    
    /// Create a new research project
    pub async fn create_research_project(
        &self,
        title: &str,
        description: &str,
        parameters: HashMap<String, serde_json::Value>,
    ) -> Result<ResearchProject, OdinError> {
        let mut request_body = HashMap::new();
        request_body.insert("title".to_string(), serde_json::Value::String(title.to_string()));
        request_body.insert("description".to_string(), serde_json::Value::String(description.to_string()));
        request_body.insert("parameters".to_string(), serde_json::Value::Object(
            parameters.into_iter().collect()
        ));
        
        let response = self.make_request("POST", "/research/projects", Some(&request_body)).await?;
        
        if response.status() != 201 {
            return Err(OdinError::ApiError {
                status: response.status().as_u16(),
                message: format!("Research project creation failed"),
            });
        }
        
        let project: ResearchProject = response.json().await?;
        Ok(project)
    }
    
    /// Get research project results
    pub async fn get_research_results(
        &self,
        project_id: &str,
    ) -> Result<HashMap<String, serde_json::Value>, OdinError> {
        let endpoint = format!("/research/projects/{}/results", project_id);
        let response = self.make_request::<()>("GET", &endpoint, None).await?;
        
        if !response.status().is_success() {
            return Err(OdinError::ApiError {
                status: response.status().as_u16(),
                message: format!("Research results retrieval failed"),
            });
        }
        
        let results: HashMap<String, serde_json::Value> = response.json().await?;
        Ok(results)
    }
    
    /// Verify cryptographic proof chain
    pub async fn verify_proof_chain(
        &self,
        proof_data: HashMap<String, serde_json::Value>,
    ) -> Result<bool, OdinError> {
        let response = self.make_request("POST", "/verify-proof", Some(&proof_data)).await?;
        
        if !response.status().is_success() {
            return Err(OdinError::ApiError {
                status: response.status().as_u16(),
                message: format!("Proof verification failed"),
            });
        }
        
        let result: HashMap<String, serde_json::Value> = response.json().await?;
        
        match result.get("valid") {
            Some(serde_json::Value::Bool(valid)) => Ok(*valid),
            _ => Err(OdinError::ApiError {
                status: 500,
                message: "Invalid verification response format".to_string(),
            }),
        }
    }
}

/// Compute SHA256 hash of data for integrity checks
pub fn compute_data_hash<T: Serialize>(data: &T) -> Result<String, OdinError> {
    let json_data = serde_json::to_vec(data)
        .map_err(|e| OdinError::HashError(format!("Failed to serialize data: {}", e)))?;
    
    let mut hasher = Sha256::new();
    hasher.update(&json_data);
    let hash = hasher.finalize();
    
    Ok(URL_SAFE_NO_PAD.encode(&hash))
}

/// Get current Unix timestamp
pub fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards")
        .as_secs()
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize ODIN client
    let client = OdinClient::new(
        "https://api.odinprotocol.com".to_string(),
        "your-api-key-here".to_string(),
    );
    
    // Example 1: SFT Translation
    println!("=== SFT Translation Example ===");
    let mut source_data = HashMap::new();
    source_data.insert("customer_id".to_string(), serde_json::Value::String("12345".to_string()));
    source_data.insert("amount".to_string(), serde_json::Value::String("100.50".to_string()));
    source_data.insert("currency".to_string(), serde_json::Value::String("USD".to_string()));
    source_data.insert("payment_type".to_string(), serde_json::Value::String("credit_card".to_string()));
    
    match client.sft_translate("payment_iso20022", source_data).await {
        Ok(translation) => println!("Translation successful: {:?}", translation),
        Err(e) => println!("SFT translation failed: {}", e),
    }
    
    // Example 2: Bridge Pro Workflow
    println!("\n=== Bridge Pro Workflow Example ===");
    match client.get_bridge_pro_workflow("swift_iso20022_conversion").await {
        Ok(workflow) => {
            println!("Workflow details: {:?}", workflow);
            
            // Execute workflow
            let mut input_data = HashMap::new();
            input_data.insert("swift_message".to_string(), serde_json::Value::String("your-swift-message-here".to_string()));
            input_data.insert("target_format".to_string(), serde_json::Value::String("iso20022".to_string()));
            
            match client.execute_bridge_pro_workflow(&workflow.workflow_id, input_data).await {
                Ok(result) => println!("Execution result: {:?}", result),
                Err(e) => println!("Bridge Pro execution failed: {}", e),
            }
        }
        Err(e) => println!("Bridge Pro workflow retrieval failed: {}", e),
    }
    
    // Example 3: Research Engine
    println!("\n=== Research Engine Example ===");
    let mut parameters = HashMap::new();
    parameters.insert("model_type".to_string(), serde_json::Value::String("classification".to_string()));
    parameters.insert("dataset_size".to_string(), serde_json::Value::Number(serde_json::Number::from(1000)));
    parameters.insert("validation_split".to_string(), serde_json::Value::Number(serde_json::Number::from_f64(0.2).unwrap()));
    parameters.insert("max_epochs".to_string(), serde_json::Value::Number(serde_json::Number::from(100)));
    
    match client.create_research_project(
        "Payment Fraud Detection",
        "ML model for detecting fraudulent payment transactions",
        parameters,
    ).await {
        Ok(project) => {
            println!("Research project created: {:?}", project);
            
            // Simulate waiting for results (in real usage, you'd poll periodically)
            println!("Waiting for research results...");
            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
            
            match client.get_research_results(&project.project_id).await {
                Ok(results) => println!("Research results: {:?}", results),
                Err(e) => println!("Research results retrieval failed: {}", e),
            }
        }
        Err(e) => println!("Research project creation failed: {}", e),
    }
    
    // Example 4: Data Integrity Verification
    println!("\n=== Data Integrity Example ===");
    let mut test_data = HashMap::new();
    test_data.insert("transaction_id".to_string(), serde_json::Value::String("txn_123".to_string()));
    test_data.insert("amount".to_string(), serde_json::Value::Number(serde_json::Number::from_f64(250.75).unwrap()));
    test_data.insert("timestamp".to_string(), serde_json::Value::Number(serde_json::Number::from(current_timestamp())));
    
    match compute_data_hash(&test_data) {
        Ok(hash) => {
            println!("Data hash: {}", hash);
            
            // Verify proof chain (example with mock data)
            let mut proof_data = HashMap::new();
            proof_data.insert("data".to_string(), serde_json::Value::Object(
                test_data.into_iter().collect()
            ));
            proof_data.insert("hash".to_string(), serde_json::Value::String(hash));
            proof_data.insert("signature".to_string(), serde_json::Value::String("mock-signature".to_string()));
            proof_data.insert("timestamp".to_string(), serde_json::Value::Number(serde_json::Number::from(current_timestamp())));
            
            match client.verify_proof_chain(proof_data).await {
                Ok(valid) => println!("Proof chain valid: {}", valid),
                Err(e) => println!("Proof verification failed: {}", e),
            }
        }
        Err(e) => println!("Hash computation failed: {}", e),
    }
    
    println!("\n=== ODIN Protocol Rust SDK Demo Complete ===");
    Ok(())
}

// Unit tests
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_data_hash() {
        let mut test_data = HashMap::new();
        test_data.insert("key1".to_string(), serde_json::Value::String("value1".to_string()));
        test_data.insert("key2".to_string(), serde_json::Value::Number(serde_json::Number::from(42)));
        
        let hash = compute_data_hash(&test_data).unwrap();
        assert!(!hash.is_empty());
        
        // Same data should produce same hash
        let hash2 = compute_data_hash(&test_data).unwrap();
        assert_eq!(hash, hash2);
    }
    
    #[test]
    fn test_client_creation() {
        let client = OdinClient::new(
            "https://test.example.com".to_string(),
            "test-key".to_string(),
        );
        assert_eq!(client.base_url, "https://test.example.com");
        assert_eq!(client.api_key, "test-key");
    }
    
    #[tokio::test]
    async fn test_error_handling() {
        let client = OdinClient::new(
            "https://invalid-url-that-does-not-exist.com".to_string(),
            "test-key".to_string(),
        );
        
        let source_data = HashMap::new();
        let result = client.sft_translate("test", source_data).await;
        assert!(result.is_err());
    }
}
```

## Cargo.toml

```toml
[package]
name = "odin-protocol-rust-sdk"
version = "1.0.0"
edition = "2021"
authors = ["ODIN Protocol Team"]
description = "Rust SDK for ODIN Protocol - Secure AI-to-AI communication"
license = "MIT"
homepage = "https://odinprotocol.com"
repository = "https://github.com/odinprotocol/odin"

[dependencies]
tokio = { version = "1.0", features = ["full"] }
reqwest = { version = "0.11", features = ["json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sha2 = "0.10"
base64 = "0.21"

[dev-dependencies]
tokio-test = "0.4"

[[bin]]
name = "odin_example"
path = "src/main.rs"
```

## Build and Run Instructions

```bash
# Add to Cargo.toml and run:
cargo build --release
cargo run

# Run tests:
cargo test

# Create documentation:
cargo doc --open
```

This Rust SDK provides:

1. **Type-safe API client** with proper error handling
2. **Async/await support** using Tokio
3. **Cryptographic utilities** for data integrity
4. **Comprehensive examples** for all major ODIN features
5. **Unit tests** for reliability
6. **Proper documentation** and error messages
7. **Production-ready code** with timeout handling and proper HTTP headers
