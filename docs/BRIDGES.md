# ODIN Bridges

This document describes the concept of Bridges in the ODIN Gateway and how to add a new one.

## What is a Bridge?

A Bridge connects two different Realms, allowing for secure and controlled communication between them. It defines how to transform data from a source realm's format to a target realm's format, and what policies to apply during the process.

Bridges are essential for interoperability between different domains, enabling use cases like cross-organizational data exchange.

## Bridge Configuration

A Bridge is defined by a YAML configuration file located in the `configs/bridges` directory. The naming convention for the file is `source-realm_to_target-realm.yaml`.

The configuration file has the following structure:

```yaml
# Bridge configuration for transforming from Source to Target

source_realm: "source"
target_realm: "target"

# The SFT map to use for the transformation.
sft_map: "source_to_target.json"

# Policy to enforce on the bridge.
policy:
  rules:
    - effect: "allow"
      action: "bridge"
      resource: "urn:odin:bridge:source-to-target"
```

- `source_realm`: The name of the source realm.
- `target_realm`: The name of the target realm.
- `sft_map`: The name of the SFT map file to use for the transformation. This map must be available in the target realm's pack.
- `policy`: A policy that is enforced on the bridge, in addition to the target realm's policy.

## How it Works

When the gateway receives a request with the `X-ODIN-Target-Realm` header, it looks for a corresponding bridge configuration file. If a configuration is found, the gateway:

1.  Loads the specified SFT map.
2.  Transforms the request payload using the SFT map.
3.  Enforces the bridge's policy.
4.  Forwards the transformed request to the target realm (if a `target_url` is provided in the request).

## Adding a New Bridge

To add a new bridge, follow these steps:

1.  **Create a new bridge configuration file:** Create a new YAML file in the `configs/bridges` directory with the name `source-realm_to_target-realm.yaml`.

2.  **Define the bridge configuration:** Populate the configuration file with the source and target realm names, the SFT map to use, and the bridge's policy.

3.  **Ensure the SFT map exists:** Make sure the SFT map specified in the bridge configuration is available in the target realm's pack.

4.  **Deploy the changes:** Deploy the updated gateway configuration. The new bridge will be active immediately.
