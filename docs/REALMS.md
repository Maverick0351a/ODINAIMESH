# ODIN Realms

This document describes the concept of Realms in the ODIN Gateway and how to add a new one.

## What is a Realm?

A Realm is a self-contained set of configurations that defines a specific operational domain within the ODIN Gateway. It includes policies, data transformation maps (SFTs), and other settings that govern how the gateway processes requests for that realm.

Realms allow for multi-tenancy and the separation of concerns, where different business units or partners can have their own customized gateway behavior.

## The Realm Pack

A Realm is defined by a "Realm Pack," which is a directory containing all the necessary configuration files. The structure of a Realm Pack is as follows:

```
my-realm/
├── pack.yaml
├── policy/
│   └── my-policy.json
└── sft/
    ├── registry.json
    └── maps/
        └── my-map.json
```

- `pack.yaml`: The main configuration file for the realm. It defines the realm's name, compatible ODIN Core version range, and points to the policy and SFT files.
- `policy/`: Contains the policy files for the realm. These policies are enforced by the gateway for all requests within the realm.
- `sft/`: Contains the Secure Function Transformation (SFT) configurations.
  - `registry.json`: Defines the available transformation functions.
  - `maps/`: Contains the SFT map files, which define how to transform data from one format to another.

## Adding a New Realm

To add a new realm, follow these steps:

1.  **Create a new Realm Pack:** Create a new directory for your realm and populate it with the required configuration files (`pack.yaml`, policy files, SFT files). You can use the template located in `packs/templates`.

2.  **Upload the Realm Pack to GCS:** Upload the Realm Pack directory to a GCS bucket.

3.  **Create a new Helm values file:** Create a new values file in the `helm/odin-gateway-relay` directory (e.g., `values-my-realm.yaml`). This file should set the `ODIN_REALM_PACK_URI` environment variable to the GCS path of your Realm Pack.

4.  **Deploy the new realm:** Deploy the gateway using the new values file. This will create a new Cloud Run instance configured for your realm.

```
helm upgrade --install my-realm-gateway helm/odin-gateway-relay -f helm/odin-gateway-relay/values-my-realm.yaml
```
