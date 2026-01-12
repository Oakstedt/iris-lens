# NGP IRIS 5 changelog
## Summary
IRIS 5 is a complete overhaul of the previous versions of IRIS, mainly in terms of its codebase. The general functionality like download from and upload to the HCP are still here, but might differ from previous versions.

## Changelog IRIS 5.0.0
| **Type of change** | **Change** |
| ------------------ | ---------- |
| Change   | The `iris` command `delete` is replaced by `delete-folder` and `delete-object` |
| Addition | The `iris` command `list-buckets` was added |
| Addition | The `iris` command `list-objects` was added |
| Change   | The `iris` command `search` is replaced by `simple-search` |
| Removal  | The `iris` command `utils` was removed |
| Addition | The new `iris_generate_credentials_file` command was added |
| Change   | The structure of the credentials file was altered |
| Change   | The class name `HCPManager` was changed to `HCPHandler` with its new set of parameters |
| Change   | The class class methods `HCPManager.set_bucket` and `HCPManager.attach_bucket` was replaced by `HCPHandler.mount_bucket` |
| Removal  | `HCPManager.delete_key` was removed |
| Addition | `HCPHandler.get_response` was added |
| Addition | `HCPHandler.list_objects` was added |
| Addition | `HCPHandler.object_exists` was added |
| Addition | `HCPHandler.upload_folder` was added |
| Addition | `HCPHandler.delete_objects` was added |
| Addition | `HCPHandler.delete_folder` was added |
| Addition | `HCPHandler.search_objects_in_bucket` was added |
| Addition | `HCPHandler.get_object_acl` was added |
| Addition | `HCPHandler.get_bucket_acl` was added |
| Addition | `HCPHandler.modify_single_object_acl` was added |
| Addition | `HCPHandler.modify_single_bucket_acl` was added |
| Addition | `HCPHandler.modify_object_acl` was added |
| Addition | `HCPHandler.modify_bucket_acl` was added |
| Addition | A new module for HCP statistics called `statistics.py` was added |
| Change   | The class name `HCIManager` was changed to `HCIHandler` with its new set of parameters |
| Removal  | `HCIManager.get_password` was removed |
| Removal  | `HCIManager.create_template` was removed |
| Removal  | `HCIManager.generate_token` was removed |
| Removal  | `HCIManager.query` was removed |
| Removal  | `HCIManager.pretty_query` was removed |
| Removal  | `HCIManager.get_index` was removed |
| Addition | `HCIHandler.request_token` was added |
| Addition | `HCIHandler.list_index_names` was added |
| Addition | `HCIHandler.look_up_index` was added |
| Addition | `HCIHandler.raw_query` was added |
| Addition | `HCIHandler.raw_query_from_JSON` was added |