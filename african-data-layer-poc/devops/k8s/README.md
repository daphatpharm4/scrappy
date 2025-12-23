# Kubernetes notes

- Apply the namespace, MinIO, and service deployments:
  ```bash
  kubectl apply -f minio.yaml
  kubectl apply -f services.yaml
  ```
- Update `ghcr.io/example/*` images to your registry paths.
- Secrets are stored in `datalayer-secrets` for demo only; use your secret manager for production and rotate credentials.
- Health probes align with the FastAPI `/health` endpoints exposed by each service.
