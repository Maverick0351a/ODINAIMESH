
# gcloud config set project
python.exe : ERROR: (gcloud) Invalid choice: 'config set project odin-producer'.
At C:\Users\Maver\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1:114 char:3
+   & "$cloudsdk_python" $run_args_array
+   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (ERROR: (gcloud)...odin-producer'.:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
Maybe you meant:
  gcloud config get
  gcloud config list
  gcloud config set
  gcloud config unset

To search the help text of gcloud commands, run:
  gcloud help -- SEARCH_TERMS



# AR: gateway tags (raw)
python.exe : ERROR: (gcloud) Invalid choice: 'artifacts docker tags list 
us-central1-docker.pkg.dev/odin-producer/odin/gateway --format json'.
At C:\Users\Maver\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1:114 char:3
+   & "$cloudsdk_python" $run_args_array
+   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (ERROR: (gcloud)...--format json'.:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
Maybe you meant:
  gcloud artifacts apt
  gcloud artifacts attachments
  gcloud artifacts files
  gcloud artifacts generic
  gcloud artifacts go
  gcloud artifacts locations
  gcloud artifacts operations
  gcloud artifacts packages
  gcloud artifacts print-settings
  gcloud artifacts repositories

To search the help text of gcloud commands, run:
  gcloud help -- SEARCH_TERMS



# AR: relay tags (raw)
python.exe : ERROR: (gcloud) Invalid choice: 'artifacts docker tags list us-central1-docker.pkg.dev/odin-producer/odin/relay 
--format json'.
At C:\Users\Maver\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1:114 char:3
+   & "$cloudsdk_python" $run_args_array
+   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (ERROR: (gcloud)...--format json'.:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
Maybe you meant:
  gcloud artifacts apt
  gcloud artifacts attachments
  gcloud artifacts files
  gcloud artifacts generic
  gcloud artifacts go
  gcloud artifacts locations
  gcloud artifacts operations
  gcloud artifacts packages
  gcloud artifacts print-settings
  gcloud artifacts repositories

To search the help text of gcloud commands, run:
  gcloud help -- SEARCH_TERMS



# Cloud Run URL (gateway)



# Cloud Run URL (relay)
https://odin-relay-2gdlxqcina-uc.a.run.app


# Relay /metrics (first 10 lines)
Invoke-WebRequest : 


403 Forbidden


Error: Forbidden
Your client does not have permission to get URL /metrics from this server.




# POST /relay httpbin (first 500 chars)




# POST /relay metadata (first 500 chars)




