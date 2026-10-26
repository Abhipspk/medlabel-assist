# From laptop to AWS (design mapping)

| This project (local, free) | AWS equivalent | Why |
|---|---|---|
| Ollama + Qwen | Amazon Bedrock (Claude / Llama / Titan) | Managed models, no GPU ops, per-token pricing |
| Qdrant local + BM25 | OpenSearch Service (hybrid: k-NN + BM25) or Aurora PostgreSQL + pgvector | Managed hybrid retrieval |
| bge-small + reranker | Bedrock Titan Embeddings / Cohere Rerank, or SageMaker endpoint | Scaling, no model hosting on the app |
| FastAPI + Docker | ECS Fargate behind an ALB (or Lambda + API Gateway for spiky traffic) | Serverless containers |
| JWT + demo users | Amazon Cognito (or corporate SSO via IAM Identity Center) | Real identity, MFA, rotation |
| Hash-chained audit.jsonl | S3 with Object Lock (COMPLIANCE) + CloudTrail | WORM, regulator-grade retention |
| Secrets in env vars | AWS Secrets Manager | Rotation, access audit |
| traces.jsonl + /metrics | CloudWatch + X-Ray (or Langfuse / Grafana) | Dashboards, alarms on p95 latency and refusal rate |
| GitHub Actions + gate | CodePipeline/CodeBuild or GitHub Actions + ECR | Build, scan, deploy image |
| PII regex | Amazon Comprehend PII detection / Bedrock Guardrails | Stronger detection, managed policy |
| Prompt-injection regex | Bedrock Guardrails prompt-attack filter + our layers | Defence in depth |

Demonstrated here with moto (mocked AWS): encrypted S3 archive with Object Lock, least-privilege IAM policy.
Not demonstrated: real Bedrock calls (needs an AWS account and costs money).