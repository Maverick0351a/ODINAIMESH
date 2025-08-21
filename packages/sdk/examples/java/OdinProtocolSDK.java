/**
 * ODIN Protocol Java SDK Example
 * 
 * Demonstrates how to interact with ODIN Protocol services using Java.
 * Shows SFT translation, Bridge Pro workflows, and Research Engine integration.
 */

package com.odinprotocol.sdk.example;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.*;
import org.jetbrains.annotations.NotNull;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

// ODIN Protocol Java SDK classes
public class OdinProtocolSDK {
    
    // Data classes
    public static class SftTranslationRequest {
        @JsonProperty("map_id")
        public String mapId;
        
        @JsonProperty("source_data")
        public Map<String, Object> sourceData;
        
        @JsonProperty("options")
        public Map<String, Object> options;
        
        public SftTranslationRequest(String mapId, Map<String, Object> sourceData) {
            this.mapId = mapId;
            this.sourceData = sourceData;
        }
    }
    
    public static class SftTranslationResponse {
        @JsonProperty("translated_data")
        public Map<String, Object> translatedData;
        
        @JsonProperty("cid")
        public String cid;
        
        @JsonProperty("signature")
        public String signature;
        
        @JsonProperty("timestamp")
        public String timestamp;
    }
    
    public static class BridgeProWorkflow {
        @JsonProperty("workflow_id")
        public String workflowId;
        
        @JsonProperty("source_format")
        public String sourceFormat;
        
        @JsonProperty("target_format")
        public String targetFormat;
        
        @JsonProperty("payment_required")
        public boolean paymentRequired;
        
        @JsonProperty("estimated_cost")
        public double estimatedCost;
        
        @JsonProperty("transformations")
        public List<Map<String, Object>> transformations;
    }
    
    public static class ResearchProject {
        @JsonProperty("project_id")
        public String projectId;
        
        @JsonProperty("title")
        public String title;
        
        @JsonProperty("description")
        public String description;
        
        @JsonProperty("byok_token")
        public String byokToken;
        
        @JsonProperty("parameters")
        public Map<String, Object> parameters;
    }
    
    // Main client class
    public static class OdinClient {
        private final String baseUrl;
        private final String apiKey;
        private final OkHttpClient httpClient;
        private final ObjectMapper objectMapper;
        
        public OdinClient(String baseUrl, String apiKey) {
            this.baseUrl = baseUrl;
            this.apiKey = apiKey;
            this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build();
            this.objectMapper = new ObjectMapper();
        }
        
        private Request.Builder createRequestBuilder(String endpoint) {
            Request.Builder builder = new Request.Builder()
                .url(baseUrl + endpoint)
                .addHeader("Content-Type", "application/json")
                .addHeader("Accept", "application/json");
                
            if (apiKey != null && !apiKey.isEmpty()) {
                builder.addHeader("Authorization", "Bearer " + apiKey);
            }
            
            return builder;
        }
        
        private <T> T executeRequest(Request request, Class<T> responseClass) throws IOException {
            try (Response response = httpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    throw new IOException("Request failed with status: " + response.code());
                }
                
                ResponseBody body = response.body();
                if (body == null) {
                    throw new IOException("Empty response body");
                }
                
                String responseJson = body.string();
                return objectMapper.readValue(responseJson, responseClass);
            }
        }
        
        @SuppressWarnings("unchecked")
        private Map<String, Object> executeRequestAsMap(Request request) throws IOException {
            try (Response response = httpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    throw new IOException("Request failed with status: " + response.code());
                }
                
                ResponseBody body = response.body();
                if (body == null) {
                    throw new IOException("Empty response body");
                }
                
                String responseJson = body.string();
                return objectMapper.readValue(responseJson, Map.class);
            }
        }
        
        public SftTranslationResponse sftTranslate(String mapId, Map<String, Object> sourceData) 
                throws IOException {
            SftTranslationRequest request = new SftTranslationRequest(mapId, sourceData);
            String requestJson = objectMapper.writeValueAsString(request);
            
            RequestBody body = RequestBody.create(requestJson, MediaType.get("application/json"));
            Request httpRequest = createRequestBuilder("/sft/translate")
                .post(body)
                .build();
                
            return executeRequest(httpRequest, SftTranslationResponse.class);
        }
        
        public BridgeProWorkflow getBridgeProWorkflow(String workflowId) throws IOException {
            Request request = createRequestBuilder("/bridge-pro/workflows/" + workflowId)
                .get()
                .build();
                
            return executeRequest(request, BridgeProWorkflow.class);
        }
        
        public Map<String, Object> executeBridgeProWorkflow(String workflowId, 
                Map<String, Object> inputData) throws IOException {
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("workflow_id", workflowId);
            requestBody.put("input_data", inputData);
            
            String requestJson = objectMapper.writeValueAsString(requestBody);
            RequestBody body = RequestBody.create(requestJson, MediaType.get("application/json"));
            
            Request request = createRequestBuilder("/bridge-pro/execute")
                .post(body)
                .build();
                
            return executeRequestAsMap(request);
        }
        
        public ResearchProject createResearchProject(String title, String description, 
                Map<String, Object> parameters) throws IOException {
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("title", title);
            requestBody.put("description", description);
            requestBody.put("parameters", parameters);
            
            String requestJson = objectMapper.writeValueAsString(requestBody);
            RequestBody body = RequestBody.create(requestJson, MediaType.get("application/json"));
            
            Request request = createRequestBuilder("/research/projects")
                .post(body)
                .build();
                
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.code() != 201) {
                    throw new IOException("Research project creation failed with status: " + response.code());
                }
                
                ResponseBody responseBody = response.body();
                if (responseBody == null) {
                    throw new IOException("Empty response body");
                }
                
                String responseJson = responseBody.string();
                return objectMapper.readValue(responseJson, ResearchProject.class);
            }
        }
        
        public Map<String, Object> getResearchResults(String projectId) throws IOException {
            Request request = createRequestBuilder("/research/projects/" + projectId + "/results")
                .get()
                .build();
                
            return executeRequestAsMap(request);
        }
        
        public boolean verifyProofChain(Map<String, Object> proofData) throws IOException {
            String requestJson = objectMapper.writeValueAsString(proofData);
            RequestBody body = RequestBody.create(requestJson, MediaType.get("application/json"));
            
            Request request = createRequestBuilder("/verify-proof")
                .post(body)
                .build();
                
            Map<String, Object> result = executeRequestAsMap(request);
            Object valid = result.get("valid");
            
            if (valid instanceof Boolean) {
                return (Boolean) valid;
            } else {
                throw new IOException("Invalid verification response format");
            }
        }
    }
    
    // Utility class for data integrity
    public static class DataIntegrity {
        public static String computeDataHash(Object data) throws JsonProcessingException, NoSuchAlgorithmException {
            ObjectMapper objectMapper = new ObjectMapper();
            String jsonData = objectMapper.writeValueAsString(data);
            
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(jsonData.getBytes());
            
            return Base64.getUrlEncoder().withoutPadding().encodeToString(hash);
        }
        
        public static long getCurrentTimestamp() {
            return Instant.now().getEpochSecond();
        }
    }
    
    // Example usage
    public static void main(String[] args) {
        // Initialize ODIN client
        OdinClient client = new OdinClient("https://api.odinprotocol.com", "your-api-key-here");
        
        try {
            // Example 1: SFT Translation
            System.out.println("=== SFT Translation Example ===");
            Map<String, Object> sourceData = new HashMap<>();
            sourceData.put("customer_id", "12345");
            sourceData.put("amount", "100.50");
            sourceData.put("currency", "USD");
            sourceData.put("payment_type", "credit_card");
            
            try {
                SftTranslationResponse translation = client.sftTranslate("payment_iso20022", sourceData);
                System.out.println("Translation successful: " + translation.translatedData);
                System.out.println("CID: " + translation.cid);
            } catch (IOException e) {
                System.err.println("SFT translation failed: " + e.getMessage());
            }
            
            // Example 2: Bridge Pro Workflow
            System.out.println("\n=== Bridge Pro Workflow Example ===");
            try {
                BridgeProWorkflow workflow = client.getBridgeProWorkflow("swift_iso20022_conversion");
                System.out.println("Workflow ID: " + workflow.workflowId);
                System.out.println("Source Format: " + workflow.sourceFormat);
                System.out.println("Target Format: " + workflow.targetFormat);
                System.out.println("Payment Required: " + workflow.paymentRequired);
                System.out.println("Estimated Cost: $" + workflow.estimatedCost);
                
                // Execute workflow
                Map<String, Object> inputData = new HashMap<>();
                inputData.put("swift_message", "your-swift-message-here");
                inputData.put("target_format", "iso20022");
                
                Map<String, Object> result = client.executeBridgeProWorkflow(workflow.workflowId, inputData);
                System.out.println("Execution result: " + result);
                
            } catch (IOException e) {
                System.err.println("Bridge Pro workflow failed: " + e.getMessage());
            }
            
            // Example 3: Research Engine
            System.out.println("\n=== Research Engine Example ===");
            Map<String, Object> parameters = new HashMap<>();
            parameters.put("model_type", "classification");
            parameters.put("dataset_size", 1000);
            parameters.put("validation_split", 0.2);
            parameters.put("max_epochs", 100);
            
            try {
                ResearchProject project = client.createResearchProject(
                    "Payment Fraud Detection",
                    "ML model for detecting fraudulent payment transactions",
                    parameters
                );
                
                System.out.println("Research project created:");
                System.out.println("Project ID: " + project.projectId);
                System.out.println("Title: " + project.title);
                System.out.println("Description: " + project.description);
                
                // Simulate waiting for results (in real usage, you'd poll periodically)
                System.out.println("Waiting for research results...");
                Thread.sleep(5000);
                
                Map<String, Object> results = client.getResearchResults(project.projectId);
                System.out.println("Research results: " + results);
                
            } catch (IOException | InterruptedException e) {
                System.err.println("Research Engine operation failed: " + e.getMessage());
            }
            
            // Example 4: Data Integrity Verification
            System.out.println("\n=== Data Integrity Example ===");
            Map<String, Object> testData = new HashMap<>();
            testData.put("transaction_id", "txn_123");
            testData.put("amount", 250.75);
            testData.put("timestamp", DataIntegrity.getCurrentTimestamp());
            
            try {
                String hash = DataIntegrity.computeDataHash(testData);
                System.out.println("Data hash: " + hash);
                
                // Verify proof chain (example with mock data)
                Map<String, Object> proofData = new HashMap<>();
                proofData.put("data", testData);
                proofData.put("hash", hash);
                proofData.put("signature", "mock-signature");
                proofData.put("timestamp", DataIntegrity.getCurrentTimestamp());
                
                boolean valid = client.verifyProofChain(proofData);
                System.out.println("Proof chain valid: " + valid);
                
            } catch (Exception e) {
                System.err.println("Data integrity verification failed: " + e.getMessage());
            }
            
            System.out.println("\n=== ODIN Protocol Java SDK Demo Complete ===");
            
        } catch (Exception e) {
            System.err.println("Unexpected error: " + e.getMessage());
            e.printStackTrace();
        }
    }
    
    // Unit tests (using JUnit would be better, but this shows the concept)
    public static class Tests {
        public static void testDataHash() throws Exception {
            Map<String, Object> testData = new HashMap<>();
            testData.put("key1", "value1");
            testData.put("key2", 42);
            
            String hash1 = DataIntegrity.computeDataHash(testData);
            String hash2 = DataIntegrity.computeDataHash(testData);
            
            assert hash1.equals(hash2) : "Same data should produce same hash";
            assert !hash1.isEmpty() : "Hash should not be empty";
            
            System.out.println("✅ Data hash test passed");
        }
        
        public static void testClientCreation() {
            OdinClient client = new OdinClient("https://test.example.com", "test-key");
            assert client.baseUrl.equals("https://test.example.com") : "Base URL should match";
            assert client.apiKey.equals("test-key") : "API key should match";
            
            System.out.println("✅ Client creation test passed");
        }
        
        public static void runAllTests() {
            try {
                testDataHash();
                testClientCreation();
                System.out.println("✅ All tests passed!");
            } catch (Exception e) {
                System.err.println("❌ Test failed: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }
}
