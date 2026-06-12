import sys
import os

# Thêm my-production-agent vào PYTHONPATH để nạp app/main
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "my-production-agent"))

import uvicorn
from app.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
