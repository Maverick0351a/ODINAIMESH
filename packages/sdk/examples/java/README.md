# ODIN Protocol Java SDK

This Maven project demonstrates how to integrate with ODIN Protocol services using Java.

## Dependencies (pom.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.odinprotocol</groupId>
    <artifactId>odin-protocol-java-sdk</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <name>ODIN Protocol Java SDK</name>
    <description>Java SDK for ODIN Protocol - Secure AI-to-AI communication</description>
    <url>https://odinprotocol.com</url>
    
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    
    <dependencies>
        <!-- HTTP client -->
        <dependency>
            <groupId>com.squareup.okhttp3</groupId>
            <artifactId>okhttp</artifactId>
            <version>4.12.0</version>
        </dependency>
        
        <!-- JSON processing -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-core</artifactId>
            <version>2.15.2</version>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <version>2.15.2</version>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-annotations</artifactId>
            <version>2.15.2</version>
        </dependency>
        
        <!-- Logging -->
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>2.0.7</version>
        </dependency>
        <dependency>
            <groupId>ch.qos.logback</groupId>
            <artifactId>logback-classic</artifactId>
            <version>1.4.8</version>
        </dependency>
        
        <!-- Testing -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-core</artifactId>
            <version>5.4.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <source>11</source>
                    <target>11</target>
                </configuration>
            </plugin>
            
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.1.2</version>
            </plugin>
            
            <plugin>
                <groupId>org.codehaus.mojo</groupId>
                <artifactId>exec-maven-plugin</artifactId>
                <version>3.1.0</version>
                <configuration>
                    <mainClass>com.odinprotocol.sdk.example.OdinProtocolSDK</mainClass>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

## Build and Run Instructions

```bash
# Compile the project
mvn clean compile

# Run the example
mvn exec:java

# Run tests
mvn test

# Package as JAR
mvn package

# Generate documentation
mvn javadoc:javadoc
```

## Features

This Java SDK provides:

1. **Type-safe API client** with proper error handling
2. **JSON serialization/deserialization** using Jackson
3. **HTTP client** with timeout and connection management
4. **Cryptographic utilities** for data integrity
5. **Comprehensive examples** for all major ODIN features
6. **Unit tests** using JUnit 5
7. **Maven project structure** for easy integration
8. **Enterprise-ready code** with proper logging and error handling

## Usage Examples

### Basic Client Setup

```java
OdinClient client = new OdinClient("https://api.odinprotocol.com", "your-api-key");
```

### SFT Translation

```java
Map<String, Object> sourceData = new HashMap<>();
sourceData.put("customer_id", "12345");
sourceData.put("amount", "100.50");

SftTranslationResponse result = client.sftTranslate("payment_iso20022", sourceData);
```

### Bridge Pro Workflow

```java
BridgeProWorkflow workflow = client.getBridgeProWorkflow("swift_iso20022_conversion");
Map<String, Object> result = client.executeBridgeProWorkflow(workflow.workflowId, inputData);
```

### Research Engine

```java
Map<String, Object> parameters = new HashMap<>();
parameters.put("model_type", "classification");

ResearchProject project = client.createResearchProject(
    "Fraud Detection", 
    "ML model for fraud detection", 
    parameters
);
```

### Data Integrity

```java
String hash = DataIntegrity.computeDataHash(data);
boolean valid = client.verifyProofChain(proofData);
```

## Integration Notes

- **Thread Safety**: The OdinClient is thread-safe and can be shared across multiple threads
- **Connection Pooling**: OkHttpClient automatically manages connection pooling
- **Error Handling**: All API methods throw IOException for network/API errors
- **Timeout Configuration**: Default 30-second timeout for all requests
- **Logging**: Uses SLF4J for logging integration with your application

## Environment Configuration

Set environment variables for configuration:

```bash
export ODIN_API_URL="https://api.odinprotocol.com"
export ODIN_API_KEY="your-api-key-here"
```

## Testing

The SDK includes comprehensive unit tests:

```bash
mvn test
```

For integration testing, set up a test environment and configure the appropriate endpoints.
