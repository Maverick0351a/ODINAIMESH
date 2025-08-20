import os
import yaml
import json
from semantic_version import Spec, Version
from google.cloud import storage
import logging
import tarfile
from io import BytesIO

# A placeholder for the actual core version of the gateway
ODIN_CORE_VERSION = "1.0.0-rc1"

logger = logging.getLogger(__name__)

class RealmPackLoader:
    def __init__(self):
        self.realm_pack = None
        self.hel_policy = None
        self.sft_registry = None
        self.sft_maps = {}
        self.pack_base_path = None

    @property
    def realm_name(self):
        return self.realm_pack.get("realm_name") if self.realm_pack else None

    @property
    def egress_allowlist(self):
        return self.realm_pack.get("egress_allowlist", []) if self.realm_pack else []

    def load_pack(self, pack_uri):
        """Loads and validates a realm pack from a local path, GCS URI, or GCS .tgz archive."""
        logger.info(f"Loading realm pack from: {pack_uri}")
        if pack_uri.startswith("gs://"):
            if pack_uri.endswith(".tgz"):
                self._load_from_gcs_archive(pack_uri)
            else:
                self._load_from_gcs_directory(pack_uri)
        else:
            self._load_from_local(pack_uri)

        self._validate_pack()
        self._load_hel()
        self._load_sft()
        logger.info(f"Successfully loaded and validated realm pack: {self.realm_name} v{self.realm_pack.get('version')}")

    def _load_from_gcs_directory(self, gcs_uri):
        """Loads pack files from a GCS bucket directory."""
        # This implementation is a stub. A real implementation would need to list files
        # and download them, reconstructing the directory structure in memory or on disk.
        logger.warning("Loading from GCS directory is not fully implemented. Using stubs.")
        # As a stub, we'll assume a convention that the pack.yaml is at the root.
        try:
            storage_client = storage.Client()
            bucket_name, blob_prefix = gcs_uri.replace("gs://", "").split("/", 1)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(f"{blob_prefix}/pack.yaml")
            if not blob.exists():
                raise FileNotFoundError(f"pack.yaml not found in GCS at {gcs_uri}")
            self.realm_pack = yaml.safe_load(blob.download_as_bytes())
            self.pack_base_path = gcs_uri # Store the base URI for resolving other files
        except Exception as e:
            logger.error(f"Failed to load pack.yaml from GCS directory {gcs_uri}: {e}")
            raise

    def _load_from_gcs_archive(self, gcs_uri):
        """Downloads a .tgz archive from GCS and loads the pack from it."""
        logger.info(f"Downloading and extracting GCS archive: {gcs_uri}")
        try:
            storage_client = storage.Client()
            bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            if not blob.exists():
                raise FileNotFoundError(f"GCS archive not found at {gcs_uri}")
            
            archive_bytes = blob.download_as_bytes()
            tar_file = tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz")
            
            # We need to find pack.yaml first to know the structure
            pack_yaml_member = None
            for member in tar_file.getmembers():
                if os.path.basename(member.name) == 'pack.yaml':
                    pack_yaml_member = member
                    break
            
            if not pack_yaml_member:
                raise FileNotFoundError("pack.yaml not found in the archive.")

            # The base path inside the tarball is the directory containing pack.yaml
            self.pack_base_path = os.path.dirname(pack_yaml_member.name)
            
            pack_yaml_file = tar_file.extractfile(pack_yaml_member)
            self.realm_pack = yaml.safe_load(pack_yaml_file)

            # Now load other files relative to the pack_base_path
            # This part is still a stub and needs full implementation for HEL/SFT
            logger.info("Archive extracted, pack.yaml loaded. Further file loading (HEL/SFT) is stubbed.")

        except Exception as e:
            logger.error(f"Failed to load and extract GCS archive {gcs_uri}: {e}")
            raise

    def _load_from_local(self, local_path):
        self.pack_base_path = local_path
        pack_path = os.path.join(local_path, "pack.yaml")
        if not os.path.exists(pack_path):
            raise FileNotFoundError(f"pack.yaml not found at local path: {pack_path}")
        with open(pack_path, 'r') as f:
            self.realm_pack = yaml.safe_load(f)

    def _validate_pack(self):
        if not self.realm_pack:
            raise ValueError("Realm pack not loaded.")

        core_range_str = self.realm_pack.get("core_range")
        if not core_range_str:
            raise ValueError("core_range not specified in pack.yaml")

        try:
            core_range_spec = Spec(core_range_str)
        except ValueError as e:
            raise ValueError(f"Invalid core_range '{core_range_str}' in pack.yaml: {e}")

        core_version = Version(ODIN_CORE_VERSION)
        if core_version not in core_range_spec:
            raise ValueError(
                f"Core version {core_version} does not satisfy the required range {core_range_spec} "
                f"for realm '{self.realm_name}'"
            )
        logger.info(f"Core version {core_version} validated against required range {core_range_spec}.")

    def _load_hel(self):
        # TODO: Implement full HEL loading from local path or GCS URI/archive
        policy_config = self.realm_pack.get("policy", {})
        files = policy_config.get("files", [])
        if not files:
            logger.warning(f"No policy files listed in pack.yaml for realm '{self.realm_name}'.")
            return
        logger.info(f"HEL loading for realm '{self.realm_name}': {files} (STUBBED)")
        # In a real implementation, you would use self.pack_base_path to resolve and load these files.
        pass

    def _load_sft(self):
        # TODO: Implement full SFT loading from local path or GCS URI/archive
        sft_config = self.realm_pack.get("sft", {})
        registry_file = sft_config.get("registry")
        map_files = sft_config.get("maps", [])
        if not registry_file:
            logger.warning(f"No SFT registry specified in pack.yaml for realm '{self.realm_name}'.")
        else:
            logger.info(f"SFT registry loading for realm '{self.realm_name}': {registry_file} (STUBBED)")
        
        if not map_files:
            logger.info(f"No SFT maps listed in pack.yaml for realm '{self.realm_name}'.")
        else:
            logger.info(f"SFT map loading for realm '{self.realm_name}': {map_files} (STUBBED)")
        # In a real implementation, you would use self.pack_base_path to resolve and load these files.
        pass

    def get_hel_policy(self):
        # This would return the fully loaded and combined HEL policy object
        return self.hel_policy

    def get_sft_registry(self):
        return self.sft_registry

    def get_sft_map(self, map_name):
        return self.sft_maps.get(map_name)

    def reload(self):
        """Reload the realm pack from the current ODIN_REALM_PACK_URI environment variable."""
        import os
        pack_uri = os.getenv("ODIN_REALM_PACK_URI")
        if pack_uri:
            logger.info(f"Reloading realm pack from: {pack_uri}")
            self.load_pack(pack_uri)
        else:
            logger.warning("No ODIN_REALM_PACK_URI set for reload")

# Global instance
realm_pack_loader = RealmPackLoader()

def get_realm_pack_loader():
    return realm_pack_loader
