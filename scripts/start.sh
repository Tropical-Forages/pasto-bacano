#!/bin/sh
# Container entry point: one image, two services.
#   PASTO_BACANO_SERVICE=api   the agent API (uvicorn, app.main:create_app)
#   anything else (default)    the Streamlit chat, as before
# PORT is set by Cloud Run; the defaults match the previous Dockerfile.
set -e
if [ "$PASTO_BACANO_SERVICE" = "api" ]; then
  exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8080}"
fi
exec streamlit run app/streamlit_app.py --server.port "${PORT:-8501}" --server.address 0.0.0.0
