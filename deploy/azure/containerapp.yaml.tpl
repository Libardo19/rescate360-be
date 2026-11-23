location: __LOCATION__
name: __APP_NAME__
properties:
  environmentId: __ENVIRONMENT_ID__
  template:
    containers:
      - name: rescate360-api
        image: __IMAGE__
        env:
          - name: APP_ENV
            value: production
          - name: PORT
            value: "8000"
          - name: REDIS_URL
            value: redis://localhost:6379/0
          - name: STORAGE_BACKEND
            value: azure
          - name: DATABASE_URL
            secretRef: database-url
          - name: JWT_SECRET
            secretRef: jwt-secret
          - name: STORAGE_BUCKET
            secretRef: storage-bucket
          - name: AZURE_STORAGE_CONNECTION_STRING
            secretRef: azure-storage-connection-string
          - name: AZURE_STORAGE_ACCOUNT_NAME
            secretRef: azure-storage-account-name
          - name: CORS_ORIGINS
            secretRef: cors-origins
__OPTIONAL_ENV__
        resources:
          cpu: 0.25
          memory: 0.5Gi
        probes:
          - type: liveness
            initialDelaySeconds: 60
            failureThreshold: 10
            periodSeconds: 10
            timeoutSeconds: 5
            httpGet:
              path: /health
              port: 8000
          - type: readiness
            initialDelaySeconds: 60
            failureThreshold: 10
            periodSeconds: 10
            timeoutSeconds: 5
            httpGet:
              path: /health/ready
              port: 8000
    scale:
      minReplicas: 0
      maxReplicas: 1
      rules:
        - name: http
          http:
            metadata:
              concurrentRequests: '10'
  configuration:
    registries:
      - server: __ACR_SERVER__
        username: __ACR_USERNAME__
        passwordSecretRef: acr-password
    ingress:
      external: true
      allowInsecure: false
      targetPort: 8000
      transport: http
    secrets:
      - name: database-url
        value: __DATABASE_URL__
      - name: jwt-secret
        value: __JWT_SECRET__
      - name: storage-bucket
        value: __STORAGE_BUCKET__
      - name: azure-storage-connection-string
        value: __AZURE_STORAGE_CONNECTION_STRING__
      - name: azure-storage-account-name
        value: __AZURE_STORAGE_ACCOUNT_NAME__
      - name: cors-origins
        value: __CORS_ORIGINS__
__OPTIONAL_SECRETS__
      - name: acr-password
        value: __ACR_PASSWORD__
